import os
import logging
from telegram import Update, Document, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from google_sheets.sheets import GoogleSheetsClient
from feed.feed_generator import XMLFeedGenerator
from s3_async_client import S3AsyncClient
from dotenv import load_dotenv
from datetime import datetime
import pandas as pd

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Отключаем лишние системные логи
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger('aiohttp').setLevel(logging.WARNING)
logging.getLogger('aiobotocore').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Константы
SAVE_DIR = "uploads"
ADMIN_IDS = list(map(int, os.getenv('ADMIN_IDS', '').split(',')))

# Создаем директорию для загрузок, если её нет
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

# Инициализация клиентов
sheets_client = GoogleSheetsClient(os.getenv('GOOGLE_CREDENTIALS_PATH', 'google-credentials.json'))
xml_generator = XMLFeedGenerator()
s3_client = S3AsyncClient(
    access_key=os.getenv('S3_ACCESS_KEY'),
    secret_key=os.getenv('S3_SECRET_KEY'),
    endpoint_url_base=os.getenv('S3_ENDPOINT', '').replace('https://', '').replace('http://', ''),
    bucket_name=os.getenv('S3_BUCKET'),
    public_endpoint=os.getenv('S3_PUBLIC_ENDPOINT')
)

def get_main_menu(is_admin: bool = False):
    """Возвращает основное меню в зависимости от прав пользователя."""
    buttons = [
        ["📤 Загрузить файл", "✅ Проверить файл"],
        ["📋 Получить фид"]
    ]
    if is_admin:
        buttons.append(["👑 Админ-панель"])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_admin_menu():
    """Возвращает меню администратора."""
    buttons = [
        ["📊 Общий фид", "📈 Статистика"],
        ["↩️ Вернуться в главное меню"]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} запустил бота")
    
    is_admin = user_id in ADMIN_IDS
    await update.message.reply_text(
        f"👋 Здравствуйте!\n\n"
        f"Я помогу вам создать XML-фид для каталога недвижимости.\n\n"
        f"Выберите действие в меню:",
        reply_markup=get_main_menu(is_admin)
    )

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок меню."""
    user_id = update.effective_user.id
    text = update.message.text
    logger.info(f"Пользователь {user_id} нажал кнопку: {text}")

    if text == "📤 Загрузить файл":
        await update.message.reply_text(
            "Отправьте мне Excel-файл с каталогом объектов.\n"
            "Файл должен соответствовать шаблону и содержать все обязательные поля."
        )
    
    elif text == "✅ Проверить файл":
        await update.message.reply_text(
            "Отправьте мне Excel-файл для проверки.\n"
            "Я проверю его на соответствие требованиям, но не буду обновлять данные в каталоге."
        )
    
    elif text == "📋 Получить фид":
        await getfeed(update, context)
    
    elif text == "👑 Админ-панель" and user_id in ADMIN_IDS:
        await update.message.reply_text(
            "Панель администратора:",
            reply_markup=get_admin_menu()
        )
    
    elif text == "📊 Общий фид" and user_id in ADMIN_IDS:
        await getallfeed(update, context)
    
    elif text == "📈 Статистика" and user_id in ADMIN_IDS:
        # TODO: Добавить вывод статистики
        await update.message.reply_text("Функция в разработке")
    
    elif text == "↩️ Вернуться в главное меню":
        await update.message.reply_text(
            "Главное меню:",
            reply_markup=get_main_menu(user_id in ADMIN_IDS)
        )

async def validate_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверяет файл на соответствие требованиям без обновления данных."""
    document: Document = update.message.document
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} запросил проверку файла {document.file_name}")

    if document.mime_type not in ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/vnd.ms-excel']:
        return await update.message.reply_text('Пожалуйста, отправьте файл в формате Excel (.xlsx или .xls).')

    try:
        file = await context.bot.get_file(document.file_id)
        file_path = os.path.join(SAVE_DIR, f"validate_{document.file_name}")
        await file.download_to_drive(file_path)
        
        # Проверяем файл через валидатор
        df = pd.read_excel(file_path)
        is_valid, messages = sheets_client.validator.validate_dataframe(df)
        
        if is_valid:
            response = "✅ Файл прошел проверку!\n\n"
            response += f"📊 Количество объектов: {len(df)}\n"
            response += "\nТеперь вы можете загрузить этот файл через кнопку '📤 Загрузить файл'"
        else:
            response = "❌ В файле найдены ошибки:\n\n"
            response += "\n".join(f"- {msg}" for msg in messages)
            
        await update.message.reply_text(response)
        
        # Удаляем временный файл
        os.remove(file_path)
        
    except Exception as e:
        logger.error(f"Ошибка при проверке файла: {e}")
        await update.message.reply_text(f"Произошла ошибка при проверке файла: {str(e)}")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает загруженный Excel файл."""
    document: Document = update.message.document
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} загрузил файл {document.file_name}")

    if document.mime_type not in ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/vnd.ms-excel']:
        return await update.message.reply_text('Пожалуйста, отправьте файл в формате Excel (.xlsx или .xls).')

    try:
        file = await context.bot.get_file(document.file_id)
        file_path = os.path.join(SAVE_DIR, document.file_name)
        await file.download_to_drive(file_path)
        await update.message.reply_text('📥 Файл получен. Обрабатываю...')

        worksheet = sheets_client.get_sheet_client(os.getenv('GOOGLE_SHEET_NAME', 'Каталог недвижимости'))
        if not worksheet:
            return await update.message.reply_text('❌ Ошибка подключения к Google Sheets')

        rows_added, errors = sheets_client.update_sheet_with_excel(
            worksheet,
            file_path,
            str(user_id)
        )

        if errors:
            return await update.message.reply_text(f"❌ Ошибки при обработке файла:\n" + "\n".join(errors))

        # Получаем данные для генерации фида
        records = sheets_client.get_developer_data(worksheet, str(user_id))
        
        output_path = f"uploads/feed_{user_id}.xml"
        if not xml_generator.create_xml_feed(records, output_path, developer_id=str(user_id)):
            return await update.message.reply_text("❌ Ошибка при генерации XML фида")

        url = await s3_client.upload_file(output_path, f"feeds/feed_{user_id}.xml")
        if url:
            await update.message.reply_text(
                f"✅ Файл обработан успешно!\n"
                f"📊 Обработано объектов: {rows_added}\n"
                f"🔗 Фид доступен по ссылке:\n{url}"
            )
        else:
            await update.message.reply_text("❌ Ошибка при загрузке фида в хранилище")

    except Exception as e:
        logger.error(f"Ошибка при обработке файла: {e}")
        await update.message.reply_text(f"❌ Произошла ошибка при обработке файла: {str(e)}")

async def getfeed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерирует и отправляет фид для конкретного застройщика."""
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} запросил свой фид")
    await update.message.reply_text('🔄 Генерирую фид...')

    try:
        worksheet = sheets_client.get_sheet_client(os.getenv('GOOGLE_SHEET_NAME', 'Каталог недвижимости'))
        if not worksheet:
            return await update.message.reply_text('❌ Ошибка подключения к Google Sheets')

        records = sheets_client.get_developer_data(worksheet, str(user_id))
        if not records:
            return await update.message.reply_text('ℹ️ В каталоге нет ваших объектов')

        output_path = f"uploads/feed_{user_id}.xml"
        success = xml_generator.create_xml_feed(
            data=records,
            output_path=output_path,
            developer_id=str(user_id)
        )

        if not success:
            return await update.message.reply_text("❌ Ошибка при генерации XML фида")

        url = await s3_client.upload_file(output_path, f"feeds/feed_{user_id}.xml")
        if url:
            await update.message.reply_text(f"✅ Ваш фид доступен по ссылке:\n{url}")
        else:
            await update.message.reply_text("❌ Ошибка при загрузке фида в хранилище")

    except Exception as e:
        logger.error(f"[ERROR] /getfeed: {e}")
        await update.message.reply_text(f"❌ Произошла ошибка: {str(e)}")

async def getallfeed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерирует и отправляет общий фид со всеми объектами."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        logger.warning(f"Пользователь {user_id} попытался получить общий фид без прав администратора")
        return await update.message.reply_text('⛔️ У вас нет прав для получения общего фида.')

    logger.info(f"Администратор {user_id} запросил общий фид")
    await update.message.reply_text('🔄 Генерирую общий фид...')

    try:
        worksheet = sheets_client.get_sheet_client(os.getenv('GOOGLE_SHEET_NAME', 'Каталог недвижимости'))
        if not worksheet:
            return await update.message.reply_text('❌ Ошибка подключения к Google Sheets')

        records = sheets_client.get_developer_data(worksheet)
        if not records:
            return await update.message.reply_text('ℹ️ В каталоге нет данных')

        output_path = "uploads/feed_all.xml"
        success = xml_generator.create_xml_feed(
            data=records,
            output_path=output_path
        )

        if not success:
            return await update.message.reply_text("❌ Ошибка при генерации XML фида")

        url = await s3_client.upload_file(output_path, "feeds/feed_all.xml")
        if url:
            await update.message.reply_text(f"✅ Общий фид доступен по ссылке:\n{url}")
        else:
            await update.message.reply_text("❌ Ошибка при загрузке фида в хранилище")

    except Exception as e:
        logger.error(f"[ERROR] /getallfeed: {e}")
        await update.message.reply_text(f"❌ Произошла ошибка: {str(e)}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет справочную информацию."""
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} запросил справку")
    
    help_text = (
        "🤖 Я помогаю создавать XML-фиды для каталога недвижимости.\n\n"
        "Доступные команды:\n"
        "📤 Загрузить файл - загрузка Excel-файла с объектами\n"
        "✅ Проверить файл - проверка файла на соответствие требованиям\n"
        "📋 Получить фид - получить ссылку на ваш XML-фид\n\n"
        "Требования к файлу:\n"
        "- Формат: Excel (.xlsx или .xls)\n"
        "- Обязательные поля: internal_id, address, price, area_total\n"
        "- Каждый объект должен иметь уникальный internal_id\n\n"
        "При возникновении проблем обратитесь к администратору."
    )
    
    await update.message.reply_text(help_text)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок."""
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Произошла ошибка при обработке запроса.\n"
            "Пожалуйста, попробуйте позже или обратитесь к администратору."
        ) 
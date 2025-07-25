import os
import logging
import hashlib
from telegram import Update, Document, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from google_sheets.sheets import GoogleSheetsClient
from feed.feed_generator import XMLFeedGenerator
from s3_async_client import S3AsyncClient
from models.file_manager import FileManager, FileMetadata
from dotenv import load_dotenv
from datetime import datetime
import pandas as pd
import uuid

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

# Добавляем FileManager в инициализацию
file_manager = FileManager(SAVE_DIR)

# Константы для типов объектов
OBJECT_TYPES = {
    "residential": "Жилая недвижимость",
    "commercial": "Коммерческая недвижимость",
    "land": "Земельные участки",
    "cottage": "Загородная недвижимость"
}

def get_base_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Возвращает базовую клавиатуру с основными командами."""
    buttons = [
        ["🏠 Главное меню", "❓ Помощь"]
    ]
    second_row = ["📚 Шаблоны/Инструкции"]
    if is_admin:
        second_row.append("🤟 Админ-панель")
    buttons.append(second_row)
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_main_menu_inline() -> InlineKeyboardMarkup:
    """Возвращает inline-клавиатуру главного меню."""
    buttons = [
        [
            InlineKeyboardButton("📤 Загрузить файл", callback_data="menu_upload"),
            InlineKeyboardButton("📋 Мои файлы", callback_data="menu_files")
        ],
        [InlineKeyboardButton("📋 Получить фид", callback_data="menu_feed")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_admin_menu_inline() -> InlineKeyboardMarkup:
    """Возвращает inline-клавиатуру админ-панели."""
    buttons = [
        [InlineKeyboardButton("📊 Общий фид", callback_data="admin_all_feed")],
        [InlineKeyboardButton("📈 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("↩️ Назад", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_object_type_keyboard():
    """Возвращает клавиатуру выбора типа объекта."""
    buttons = []
    for key, value in OBJECT_TYPES.items():
        buttons.append([InlineKeyboardButton(value, callback_data=f"type_{key}")])
    return InlineKeyboardMarkup(buttons)

def get_feed_type_keyboard():
    """Возвращает клавиатуру выбора типа фида."""
    buttons = []
    for key, value in OBJECT_TYPES.items():
        buttons.append([InlineKeyboardButton(f"📋 {value}", callback_data=f"feed_{key}")])
    buttons.append([InlineKeyboardButton("📊 Общий фид", callback_data="feed_all")])
    buttons.append([InlineKeyboardButton("↩️ Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(buttons)

def get_user_feed_keyboard(user_id: str):
    """Возвращает клавиатуру со списком файлов пользователя для генерации фида."""
    files = file_manager.get_user_files(str(user_id))
    buttons = []
    
    if not files:
        buttons.append([InlineKeyboardButton("📤 Загрузить файл", callback_data="upload_new")])
        buttons.append([InlineKeyboardButton("↩️ Назад", callback_data="back_to_main")])
        return InlineKeyboardMarkup(buttons)

    # Группируем файлы по типам
    files_by_type = {}
    for file in files:
        if file.object_type not in files_by_type:
            files_by_type[file.object_type] = []
        files_by_type[file.object_type].append(file)
    
    # Создаем кнопки для каждого типа
    for obj_type, type_files in files_by_type.items():
        buttons.append([InlineKeyboardButton(
            f"📋 {OBJECT_TYPES[obj_type]} ({len(type_files)})",
            callback_data=f"feed_type_{obj_type}"
        )])
    
    # Для админа добавляем кнопку общего фида
    if int(user_id) in ADMIN_IDS:
        buttons.append([InlineKeyboardButton("📊 Общий фид по всем объектам", callback_data="feed_all")])
    
    buttons.append([InlineKeyboardButton("↩️ Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(buttons)

def get_files_by_type_keyboard(user_id: str, object_type: str):
    """Возвращает клавиатуру со списком файлов определенного типа."""
    files = file_manager.get_files_by_type(str(user_id), object_type)
    buttons = []
    
    for file in files:
        status_emoji = {
            "new": "🆕",
            "processing": "⏳",
            "processed": "✅",
            "error": "❌"
        }.get(file.status, "❓")
        
        buttons.append([InlineKeyboardButton(
            f"{status_emoji} {file.original_name}",
            callback_data=f"feed_file_{file.file_id}"
        )])
    
    buttons.append([InlineKeyboardButton("↩️ Назад к типам", callback_data="feed_back_to_types")])
    return InlineKeyboardMarkup(buttons)

async def handle_object_type_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора типа объекта."""
    query = update.callback_query
    await query.answer()
    
    # Получаем тип объекта из callback_data
    obj_type = query.data.split('_')[1]
    
    # Сохраняем выбранный тип в контексте пользователя
    context.user_data['selected_object_type'] = obj_type
    
    await query.message.edit_text(
        f"Выбран тип: {OBJECT_TYPES[obj_type]}\n"
        "Теперь отправьте Excel-файл с объектами этого типа.",
        reply_markup=None
    )

async def handle_file_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик просмотра списка файлов определенного типа."""
    query = update.callback_query
    await query.answer()
    
    obj_type = query.data.split('_')[1]
    user_id = str(update.effective_user.id)
    
    files = file_manager.get_files_by_type(user_id, obj_type)
    if not files:
        await query.message.edit_text(
            f"У вас нет загруженных файлов типа {OBJECT_TYPES[obj_type]}",
            reply_markup=get_file_list_keyboard(user_id)
        )
        return
    
    # Создаем сообщение со списком файлов
    message = f"Файлы типа {OBJECT_TYPES[obj_type]}:\n\n"
    for file in files:
        status_emoji = {
            "new": "🆕",
            "processing": "⏳",
            "processed": "✅",
            "error": "❌"
        }.get(file.status, "❓")
        
        message += (
            f"{status_emoji} {file.original_name}\n"
            f"Загружен: {file.upload_date.strftime('%d.%m.%Y %H:%M')}\n"
            f"Статус: {file.status}\n"
            f"ID: {file.file_id}\n\n"
        )
    
    # Добавляем кнопки действий
    buttons = [
        [InlineKeyboardButton("📤 Загрузить новый", callback_data=f"upload_{obj_type}")],
        [InlineKeyboardButton("↩️ Назад к списку", callback_data="back_to_list")]
    ]
    
    await query.message.edit_text(
        message,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def handle_feed_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора фида."""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    action = query.data.split('_')[1]
    
    if action == "type":
        # Показываем список файлов выбранного типа
        object_type = query.data.split('_')[2]
        await query.message.edit_text(
            f"{user.first_name}, выберите файл для генерации фида:",
            reply_markup=get_files_by_type_keyboard(str(user.id), object_type)
        )
    
    elif action == "file":
        # Генерируем фид для конкретного файла
        file_id = query.data.split('_')[2]
        file_metadata = file_manager.get_file_metadata(file_id)
        
        if not file_metadata:
            await query.message.edit_text(
                f"❌ {user.first_name}, файл не найден",
                reply_markup=get_user_feed_keyboard(str(user.id))
            )
            return
        
        # Проверяем права доступа
        if str(user.id) != file_metadata.user_id and user.id not in ADMIN_IDS:
            await query.message.edit_text(
                f"⛔️ {user.first_name}, у вас нет доступа к этому файлу",
                reply_markup=get_user_feed_keyboard(str(user.id))
            )
            return
        
        await query.message.edit_text(
            f"⏳ {user.first_name}, генерирую фид..."
        )

        try:
            worksheet = sheets_client.get_sheet_client(os.getenv('GOOGLE_SHEET_NAME', 'Каталог недвижимости'))
            if not worksheet:
                return await query.message.edit_text(
                    f'❌ {user.first_name}, ошибка подключения к Google Sheets',
                    reply_markup=get_user_feed_keyboard(str(user.id))
                )

            # Получаем данные из файла
            records = sheets_client.get_developer_data(worksheet, file_metadata.user_id)
            if not records:
                return await query.message.edit_text(
                    f'ℹ️ {user.first_name}, в файле нет данных',
                    reply_markup=get_user_feed_keyboard(str(user.id))
                )

            await query.message.edit_text(
                f"📝 {user.first_name}, создаю XML фид..."
            )

            output_path = f"uploads/feed_{file_metadata.file_id}.xml"
            success = xml_generator.create_xml_feed(
                data=records,
                output_path=output_path,
                developer_id=file_metadata.user_id
            )

            if not success:
                return await query.message.edit_text(
                    f"❌ {user.first_name}, ошибка при генерации XML фида",
                    reply_markup=get_user_feed_keyboard(str(user.id))
                )

            await query.message.edit_text(
                f"📤 {user.first_name}, загружаю фид в хранилище..."
            )

            url = await s3_client.upload_file(output_path, f"feeds/feed_{file_metadata.file_id}.xml")
            if url:
                await query.message.edit_text(
                    f"✅ {user.first_name}, фид для файла {file_metadata.original_name} доступен по ссылке:\n{url}\n\n"
                    f"📊 Количество объектов: {len(records)}",
                    reply_markup=get_user_feed_keyboard(str(user.id))
                )
            else:
                await query.message.edit_text(
                    f"❌ {user.first_name}, ошибка при загрузке фида в хранилище",
                    reply_markup=get_user_feed_keyboard(str(user.id))
                )

        except Exception as e:
            logger.error(f"[ERROR] handle_feed_selection (file): {e}")
            await query.message.edit_text(
                f"❌ {user.first_name}, произошла ошибка: {str(e)}",
                reply_markup=get_user_feed_keyboard(str(user.id))
            )
    
    elif action == "all":
        # Проверяем права администратора
        if user.id not in ADMIN_IDS:
            await query.message.edit_text(
                f"⛔️ {user.first_name}, у вас нет прав для генерации общего фида",
                reply_markup=get_user_feed_keyboard(str(user.id))
            )
            return
        
        await query.message.edit_text(
            f"⏳ {user.first_name}, генерирую общий фид..."
        )

        try:
            worksheet = sheets_client.get_sheet_client(os.getenv('GOOGLE_SHEET_NAME', 'Каталог недвижимости'))
            if not worksheet:
                return await query.message.edit_text(
                    f'❌ {user.first_name}, ошибка подключения к Google Sheets',
                    reply_markup=get_user_feed_keyboard(str(user.id))
                )

            # Получаем все данные
            records = sheets_client.get_developer_data(worksheet)
            if not records:
                return await query.message.edit_text(
                    f'ℹ️ {user.first_name}, нет данных для формирования общего фида',
                    reply_markup=get_user_feed_keyboard(str(user.id))
                )

            await query.message.edit_text(
                f"📝 {user.first_name}, создаю общий XML фид..."
            )

            output_path = "uploads/feed_all.xml"
            success = xml_generator.create_xml_feed(
                data=records,
                output_path=output_path
            )

            if not success:
                return await query.message.edit_text(
                    f"❌ {user.first_name}, ошибка при генерации общего XML фида",
                    reply_markup=get_user_feed_keyboard(str(user.id))
                )

            await query.message.edit_text(
                f"📤 {user.first_name}, загружаю общий фид в хранилище..."
            )

            url = await s3_client.upload_file(output_path, "feeds/feed_all.xml")
            if url:
                await query.message.edit_text(
                    f"✅ {user.first_name}, общий фид доступен по ссылке:\n{url}\n\n"
                    f"📊 Общее количество объектов: {len(records)}",
                    reply_markup=get_user_feed_keyboard(str(user.id))
                )
            else:
                await query.message.edit_text(
                    f"❌ {user.first_name}, ошибка при загрузке общего фида в хранилище",
                    reply_markup=get_user_feed_keyboard(str(user.id))
                )

        except Exception as e:
            logger.error(f"[ERROR] handle_feed_selection (all): {e}")
            await query.message.edit_text(
                f"❌ {user.first_name}, произошла ошибка: {str(e)}",
                reply_markup=get_user_feed_keyboard(str(user.id))
            )
    
    elif action == "back":
        if query.data == "feed_back_to_types":
            await query.message.edit_text(
                f"{user.first_name}, выберите тип объектов для генерации фида:",
                reply_markup=get_user_feed_keyboard(str(user.id))
            )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    user = update.effective_user
    is_admin = user.id in ADMIN_IDS
    
    welcome_text = (
        f"👋 Здравствуйте, {user.first_name}!\n\n"
        "Я помогу вам работать с каталогом недвижимости:\n"
        "• Загружать Excel-файлы с объектами\n"
        "• Управлять загруженными файлами\n"
        "• Генерировать XML-фиды\n\n"
        "Нажмите '🏠 Главное меню' чтобы начать работу или '❓ Помощь' для получения справки."
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_base_keyboard(is_admin)
    )

async def show_file_details(update: Update, context: ContextTypes.DEFAULT_TYPE, file_metadata: FileMetadata):
    """Показывает детали файла и опции действий."""
    status_emoji = {
        "new": "🆕",
        "processing": "⏳",
        "processed": "✅",
        "error": "❌"
    }.get(file_metadata.status, "❓")
    
    message = (
        f"{status_emoji} Файл: {file_metadata.original_name}\n"
        f"📅 Загружен: {file_metadata.upload_date.strftime('%d.%m.%Y %H:%M')}\n"
        f"📊 Тип: {OBJECT_TYPES[file_metadata.object_type]}\n"
        f"ℹ️ Статус: {file_metadata.status}\n"
    )
    
    if file_metadata.description:
        message += f"📝 Примечание: {file_metadata.description}\n"
    
    buttons = [
        [InlineKeyboardButton("🔄 Обновить данные", callback_data=f"update_{file_metadata.file_id}")],
        [InlineKeyboardButton("❌ Удалить файл", callback_data=f"delete_{file_metadata.file_id}")],
        [InlineKeyboardButton("↩️ Назад к списку", callback_data="back_files")]
    ]
    
    return await update.callback_query.message.edit_text(
        message,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def handle_file_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик действий с файлами."""
    query = update.callback_query
    await query.answer()
    
    action = query.data.split('_', 1)[0]
    file_id = query.data.split('_')[-1]
    user = update.effective_user

    if action == "back":
        # Обработка всех кнопок "Назад"
        back_action = query.data.split('_')[1]
        
        if back_action == "files":
            # Возврат к списку файлов
            await show_user_files(update, context)
            return
        elif back_action == "main":
            # Возврат в главное меню
            await query.message.edit_text(
                f"{user.first_name}, выберите действие:",
                reply_markup=get_main_menu_inline()
            )
            return
        elif back_action == "types":
            # Возврат к списку типов файлов
            await query.message.edit_text(
                f"{user.first_name}, выберите тип объектов:",
                reply_markup=get_user_feed_keyboard(str(user.id))
            )
            return
    
    elif action == "file":
        # Показываем детали файла
        file_metadata = file_manager.get_file_metadata(file_id)
        if file_metadata:
            await show_file_details(update, context, file_metadata)
        else:
            await query.message.edit_text(
                "❌ Файл не найден",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("↩️ Назад к списку", callback_data="back_files")
                ]])
            )
    
    elif action == "update":
        # Подтверждение обновления
        file_metadata = file_manager.get_file_metadata(file_id)
        if not file_metadata:
            await query.message.edit_text("❌ Файл не найден")
            return
            
        # Проверяем права доступа
        if str(user.id) != file_metadata.user_id and user.id not in ADMIN_IDS:
            await query.message.edit_text(
                f"⛔️ {user.first_name}, у вас нет прав для обновления этого файла",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("↩️ Назад", callback_data="back_files")
                ]])
            )
            return
            
        # Сохраняем ID файла для обновления в контексте
        context.user_data['updating_file_id'] = file_id
        
        await query.message.edit_text(
            f"{user.first_name}, вы уверены, что хотите обновить данные из файла {file_metadata.original_name}?\n\n"
            "⚠️ Отправьте новый Excel файл для обновления данных или нажмите 'Отмена'",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отмена", callback_data=f"file_{file_id}")]
            ])
        )
    
    elif action == "delete":
        # Подтверждение удаления
        file_metadata = file_manager.get_file_metadata(file_id)
        if not file_metadata:
            await query.message.edit_text("❌ Файл не найден")
            return
            
        # Проверяем права доступа
        if str(user.id) != file_metadata.user_id and user.id not in ADMIN_IDS:
            await query.message.edit_text(
                f"⛔️ {user.first_name}, у вас нет прав для удаления этого файла",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("↩️ Назад", callback_data="back_files")
                ]])
            )
            return
            
        await query.message.edit_text(
            f"{user.first_name}, вы уверены, что хотите удалить файл {file_metadata.original_name}?\n"
            "⚠️ Это действие нельзя будет отменить!",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Да", callback_data=f"confirm_delete_{file_id}"),
                    InlineKeyboardButton("❌ Нет", callback_data=f"file_{file_id}")
                ]
            ])
        )
    
    elif action == "confirm":
        sub_action = query.data.split('_')[1]
        if sub_action == "delete":
            # Получаем метаданные файла
            file_metadata = file_manager.get_file_metadata(file_id)
            if not file_metadata:
                await query.message.edit_text(
                    "❌ Файл не найден",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("↩️ Назад к списку", callback_data="back_files")
                    ]])
                )
                return

            # Проверяем права доступа
            if str(user.id) != file_metadata.user_id and user.id not in ADMIN_IDS:
                await query.message.edit_text(
                    f"⛔️ {user.first_name}, у вас нет прав для удаления этого файла",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("↩️ Назад", callback_data="back_files")
                    ]])
                )
                return

            try:
                # Удаляем записи из Google Sheets
                worksheet = sheets_client.get_sheet_client(os.getenv('GOOGLE_SHEET_NAME', 'Каталог недвижимости'))
                if worksheet:
                    await query.message.edit_text(
                        f"🗑 {user.first_name}, удаляю данные из Google Sheets..."
                    )
                    # Удаляем записи через метод обновления с пустым DataFrame
                    sheets_client.update_sheet_with_excel(worksheet, None, str(user.id), file_id)

                # Удаляем файл из S3
                await query.message.edit_text(
                    f"🗑 {user.first_name}, удаляю файлы из хранилища..."
                )
                await s3_client.delete_file(f"feeds/feed_{file_id}.xml")

                # Удаляем метаданные файла
                if file_manager.delete_file(file_id):
                    await query.message.edit_text(
                        f"✅ {user.first_name}, файл и все связанные данные успешно удалены",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("↩️ Назад к списку", callback_data="back_files")
                        ]])
                    )
                else:
                    await query.message.edit_text(
                        f"⚠️ {user.first_name}, возникли проблемы при удалении файла",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("↩️ Назад к списку", callback_data="back_files")
                        ]])
                    )

            except Exception as e:
                logger.error(f"Ошибка при удалении файла и данных: {e}")
                await query.message.edit_text(
                    f"❌ {user.first_name}, произошла ошибка при удалении: {str(e)}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("↩️ Назад к файлу", callback_data=f"file_{file_id}")
                    ]])
                )

async def show_user_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список файлов пользователя."""
    # Определяем, вызвана ли функция из callback_query или из обычного сообщения
    if update.callback_query:
        message = update.callback_query.message
        user = update.callback_query.from_user
    else:
        message = update.message
        user = update.effective_user

    files = file_manager.get_user_files(str(user.id))
    
    if not files:
        text = (
            f"{user.first_name}, у вас пока нет загруженных файлов.\n"
            "Используйте кнопку '📤 Загрузить файл' чтобы добавить новый файл."
        )
        if update.callback_query:
            await message.edit_text(
                text,
                reply_markup=get_main_menu_inline()
            )
        else:
            await message.reply_text(
                text,
                reply_markup=get_base_keyboard(user.id in ADMIN_IDS)
            )
        return
    
    # Группируем файлы по типам
    files_by_type = {}
    for file in files:
        if file.object_type not in files_by_type:
            files_by_type[file.object_type] = []
        files_by_type[file.object_type].append(file)
    
    message_text = f"📋 {user.first_name}, вот список ваших файлов:\n\n"
    buttons = []
    
    for obj_type, type_files in files_by_type.items():
        message_text += f"\n{OBJECT_TYPES[obj_type]}:\n"
        for file in type_files:
            status_emoji = {
                "new": "🆕",
                "processing": "⏳",
                "processed": "✅",
                "error": "❌"
            }.get(file.status, "❓")
            message_text += f"{status_emoji} {file.original_name}\n"
            buttons.append([InlineKeyboardButton(
                f"{status_emoji} {file.original_name}",
                callback_data=f"file_{file.file_id}"
            )])
    
    buttons.append([InlineKeyboardButton("↩️ В главное меню", callback_data="back_main")])
    
    if update.callback_query:
        await message.edit_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        await message.reply_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

def generate_file_id(file_content: bytes, user_id: str, object_type: str, filename: str) -> str:
    """Генерирует уникальный ID файла на основе его имени и метаданных."""
    # Используем имя файла вместо содержимого
    combined = f"{filename}:{user_id}:{object_type}"
    return hashlib.sha256(combined.encode()).hexdigest()[:32]

async def process_excel_file(file_content: bytes, document: Document, user_id: str, object_type: str) -> tuple[str, str]:
    """
    Обрабатывает содержимое Excel файла и возвращает file_id и путь к сохраненному файлу.
    """
    # Генерируем file_id на основе имени файла и метаданных
    file_id = generate_file_id(file_content, user_id, object_type, document.file_name)
    
    # Создаем путь для сохранения файла
    file_path = os.path.join(SAVE_DIR, f"{file_id}_{document.file_name}")
    
    # Сохраняем файл
    with open(file_path, 'wb') as f:
        f.write(file_content)
    
    return file_id, file_path

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает загруженный Excel файл."""
    document: Document = update.message.document
    user = update.effective_user
    temp_file_path = None
    
    logger.info(f"Пользователь {user.id} ({user.first_name}) загрузил файл {document.file_name}")
    
    try:
        # Проверяем, является ли это обновлением существующего файла
        updating_file_id = context.user_data.get('updating_file_id')
        if updating_file_id:
            # Очищаем ID обновляемого файла из контекста
            del context.user_data['updating_file_id']
            await handle_file_update(update, context, updating_file_id)
            return
        
        # Проверяем, был ли выбран тип объекта
        if 'selected_object_type' not in context.user_data:
            await update.message.reply_text(
                f"{user.first_name}, пожалуйста, сначала выберите тип объекта:",
                reply_markup=get_object_type_keyboard()
            )
            return

        obj_type = context.user_data['selected_object_type']
        
        if document.mime_type not in ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/vnd.ms-excel']:
            return await update.message.reply_text(
                f"{user.first_name}, пожалуйста, отправьте файл в формате Excel (.xlsx или .xls)."
            )

        # Скачиваем файл во временную память
        file = await context.bot.get_file(document.file_id)
        file_content = await file.download_as_bytearray()
        
        # Обрабатываем файл и получаем его ID и путь
        file_id, temp_file_path = await process_excel_file(file_content, document, str(user.id), obj_type)
        
        # Проверяем, существует ли уже файл с таким ID
        existing_file = file_manager.get_file_metadata(file_id)
        if existing_file:
            # Если файл существует, предлагаем обновить его
            context.user_data['updating_file_id'] = file_id
            await update.message.reply_text(
                f"📝 {user.first_name}, файл с таким содержимым уже существует.\n"
                f"Название: {existing_file.original_name}\n"
                f"Загружен: {existing_file.upload_date}\n\n"
                "Хотите обновить существующий файл?",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Да", callback_data=f"update_{file_id}"),
                        InlineKeyboardButton("❌ Нет", callback_data="back_main")
                    ]
                ])
            )
            return
        
        # Добавляем метаданные файла
        metadata = file_manager.add_file(
            file_id=file_id,
            original_name=document.file_name,
            user_id=str(user.id),
            object_type=obj_type
        )
        
        await update.message.reply_text(
            f"📥 {user.first_name}, файл получен. Начинаю обработку..."
        )

        # Обновляем статус
        file_manager.update_file_status(file_id, "processing")

        worksheet = sheets_client.get_sheet_client(os.getenv('GOOGLE_SHEET_NAME', 'Каталог недвижимости'))
        if not worksheet:
            file_manager.update_file_status(file_id, "error", "Ошибка подключения к Google Sheets")
            await update.message.reply_text(
                f"❌ {user.first_name}, произошла ошибка при подключении к Google Sheets"
            )
            return

        # Обновляем данные в Google Sheets
        rows_added, messages = sheets_client.update_sheet_with_excel(
            worksheet,
            temp_file_path,
            str(user.id),
            file_id
        )

        if messages:  # Если есть ошибки
            file_manager.update_file_status(file_id, "error", "; ".join(messages))
            await update.message.reply_text(
                f"❌ {user.first_name}, при обработке файла возникли ошибки:\n" + "\n".join(messages)
            )
            return

        # Генерируем XML-фид
        try:
            records = sheets_client.get_developer_data(worksheet, str(user.id), file_id)
            xml_content = xml_generator.generate_feed(records)
            
            # Загружаем фид в S3
            s3_filename = f"feed_{file_id}.xml"
            public_url = await s3_client.upload_file(xml_content, s3_filename)
            
            if not public_url:
                raise Exception("Не удалось загрузить фид в S3")
            
            # Обновляем статус и отправляем сообщение об успехе
            file_manager.update_file_status(file_id, "processed")
            
            await update.message.reply_text(
                f"✅ {user.first_name}, файл успешно обработан!\n"
                f"📊 Добавлено записей: {rows_added}\n"
                f"🔗 Ссылка на XML-фид: {public_url}"
            )
            
        except Exception as e:
            logger.error(f"Ошибка при генерации фида: {e}")
            file_manager.update_file_status(file_id, "error", "Ошибка при генерации XML-фида")
            await update.message.reply_text(
                f"❌ {user.first_name}, произошла ошибка при создании XML-фида"
            )

    except Exception as e:
        logger.error(f"Ошибка при обработке файла: {e}")
        await update.message.reply_text(
            f"❌ {user.first_name}, произошла ошибка при обработке файла. Пожалуйста, попробуйте позже или обратитесь к администратору."
        )
    
    finally:
        # Удаляем временный файл, если он был создан
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.debug(f"Удален временный файл: {temp_file_path}")
            except Exception as e:
                logger.error(f"Ошибка при удалении временного файла {temp_file_path}: {e}")

async def handle_file_update(update: Update, context: ContextTypes.DEFAULT_TYPE, file_id: str):
    """Обрабатывает обновление существующего файла."""
    document: Document = update.message.document
    user = update.effective_user
    
    if document.mime_type not in ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/vnd.ms-excel']:
        return await update.message.reply_text(
            f"{user.first_name}, пожалуйста, отправьте файл в формате Excel (.xlsx или .xls)."
        )

    try:
        # Получаем метаданные обновляемого файла
        file_metadata = file_manager.get_file_metadata(file_id)
        if not file_metadata:
            return await update.message.reply_text("❌ Файл для обновления не найден")
        
        # Проверяем права доступа
        if str(user.id) != file_metadata.user_id and user.id not in ADMIN_IDS:
            return await update.message.reply_text("⛔️ У вас нет прав для обновления этого файла")

        # Сохраняем новый файл
        file = await context.bot.get_file(document.file_id)
        file_path = os.path.join(SAVE_DIR, f"update_{file_id}_{document.file_name}")
        await file.download_to_drive(file_path)
        
        await update.message.reply_text(
            f"📥 {user.first_name}, файл получен. Начинаю обновление данных..."
        )

        # Обновляем статус
        file_manager.update_file_status(file_id, "processing")

        worksheet = sheets_client.get_sheet_client(os.getenv('GOOGLE_SHEET_NAME', 'Каталог недвижимости'))
        if not worksheet:
            file_manager.update_file_status(file_id, "error", "Ошибка подключения к Google Sheets")
            return await update.message.reply_text(
                f"❌ {user.first_name}, произошла ошибка при подключении к Google Sheets"
            )

        await update.message.reply_text(
            f"📊 {user.first_name}, проверяю и обновляю данные..."
        )

        # Передаем file_id в метод обновления
        rows_added, errors = sheets_client.update_sheet_with_excel(
            worksheet,
            file_path,
            str(user.id),
            file_id
        )

        if errors:
            file_manager.update_file_status(file_id, "error", "\n".join(errors))
            return await update.message.reply_text(
                f"❌ {user.first_name}, при обновлении данных возникли ошибки:\n" + "\n".join(errors)
            )

        # Обновляем метаданные файла
        file_metadata.original_name = document.file_name
        file_manager.update_file_status(file_id, "processed")

        await update.message.reply_text(
            f"✅ {user.first_name}, данные успешно обновлены!\n"
            f"📊 Обработано объектов: {rows_added}"
        )

        # Генерируем новый фид
        await update.message.reply_text(
            f"📈 {user.first_name}, генерирую обновленный XML фид..."
        )

        # Получаем только данные из обновленного файла
        records = sheets_client.get_developer_data(worksheet, str(user.id), file_id)
        output_path = f"uploads/feed_{file_id}.xml"
        if not xml_generator.create_xml_feed(records, output_path, developer_id=str(user.id)):
            return await update.message.reply_text(
                f"❌ {user.first_name}, ошибка при генерации XML фида"
            )

        url = await s3_client.upload_file(output_path, f"feeds/feed_{file_id}.xml")
        if url:
            await update.message.reply_text(
                f"✅ {user.first_name}, обновленный фид доступен по ссылке:\n{url}\n"
                f"📊 Количество объектов в файле: {len(records)}"
            )
        else:
            await update.message.reply_text(
                f"❌ {user.first_name}, ошибка при загрузке фида в хранилище"
            )

    except Exception as e:
        logger.error(f"Ошибка при обновлении файла: {e}")
        file_manager.update_file_status(file_id, "error", str(e))
        await update.message.reply_text(
            f"❌ {user.first_name}, произошла ошибка при обновлении файла: {str(e)}"
        )
    finally:
        # Удаляем временный файл
        if os.path.exists(file_path):
            os.remove(file_path)

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
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        logger.warning(f"Пользователь {user.id} попытался получить общий фид без прав администратора")
        message = "⛔️ У вас нет прав для получения общего фида."
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(message)
        else:
            await update.message.reply_text(message)
        return

    logger.info(f"Администратор {user.id} запросил общий фид")
    
    # Отправляем начальное сообщение
    if update.callback_query:
        await update.callback_query.answer()
        message = await update.callback_query.message.reply_text('🔄 Генерирую общий фид...')
    else:
        message = await update.message.reply_text('🔄 Генерирую общий фид...')

    try:
        worksheet = sheets_client.get_sheet_client(os.getenv('GOOGLE_SHEET_NAME', 'Каталог недвижимости'))
        if not worksheet:
            await message.edit_text('❌ Ошибка подключения к Google Sheets')
            return

        records = sheets_client.get_developer_data(worksheet)
        if not records:
            await message.edit_text('ℹ️ В каталоге нет объектов')
            return

        # Генерируем XML-фид
        xml_content = xml_generator.generate_feed(records)
        
        # Загружаем фид в S3
        s3_filename = "feed_all.xml"
        public_url = await s3_client.upload_file(xml_content, s3_filename)
        
        if public_url:
            await message.edit_text(
                f"✅ Общий фид сгенерирован!\n"
                f"📊 Всего объектов: {len(records)}\n"
                f"🔗 Ссылка на фид: {public_url}"
            )
        else:
            await message.edit_text("❌ Ошибка при загрузке фида в хранилище")

    except Exception as e:
        logger.error(f"Ошибка при генерации общего фида: {e}")
        await message.edit_text(f"❌ Произошла ошибка при генерации фида")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help."""
    help_text = (
        "🔍 *Как пользоваться ботом:*\n\n"
        "*Основные команды:*\n"
        "🏠 Главное меню - открыть основное меню\n"
        "❓ Помощь - показать эту справку\n\n"
        "*Работа с файлами:*\n"
        "1. Откройте главное меню\n"
        "2. Выберите '📤 Загрузить файл'\n"
        "3. Укажите тип объектов\n"
        "4. Загрузите Excel-файл\n\n"
        "*Управление файлами:*\n"
        "• '📋 Мои файлы' - просмотр и управление файлами\n"
        "• '📋 Получить фид' - генерация XML-фида\n\n"
        "Используйте кнопки навигации ↩️ для возврата в предыдущее меню."
    )
    await update.message.reply_text(
        help_text,
        parse_mode='Markdown'
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок."""
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Произошла ошибка при обработке запроса.\n"
            "Пожалуйста, попробуйте позже или обратитесь к администратору."
        ) 

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок базовой клавиатуры."""
    user = update.effective_user
    text = update.message.text
    
    if text == "🏠 Главное меню":
        await update.message.reply_text(
            f"{user.first_name}, выберите действие:",
            reply_markup=get_main_menu_inline()
        )
    
    elif text == "❓ Помощь":
        await help_command(update, context)
    
    elif text == "📚 Шаблоны/Инструкции":
        await handle_templates(update, context)
    
    elif text == "🤟 Админ-панель" and user.id in ADMIN_IDS:
        await update.message.reply_text(
            f"{user.first_name}, панель администратора:",
            reply_markup=get_admin_menu_inline()
        ) 

async def menu_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик inline-кнопок меню."""
    query = update.callback_query
    await query.answer()
    
    action = query.data.split('_', 1)[1]
    user = update.effective_user

    if action == "upload":
        await query.message.edit_text(
            f"{user.first_name}, выберите тип объектов недвижимости:",
            reply_markup=get_object_type_keyboard()
        )
    
    elif action == "files":
        await show_user_files(update, context)
    
    elif action == "feed":
        await query.message.edit_text(
            f"{user.first_name}, выберите файл для генерации фида:",
            reply_markup=get_user_feed_keyboard(str(user.id))
        )
    
    elif action == "back_main":
        # Очищаем все контексты
        context.user_data.clear()
        
        # Возвращаемся в главное меню
        await query.message.edit_text(
            f"{user.first_name}, выберите действие:",
            reply_markup=get_main_menu_inline()
        ) 

async def handle_template_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик действий с шаблонами и инструкциями."""
    query = update.callback_query
    await query.answer()
    
    action = query.data.split('_')[1]
    
    if action == "excel":
        # Отправляем шаблон Excel
        template_path = "templates/partner_template.xlsx"
        await query.message.reply_document(
            document=open(template_path, 'rb'),
            filename="template.xlsx",
            caption=(
                "📊 Шаблон для подготовки данных:\n\n"
                "• Заполните все обязательные поля\n"
                "• Следуйте инструкции по заполнению\n"
                "• Проверьте данные перед отправкой"
            )
        )
    
    elif action == "docs":
        # Показываем опции для инструкции
        await query.message.edit_text(
            "📖 Выберите формат инструкции:",
            reply_markup=get_docs_keyboard()
        )
    
    elif action == "back":
        # Возвращаемся к выбору шаблонов
        await query.message.edit_text(
            "📚 Выберите нужный документ:\n\n"
            "• Excel шаблон - готовая структура для ваших данных\n"
            "• Инструкция - подробное описание всех полей и правил",
            reply_markup=get_templates_keyboard()
        )

async def handle_docs_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик действий с документацией."""
    query = update.callback_query
    await query.answer()
    
    action = query.data.split('_')[1]
    
    if action == "md":
        # Отправляем markdown файл
        docs_path = "templates/partner_template_description.md"
        await query.message.reply_document(
            document=open(docs_path, 'rb'),
            filename="instructions.md",
            caption="📝 Инструкция в формате Markdown"
        )
    
    elif action == "pdf":
        # TODO: Добавить конвертацию MD в PDF
        await query.message.reply_text(
            "🔄 Функция скачивания в PDF будет доступна в ближайшее время.\n"
            "Пока вы можете использовать Markdown версию или прочитать инструкцию в чате."
        )
    
    elif action == "read":
        # Читаем MD файл и отправляем его содержимое
        with open("templates/partner_template_description.md", 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Разбиваем на секции (пропускаем первый символ # в начале файла)
        sections = content[1:].split('\n## ')
        main_section = sections[0]  # Основная секция с введением
        
        # Создаем список доступных разделов
        section_buttons = []
        for i, section in enumerate(sections[1:], 1):  # Начинаем с 1, так как 0 - это введение
            title = section.split('\n')[0]
            section_buttons.append([InlineKeyboardButton(title, callback_data=f"section_{i}")])
        
        section_buttons.append([InlineKeyboardButton("↩️ Назад", callback_data="template_back")])
        
        # Отправляем введение и список разделов
        intro_text = (
            "📖 Инструкция по подготовке данных\n\n" +
            main_section.split('\n', 1)[1] + "\n\n" +  # Пропускаем заголовок введения
            "Выберите раздел для подробной информации:"
        )
        
        # Если текст слишком длинный, обрезаем его
        if len(intro_text) > 4096:
            intro_text = intro_text[:4000] + "\n\n(введение слишком длинное, скачайте полную версию)"
        
        await query.message.edit_text(
            intro_text,
            reply_markup=InlineKeyboardMarkup(section_buttons),
            parse_mode='Markdown'
        )

async def handle_section_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик просмотра разделов документации."""
    query = update.callback_query
    await query.answer()
    
    section_idx = int(query.data.split('_')[1])
    
    try:
        # Читаем MD файл
        with open("templates/partner_template_description.md", 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Разбиваем на секции (пропускаем первый символ # в начале файла)
        sections = content[1:].split('\n## ')
        
        if 0 <= section_idx < len(sections):
            # Получаем текст выбранной секции
            section_content = f"## {sections[section_idx]}"
            
            # Если текст слишком длинный, обрезаем его
            if len(section_content) > 4096:
                section_content = section_content[:4000] + "\n\n(раздел слишком длинный, скачайте полную версию)"
            
            # Создаем навигационные кнопки
            nav_buttons = []
            if section_idx > 0:
                nav_buttons.append(InlineKeyboardButton("⬅️ Предыдущий", callback_data=f"section_{section_idx-1}"))
            if section_idx < len(sections) - 1:
                nav_buttons.append(InlineKeyboardButton("➡️ Следующий", callback_data=f"section_{section_idx+1}"))
            
            buttons = [nav_buttons] if nav_buttons else []
            buttons.append([InlineKeyboardButton("📖 К списку разделов", callback_data="docs_read")])
            buttons.append([InlineKeyboardButton("↩️ Назад", callback_data="template_back")])
            
            # Отправляем текст секции
            await query.message.edit_text(
                section_content,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode='Markdown'
            )
        else:
            # Если индекс за пределами списка, возвращаемся к списку разделов
            await query.message.edit_text(
                "⚠️ Раздел не найден. Выберите раздел из списка:",
                reply_markup=get_docs_keyboard()
            )
    except Exception as e:
        logger.error(f"Ошибка при просмотре раздела: {e}")
        await query.message.edit_text(
            "❌ Произошла ошибка при загрузке раздела. Попробуйте снова или выберите другой раздел.",
            reply_markup=get_docs_keyboard()
        )

def get_templates_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру с опциями шаблонов и инструкций."""
    buttons = [
        [InlineKeyboardButton("📥 Скачать шаблон Excel", callback_data="template_excel")],
        [InlineKeyboardButton("📖 Инструкция по заполнению", callback_data="template_docs")],
        [InlineKeyboardButton("↩️ Назад", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_docs_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру с опциями для инструкции."""
    buttons = [
        [InlineKeyboardButton("📥 Скачать в PDF", callback_data="docs_pdf")],
        [InlineKeyboardButton("📥 Скачать в Markdown", callback_data="docs_md")],
        [InlineKeyboardButton("📖 Читать в чате", callback_data="docs_read")],
        [InlineKeyboardButton("↩️ Назад", callback_data="template_back")]
    ]
    return InlineKeyboardMarkup(buttons)

async def handle_templates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки Шаблоны/Инструкции."""
    await update.message.reply_text(
        "📚 Выберите нужный документ:\n\n"
        "• Excel шаблон - готовая структура для ваших данных\n"
        "• Инструкция - подробное описание всех полей и правил",
        reply_markup=get_templates_keyboard()
    ) 
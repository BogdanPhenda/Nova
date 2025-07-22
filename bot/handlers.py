import os
import logging
from telegram import Update, Document, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from google_sheets.sheets import get_sheet_client, update_sheet_with_excel
from feed.feed_generator import create_xml_feed
from datetime import datetime
from s3_async_client import S3Client

SAVE_DIR = 'uploads'
GREETINGS = ["привет", "здравств", "hello", "hi", "добрый день", "доброе утро", "добрый вечер"]
ADMIN_IDS = {941701865}  # Замените на реальные user_id админов

# --- Меню ---
def get_main_menu():
    return ReplyKeyboardMarkup([["Меню"]], resize_keyboard=True)

def get_inline_menu(is_admin=False):
    buttons = [
        [InlineKeyboardButton("📥 Загрузить Excel", callback_data="upload_excel")],
        [InlineKeyboardButton("📄 Получить мой фид", callback_data="getfeed")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    if is_admin:
        buttons.append([InlineKeyboardButton("🌐 Общий фид", callback_data="getallfeed")])
    return InlineKeyboardMarkup(buttons)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name or "друг"
    is_admin = update.effective_user.id in ADMIN_IDS
    logging.info(f"[START] /start от user_id={update.effective_user.id}")
    await update.message.reply_text(
        f'Привет, {user_first_name}! Я помогу тебе с генерацией фида. Нажмите "Меню" для выбора действия.',
        reply_markup=get_main_menu()
    )

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_admin = update.effective_user.id in ADMIN_IDS
    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=get_inline_menu(is_admin)
    )

async def inline_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, s3_client: S3Client):
    query = update.callback_query
    user_id = query.from_user.id
    is_admin = user_id in ADMIN_IDS
    await query.answer()
    if query.data == "getfeed":
        # Имитация команды /getfeed
        class DummyUpdate:
            effective_user = query.from_user
            message = query.message
        await getfeed(DummyUpdate, context, s3_client)
    elif query.data == "help":
        class DummyUpdate:
            effective_user = query.from_user
            message = query.message
        await help_command(DummyUpdate, context)
    elif query.data == "getallfeed" and is_admin:
        class DummyUpdate:
            effective_user = query.from_user
            message = query.message
        await getallfeed(DummyUpdate, context, s3_client)
    elif query.data == "upload_excel":
        await query.edit_message_text("Просто отправьте Excel-файл в этот чат, и я его обработаю!")
    else:
        await query.edit_message_text("Неизвестное действие.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"[START] handle_document от user_id={update.effective_user.id}")
    document: Document = update.message.document
    if document.mime_type in ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/vnd.ms-excel']:
        file = await context.bot.get_file(document.file_id)
        file_path = os.path.join(SAVE_DIR, document.file_name)
        await file.download_to_drive(file_path)
        await update.message.reply_text(f'Файл {document.file_name} получен. Обрабатываю...')
        worksheet = get_sheet_client(os.getenv('GOOGLE_CREDENTIALS_PATH'), os.getenv('GOOGLE_SHEET_NAME'))
        if worksheet:
            developer_id = update.effective_user.id
            rows_added = update_sheet_with_excel(worksheet, file_path, developer_id)
            if rows_added > 0:
                logging.info(f"[SUCCESS] handle_document: добавлено {rows_added} строк для user_id={developer_id}")
                await update.message.reply_text(f'Данные из файла успешно добавлены в Google Таблицу!')
            else:
                logging.warning(f"[FAIL] handle_document: не удалось добавить строки для user_id={developer_id}")
                await update.message.reply_text('Ошибка при добавлении данных в Google Таблицу. Проверьте лог.')
        else:
            logging.error(f"[ERROR] handle_document: ошибка подключения к Google Таблице для user_id={update.effective_user.id}")
            await update.message.reply_text('Ошибка подключения к Google Таблице. Проверьте настройки.')
    else:
        logging.warning(f"[FAIL] handle_document: неверный формат файла от user_id={update.effective_user.id}")
        await update.message.reply_text('Пожалуйста, отправьте файл в формате Excel (.xlsx или .xls).')

async def getfeed(update: Update, context: ContextTypes.DEFAULT_TYPE, s3_client: S3Client):
    user_id = update.effective_user.id
    logging.info(f"[START] /getfeed от user_id={user_id}")
    await update.message.reply_text('Генерирую фид...')
    worksheet = get_sheet_client(os.getenv('GOOGLE_CREDENTIALS_PATH'), os.getenv('GOOGLE_SHEET_NAME'))
    if not worksheet:
        logging.error(f"[ERROR] /getfeed: ошибка подключения к Google Таблице для user_id={user_id}")
        await update.message.reply_text('Ошибка подключения к Google Таблице. Проверьте настройки.')
        return
    all_records = worksheet.get_all_records()
    user_records = [rec for rec in all_records if rec.get('developer_telegram_id') == user_id]
    if not user_records:
        logging.info(f"[INFO] /getfeed: нет данных для user_id={user_id}")
        await update.message.reply_text('В таблице нет данных от вас. Сначала загрузите Excel-файл.')
        return
    public_feed_path = os.path.join(SAVE_DIR, f'feed_{user_id}.xml')
    if create_xml_feed(user_records, public_feed_path):
        object_name = f'feeds/feed_{user_id}.xml'
        public_url = await s3_client.upload_file(public_feed_path, object_name)
        if public_url:
            logging.info(f"[SUCCESS] /getfeed: ссылка сгенерирована для user_id={user_id}: {public_url}")
            await update.message.reply_text(f'✅ Данные в хранилище успешно обновлены!\n\n🔗 Ваша ссылка на фид:\n{public_url}')
        else:
            logging.error(f"[ERROR] /getfeed: ошибка загрузки в S3 для user_id={user_id}")
            await update.message.reply_text('Ошибка при загрузке фида в S3. Проверьте логи.')
    else:
        logging.error(f"[ERROR] /getfeed: ошибка генерации фида для user_id={user_id}")
        await update.message.reply_text('Ошибка при генерации фида. Проверьте логи.')

async def getallfeed(update: Update, context: ContextTypes.DEFAULT_TYPE, s3_client: S3Client):
    user_id = update.effective_user.id
    logging.info(f"[START] /getallfeed от user_id={user_id}")
    if user_id not in ADMIN_IDS:
        logging.warning(f"[FAIL] /getallfeed: попытка доступа не-админа user_id={user_id}")
        await update.message.reply_text('У вас нет прав для получения общего фида.')
        return
    await update.message.reply_text('Генерирую общий фид...')
    worksheet = get_sheet_client(os.getenv('GOOGLE_CREDENTIALS_PATH'), os.getenv('GOOGLE_SHEET_NAME'))
    if not worksheet:
        logging.error(f"[ERROR] /getallfeed: ошибка подключения к Google Таблице")
        await update.message.reply_text('Ошибка подключения к Google Таблице. Проверьте настройки.')
        return
    all_records = worksheet.get_all_records()
    public_feed_path = os.path.join(SAVE_DIR, 'feed_all.xml')
    if create_xml_feed(all_records, public_feed_path):
        object_name = 'feeds/feed_all.xml'
        public_url = await s3_client.upload_file(public_feed_path, object_name)
        if public_url:
            logging.info(f"[SUCCESS] /getallfeed: общий фид обновлён: {public_url}")
            await update.message.reply_text(f'✅ Общий фид успешно обновлён!\n\n🔗 Ссылка на общий фид:\n{public_url}')
        else:
            logging.error(f"[ERROR] /getallfeed: ошибка загрузки общего фида в S3")
            await update.message.reply_text('Ошибка при загрузке общего фида в S3. Проверьте логи.')
    else:
        logging.error(f"[ERROR] /getallfeed: ошибка генерации общего фида")
        await update.message.reply_text('Ошибка при генерации общего фида. Проверьте логи.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name or "друг"
    is_admin = update.effective_user.id in ADMIN_IDS
    logging.info(f"[START] /help от user_id={update.effective_user.id}")
    await update.message.reply_text(
        f'👋 {user_first_name}, вот что я умею:\n'
        '- Пришли Excel-файл с каталогом — я добавлю его в Google Таблицу.\n'
        '- Используй /getfeed — я сгенерирую и пришлю ссылку на твой фид.\n'
        + ('- Используй /getallfeed — общий фид по всем застройщикам (только для админов).\n' if is_admin else '') +
        'Если нужна помощь — просто напиши /help.',
        reply_markup=get_main_menu()
    )

async def greeting_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name or "друг"
    is_admin = update.effective_user.id in ADMIN_IDS
    logging.info(f"[START] greeting_handler от user_id={update.effective_user.id}")
    await update.message.reply_text(
        f'Привет, {user_first_name}! Я помогу тебе с генерацией фида.\n'
        'Пришли Excel-файл с каталогом или используй /getfeed для получения публичной ссылки.',
        reply_markup=get_main_menu()
    )

async def fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_admin = update.effective_user.id in ADMIN_IDS
    logging.info(f"[START] fallback_handler от user_id={update.effective_user.id}")
    await update.message.reply_text(
        'Я могу принять Excel-файл с каталогом или сгенерировать фид по команде /getfeed.\n'
        'Для справки — /help.',
        reply_markup=get_main_menu()
    ) 
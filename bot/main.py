import logging
# Отключаем подробные логи httpx и других сторонних библиотек
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiobotocore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv
import os
from functools import partial
from s3_async_client import S3Client
from bot.handlers import start, handle_document, getfeed, getallfeed, help_command, greeting_handler, fallback_handler, menu_handler, inline_menu_callback, GREETINGS


def run_bot(feed_url=None):
    load_dotenv()
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    SAVE_DIR = 'uploads'
    os.makedirs(SAVE_DIR, exist_ok=True)
    logging.basicConfig(level=logging.INFO)

    S3_ENDPOINT = os.getenv('S3_ENDPOINT')
    S3_ACCESS_KEY = os.getenv('S3_ACCESS_KEY')
    S3_SECRET_KEY = os.getenv('S3_SECRET_KEY')
    S3_BUCKET = os.getenv('S3_BUCKET')
    S3_BASE = S3_ENDPOINT.replace('https://', '').replace('http://', '')
    S3_PUBLIC_ENDPOINT = os.getenv('S3_PUBLIC_ENDPOINT')
    s3_client = S3Client(S3_ACCESS_KEY, S3_SECRET_KEY, S3_BASE, S3_BUCKET, S3_PUBLIC_ENDPOINT)

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('getfeed', partial(getfeed, s3_client=s3_client)))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('getallfeed', partial(getallfeed, s3_client=s3_client)))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r'(?i)(' + '|'.join(GREETINGS) + ')'),
        greeting_handler
    ))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT, fallback_handler))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^меню$'), menu_handler))
    app.add_handler(CallbackQueryHandler(partial(inline_menu_callback, s3_client=s3_client)))
    app.run_polling() 
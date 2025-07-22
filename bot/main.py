import os
import logging
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters
)
from dotenv import load_dotenv

from bot.handlers import (
    start,
    menu_handler,
    handle_document,
    validate_file,
    getfeed,
    getallfeed,
    help_command,
    error_handler
)

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def run_bot():
    """Запускает бота."""
    # Получаем токен из переменных окружения
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        raise ValueError("Не задан токен бота (BOT_TOKEN)")

    # Создаем приложение
    application = Application.builder().token(bot_token).build()

    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("getfeed", getfeed))
    application.add_handler(CommandHandler("getallfeed", getallfeed))

    # Добавляем обработчики сообщений
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler))

    # Добавляем обработчик ошибок
    application.add_error_handler(error_handler)

    logger.info("Бот запущен")
    
    # Запускаем бота
    application.run_polling() 
import os
import logging
import sys
import tempfile
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler
)
from dotenv import load_dotenv

from .handlers import (
    start,
    menu_handler,
    menu_action_handler,
    handle_document,
    getfeed,
    getallfeed,
    help_command,
    error_handler,
    handle_object_type_selection,
    handle_file_action,
    show_user_files,
    handle_feed_selection,
    handle_template_action,
    handle_docs_action,
    handle_section_view
)

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

logger = logging.getLogger(__name__)

def check_single_instance():
    """Проверяет, что запущен только один экземпляр бота."""
    lock_file = os.path.join(tempfile.gettempdir(), 'catalog_bot.lock')
    
    try:
        # Пытаемся создать или открыть файл блокировки
        if os.path.exists(lock_file):
            # Проверяем, активен ли процесс из файла блокировки
            with open(lock_file, 'r') as f:
                old_pid = int(f.read().strip())
            try:
                # Проверяем существование процесса
                os.kill(old_pid, 0)
                logger.error(f"Бот уже запущен (PID: {old_pid})")
                return False
            except OSError:
                # Процесс не существует, можно перезаписать файл
                pass
        
        # Записываем текущий PID
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при проверке единственного экземпляра: {e}")
        return False

def cleanup_lock():
    """Удаляет файл блокировки при завершении работы."""
    try:
        lock_file = os.path.join(tempfile.gettempdir(), 'catalog_bot.lock')
        if os.path.exists(lock_file):
            os.remove(lock_file)
    except Exception as e:
        logger.error(f"Ошибка при удалении файла блокировки: {e}")

def main():
    """Запускает бота."""
    if not check_single_instance():
        sys.exit(1)
    
    logger.info("Инициализация бота...")
    
    try:
        # Проверяем наличие токена
        bot_token = os.getenv('BOT_TOKEN')
        if not bot_token:
            logger.error("Не задан токен бота (BOT_TOKEN)")
            return

        # Создаем приложение
        application = Application.builder().token(bot_token).build()
        logger.info("Приложение создано успешно")

        # Добавляем обработчики команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        
        # Обработчик базовых кнопок меню
        application.add_handler(MessageHandler(
            filters.Regex("^(🏠 Главное меню|❓ Помощь|📚 Шаблоны/Инструкции|🤟 Админ-панель)$"),
            menu_handler
        ))
        
        # Обработчики для работы с файлами
        application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
        
        # Обработчики callback-запросов
        application.add_handler(CallbackQueryHandler(menu_action_handler, pattern="^menu_"))
        application.add_handler(CallbackQueryHandler(handle_object_type_selection, pattern="^type_"))
        application.add_handler(CallbackQueryHandler(handle_file_action, pattern="^(file|update|delete|confirm|back)_"))
        application.add_handler(CallbackQueryHandler(handle_feed_selection, pattern="^feed_"))
        application.add_handler(CallbackQueryHandler(getallfeed, pattern="^admin_"))
        application.add_handler(CallbackQueryHandler(handle_template_action, pattern="^template_"))
        application.add_handler(CallbackQueryHandler(handle_docs_action, pattern="^docs_"))
        application.add_handler(CallbackQueryHandler(handle_section_view, pattern="^section_"))
        
        # Обработчик ошибок
        application.add_error_handler(error_handler)

        logger.info("Все обработчики зарегистрированы")
        logger.info("Запускаем бота...")

        # Регистрируем очистку при завершении
        import atexit
        atexit.register(cleanup_lock)

        # Запускаем бота
        application.run_polling()
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        cleanup_lock()
        raise

if __name__ == '__main__':
    main() 
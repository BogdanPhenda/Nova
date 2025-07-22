# Catalog Bot

Сервис для автоматизации создания и публикации каталогов недвижимости в формате XML-фида.

## Возможности

- Загрузка данных из Excel файлов
- Автоматическая валидация данных
- Поддержка иерархической структуры (ЖК → Корпус → Объект)
- Синхронизация с Google Sheets
- Генерация XML-фида
- Загрузка фидов в S3 хранилище
- Асинхронная обработка файлов

## Требования

- Python 3.8+
- Google Sheets API credentials
- AWS S3 credentials
- Доступ к Google Spreadsheets

## Установка

1. Клонируйте репозиторий:
```bash
git clone <your-repository-url>
cd catalog-bot2
```

2. Создайте и активируйте виртуальное окружение:
```bash
python -m venv venv
# Для Windows
venv\Scripts\activate
# Для Unix/MacOS
source venv/bin/activate
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Настройте конфигурацию:
   - Создайте `google-credentials.json` с вашими учетными данными Google API
   - Настройте переменные окружения:
     ```
     AWS_ACCESS_KEY_ID=your_access_key
     AWS_SECRET_ACCESS_KEY=your_secret_key
     AWS_DEFAULT_REGION=your_region
     SPREADSHEET_ID=your_spreadsheet_id
     ```

## Структура проекта

```
catalog-bot2/
├── bot/            # Основная логика бота
├── feed/           # Генерация XML фидов
├── google_sheets/  # Интеграция с Google Sheets
├── models/         # Модели данных и валидаторы
├── templates/      # Шаблоны и примеры
├── uploads/        # Временное хранилище файлов
└── s3_async_client.py  # Асинхронный клиент S3
```

## Использование

### Подготовка данных

1. Используйте шаблон Excel из директории `templates/`
2. Заполните все обязательные поля:
   - `internal_id` - Уникальный идентификатор объекта
   - `address` - Полный адрес
   - `price` - Цена объекта
   - `area_total` - Общая площадь

### Загрузка данных

1. Поместите Excel файл в директорию `uploads/`
2. Запустите обработку:
```bash
python main.py
```

### Структура данных

Система поддерживает иерархическую структуру данных:

```
ЖК
└── Корпус 1
    ├── Квартира 101
    ├── Квартира 102
└── Корпус 2
    ├── Квартира 201
    └── Квартира 202
```

## Валидация данных

Система автоматически проверяет:
1. Наличие обязательных полей
2. Корректность типов данных
3. Валидность цен и площадей
4. Корректность этажности
5. Доступность изображений

## API Endpoints

- `GET /health` - Проверка работоспособности сервиса
- `POST /generate-feed` - Запуск генерации фида
- `GET /feeds` - Получение списка доступных фидов

## Разработка

1. Установите зависимости для разработки:
```bash
pip install -r requirements-dev.txt
```

2. Запустите тесты:
```bash
pytest
```

## Рекомендации по использованию

1. Всегда используйте шаблон Excel для подготовки данных
2. Проверяйте данные перед загрузкой
3. Следите за уникальностью идентификаторов
4. Используйте осмысленные названия для корпусов
5. Добавляйте качественные изображения

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 
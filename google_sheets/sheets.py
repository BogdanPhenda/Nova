import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
import logging
from typing import Optional, List, Dict, Tuple
from models.validators import ExcelValidator
from models.data_processor import DataProcessor
from datetime import datetime

logger = logging.getLogger(__name__)

class GoogleSheetsClient:
    """Клиент для работы с Google Sheets."""
    
    BATCH_SIZE = 1000  # Максимальное количество строк для одного batch-обновления
    SERVICE_COLUMNS = [
        'developer_telegram_id',  # ID пользователя
        'source_file_id',        # ID файла-источника
        'creation_date',         # Дата создания записи
        'last_update_date'       # Дата последнего обновления
    ]
    
    def __init__(self, credentials_path: str):
        self.credentials_path = credentials_path
        self.validator = ExcelValidator()
        self.processor = DataProcessor()

    def get_sheet_client(self, sheet_name: str) -> Optional[gspread.Worksheet]:
        """Получает клиент для работы с конкретным листом."""
        try:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = Credentials.from_service_account_file(self.credentials_path, scopes=scopes)
            client = gspread.authorize(creds)
            spreadsheet = client.open(sheet_name)
            return spreadsheet.sheet1
        except Exception as e:
            logger.error(f"Ошибка при подключении к Google Sheets: {e}")
            return None

    def _clean_worksheet(self, worksheet: gspread.Worksheet) -> None:
        """Очищает таблицу и создает новые заголовки."""
        try:
            worksheet.clear()
            logger.info("Таблица очищена")
        except Exception as e:
            logger.error(f"Ошибка при очистке таблицы: {e}")
            raise

    def _get_or_create_headers(self, worksheet: gspread.Worksheet, df_columns: List[str]) -> List[str]:
        """Получает существующие или создает новые заголовки."""
        try:
            # Получаем текущие заголовки
            current_headers = worksheet.row_values(1)
            
            if not current_headers:
                # Если таблица пустая, создаем заголовки
                headers = self.SERVICE_COLUMNS + [col for col in df_columns if col not in self.SERVICE_COLUMNS]
                worksheet.append_row(headers)
                return headers
            
            # Проверяем наличие служебных столбцов
            service_cols_present = all(col in current_headers for col in self.SERVICE_COLUMNS)
            
            if not service_cols_present:
                # Если служебных столбцов нет, добавляем их в начало
                new_headers = self.SERVICE_COLUMNS + [col for col in current_headers if col not in self.SERVICE_COLUMNS]
                # Очищаем таблицу и создаем новые заголовки
                self._clean_worksheet(worksheet)
                worksheet.append_row(new_headers)
                return new_headers
                
            return current_headers
            
        except Exception as e:
            logger.error(f"Ошибка при работе с заголовками: {e}")
            raise

    def check_and_fix_data(self, worksheet: gspread.Worksheet) -> bool:
        """Проверяет и исправляет данные в таблице."""
        try:
            # Получаем все данные
            all_data = worksheet.get_all_values()
            if not all_data:
                logger.info("Таблица пуста")
                return True

            headers = all_data[0]
            if not headers:
                logger.info("Нет заголовков")
                return True

            # Проверяем наличие дубликатов в заголовках
            if len(headers) != len(set(headers)):
                logger.warning("Найдены дубликаты в заголовках")
                # Очищаем таблицу
                self._clean_worksheet(worksheet)
                return True

            # Проверяем служебные столбцы
            if not all(col in headers for col in self.SERVICE_COLUMNS):
                logger.warning("Отсутствуют служебные столбцы")
                # Очищаем таблицу
                self._clean_worksheet(worksheet)
                return True

            # Проверяем данные на корректность
            for row_idx, row in enumerate(all_data[1:], start=2):
                try:
                    # Проверяем, что все значения можно преобразовать в строку
                    processed_row = [self.processor.safe_str(val) for val in row]
                    # Если строка изменилась, обновляем её
                    if processed_row != row:
                        worksheet.update(f'A{row_idx}:{chr(65 + len(row) - 1)}{row_idx}', [processed_row])
                except Exception as e:
                    logger.error(f"Ошибка в строке {row_idx}: {e}")
                    continue

            return True

        except Exception as e:
            logger.error(f"Ошибка при проверке данных: {e}")
            return False

    def _delete_rows_batch(self, worksheet: gspread.Worksheet, rows_to_delete: set) -> None:
        """Удаляет строки батчами для соблюдения ограничений API."""
        if not rows_to_delete:
            return

        # Сортируем строки в обратном порядке (чтобы индексы не сдвигались при удалении)
        sorted_rows = sorted(rows_to_delete, reverse=True)
        
        # Размер батча для API (не более 1000 строк за раз)
        BATCH_SIZE = 1000
        
        # Разбиваем на батчи
        for i in range(0, len(sorted_rows), BATCH_SIZE):
            batch = sorted_rows[i:i + BATCH_SIZE]
            try:
                # Создаем batch request
                request_body = {
                    'requests': [
                        {
                            'deleteDimension': {
                                'range': {
                                    'sheetId': worksheet.id,
                                    'dimension': 'ROWS',
                                    'startIndex': row - 1,  # API использует 0-based индексы
                                    'endIndex': row  # endIndex не включается в диапазон
                                }
                            }
                        }
                        for row in batch
                    ]
                }
                
                # Выполняем batch request
                worksheet.spreadsheet.batch_update(request_body)
                logger.info(f"Удален батч из {len(batch)} строк")
                
            except Exception as e:
                logger.error(f"Ошибка при удалении батча строк: {e}")
                # Если batch request не сработал, пробуем удалять по одной строке
                for row in batch:
                    try:
                        worksheet.delete_rows(row)
                        logger.debug(f"Удалена строка {row}")
                    except Exception as e2:
                        logger.error(f"Ошибка при удалении строки {row}: {e2}")
                        continue

    def _remove_duplicates(self, worksheet: gspread.Worksheet, header: List[str]) -> None:
        """Удаляет дубликаты записей на основе developer_telegram_id и internal_id."""
        try:
            # Получаем все данные
            all_values = worksheet.get_all_values()
            if len(all_values) <= 1:  # Только заголовки или пустая таблица
                return

            # Находим индексы ключевых столбцов
            try:
                dev_id_col = header.index('developer_telegram_id')
                internal_id_col = header.index('internal_id')
            except ValueError as e:
                logger.error(f"Не найден обязательный столбец: {e}")
                return

            # Создаем словарь для отслеживания уникальных записей
            # Ключ: (developer_id, internal_id), Значение: [индексы строк]
            unique_records = {}
            
            # Пропускаем заголовок (строка 1)
            for idx, row in enumerate(all_values[1:], start=2):
                try:
                    if len(row) <= max(dev_id_col, internal_id_col):
                        continue
                    
                    key = (row[dev_id_col], row[internal_id_col])
                    if key in unique_records:
                        unique_records[key].append(idx)
                    else:
                        unique_records[key] = [idx]
                except IndexError:
                    continue

            # Собираем строки для удаления (оставляем только первое вхождение)
            rows_to_delete = set()
            for indices in unique_records.values():
                if len(indices) > 1:  # Если есть дубликаты
                    # Оставляем первую запись, остальные удаляем
                    rows_to_delete.update(indices[1:])

            if rows_to_delete:
                logger.info(f"Найдено {len(rows_to_delete)} дублирующихся записей")
                self._delete_rows_batch(worksheet, rows_to_delete)
                logger.info("Дубликаты удалены")

        except Exception as e:
            logger.error(f"Ошибка при удалении дубликатов: {e}")

    def update_sheet_with_excel(self, worksheet: gspread.Worksheet, 
                              excel_path: str, 
                              developer_id: str,
                              file_id: str) -> Tuple[int, List[str]]:
        """Обновляет Google Sheet данными из Excel файла."""
        try:
            logger.info("=== [START] update_sheet_with_excel ===")

            # Если excel_path is None, это означает удаление данных
            if excel_path is None:
                try:
                    # Получаем заголовки
                    header = worksheet.row_values(1)
                    if not header:
                        return 0, []  # Таблица пуста

                    # Получаем все данные
                    all_values = worksheet.get_all_values()
                    if not all_values:
                        return 0, []  # Таблица уже пуста

                    # Находим индексы нужных столбцов
                    try:
                        dev_id_col = header.index('developer_telegram_id')
                        source_file_col = header.index('source_file_id')
                    except ValueError as e:
                        return 0, [f"Не найден обязательный столбец: {e}"]

                    # Собираем строки для удаления
                    rows_to_delete = set()
                    for idx, row in enumerate(all_values[1:], start=2):
                        try:
                            if len(row) <= max(dev_id_col, source_file_col):
                                continue
                                
                            current_dev_id = row[dev_id_col]
                            current_file_id = row[source_file_col]
                            
                            # Помечаем на удаление все записи этого файла
                            if current_dev_id == str(developer_id) and current_file_id == file_id:
                                rows_to_delete.add(idx)
                        except IndexError:
                            continue

                    # Удаляем записи
                    if rows_to_delete:
                        logger.info(f"Удаляем {len(rows_to_delete)} записей для file_id: {file_id}")
                        self._delete_rows_batch(worksheet, rows_to_delete)
                        return len(rows_to_delete), []
                    return 0, []

                except Exception as e:
                    error_msg = f"Ошибка при удалении данных: {e}"
                    logger.error(error_msg)
                    return 0, [error_msg]

            # Если есть excel_path, обрабатываем файл как обычно
            df = pd.read_excel(excel_path)
            
            # Валидируем данные до их обработки
            is_valid, messages = self.validator.validate_dataframe(df)
            if not is_valid:
                logger.error("Ошибки валидации: %s", messages)
                return 0, messages

            # Нормализуем данные из Excel
            df = self.processor.normalize_dataframe(df, developer_id)
            
            # Получаем или создаем заголовки с учетом столбцов из DataFrame
            try:
                header = self._get_or_create_headers(worksheet, df.columns.tolist())
            except Exception as e:
                return 0, [f"Ошибка при работе с заголовками: {e}"]
            
            # Добавляем информацию о файле-источнике и времени обновления
            now = datetime.now().isoformat()
            df['source_file_id'] = file_id
            df['last_update_date'] = now
            df['creation_date'] = now  # для новых записей
            df['developer_telegram_id'] = developer_id

            try:
                # Получаем все данные
                all_values = worksheet.get_all_values()
                if not all_values:
                    # Если таблица пустая, просто добавляем все записи
                    worksheet.append_row(header)
                    all_values = [header]

                # Находим индексы нужных столбцов
                try:
                    dev_id_col = header.index('developer_telegram_id')
                    source_file_col = header.index('source_file_id')
                except ValueError as e:
                    return 0, [f"Не найден обязательный столбец: {e}"]

                # Собираем строки для удаления (все записи с текущим file_id)
                rows_to_delete = set()
                for idx, row in enumerate(all_values[1:], start=2):
                    try:
                        if len(row) <= max(dev_id_col, source_file_col):
                            continue
                            
                        current_dev_id = row[dev_id_col]
                        current_file_id = row[source_file_col]
                        
                        # Помечаем на удаление все записи этого файла
                        if current_dev_id == str(developer_id) and current_file_id == file_id:
                            rows_to_delete.add(idx)
                    except IndexError:
                        continue

                # Удаляем старые записи этого файла
                if rows_to_delete:
                    logger.info(f"Удаляем {len(rows_to_delete)} старых записей для file_id: {file_id}")
                    self._delete_rows_batch(worksheet, rows_to_delete)

                # Подготавливаем новые данные
                new_rows = []
                for _, row in df.iterrows():
                    new_row = []
                    for col in header:
                        value = row.get(col, '')
                        new_row.append(str(value))
                    new_rows.append(new_row)

                # Добавляем новые данные батчами
                total_rows = 0
                for i in range(0, len(new_rows), self.BATCH_SIZE):
                    batch = new_rows[i:i + self.BATCH_SIZE]
                    worksheet.append_rows(batch)
                    total_rows += len(batch)
                    logger.info(f"Добавлено {len(batch)} строк")

                logger.info(f"=== [END] update_sheet_with_excel: добавлено {total_rows} строк ===")
                return total_rows, []

            except Exception as e:
                error_msg = f"Ошибка при обновлении данных: {e}"
                logger.error(error_msg)
                return 0, [error_msg]

        except Exception as e:
            error_msg = f"Общая ошибка при обновлении таблицы: {e}"
            logger.error(error_msg)
            return 0, [error_msg]

    def get_developer_data(self, worksheet: gspread.Worksheet, developer_id: str = None, file_id: str = None) -> List[Dict]:
        """Получает данные определенного застройщика или все данные."""
        try:
            # Получаем заголовки
            headers = worksheet.row_values(1)
            if not headers:
                return []
                
            # Получаем все записи
            records = worksheet.get_all_records(expected_headers=headers)
            
            # Фильтруем по developer_id и file_id
            filtered_records = records
            if developer_id:
                filtered_records = [
                    record for record in filtered_records 
                    if self.processor.safe_str(record.get('developer_telegram_id')) == str(developer_id)
                ]
            if file_id:
                filtered_records = [
                    record for record in filtered_records
                    if self.processor.safe_str(record.get('source_file_id')) == str(file_id)
                ]
            return filtered_records
            
        except Exception as e:
            logger.error(f"Ошибка при получении данных: {e}")
            return [] 
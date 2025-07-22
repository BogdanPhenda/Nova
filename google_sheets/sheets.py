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
    SERVICE_COLUMNS = ['developer_telegram_id', 'creation_date']
    
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

        # Группируем последовательные строки для batch-удаления
        sorted_rows = sorted(rows_to_delete, reverse=True)  # Сортируем в обратном порядке
        batches = []
        current_batch = []
        
        for row in sorted_rows:
            if not current_batch:
                current_batch.append(row)
            elif current_batch[-1] == row + 1:  # Если строка последовательная
                current_batch.append(row)
            else:
                batches.append(current_batch)
                current_batch = [row]
        
        if current_batch:
            batches.append(current_batch)

        # Удаляем каждый батч как диапазон строк
        for batch in batches:
            try:
                start_index = min(batch)
                end_index = max(batch)
                worksheet.delete_rows(start_index, end_index)
                logger.debug(f"Удален диапазон строк {start_index}-{end_index}")
            except Exception as e:
                logger.error(f"Ошибка при удалении батча строк {start_index}-{end_index}: {e}")

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
                              developer_id: str) -> Tuple[int, List[str]]:
        """Обновляет Google Sheet данными из Excel файла."""
        try:
            logger.info("=== [START] update_sheet_with_excel ===")

            # Читаем Excel файл
            df = pd.read_excel(excel_path)
            
            # Валидируем данные до их обработки
            is_valid, messages = self.validator.validate_dataframe(df)
            if not is_valid:
                logger.error("Ошибки валидации: %s", messages)
                return 0, messages

            # Получаем или создаем заголовки
            try:
                header = self._get_or_create_headers(worksheet, df.columns.tolist())
            except Exception as e:
                return 0, [f"Ошибка при работе с заголовками: {e}"]

            # Сначала удаляем дубликаты из таблицы
            self._remove_duplicates(worksheet, header)

            # Нормализуем данные из Excel и получаем список internal_id
            df = self.processor.normalize_dataframe(df, developer_id)
            new_internal_ids = set(df['internal_id'].astype(str))
            
            try:
                # Получаем все данные (после удаления дубликатов)
                all_values = worksheet.get_all_values()
                if not all_values:
                    # Если таблица пустая, просто добавляем все записи
                    worksheet.append_row(header)
                    all_values = [header]

                # Находим индексы нужных столбцов
                try:
                    dev_id_col = header.index('developer_telegram_id')
                    internal_id_col = header.index('internal_id')
                except ValueError as e:
                    return 0, [f"Не найден обязательный столбец: {e}"]

                # Собираем информацию о всех записях текущего застройщика
                developer_records = {}  # internal_id -> row_index
                for idx, row in enumerate(all_values[1:], start=2):  # start=2, пропускаем заголовки
                    try:
                        if len(row) <= max(dev_id_col, internal_id_col):
                            logger.warning(f"Пропущена короткая строка {idx}: {row}")
                            continue
                            
                        current_dev_id = row[dev_id_col]
                        current_internal_id = row[internal_id_col]
                        
                        if current_dev_id == str(developer_id):
                            developer_records[current_internal_id] = idx
                    except IndexError:
                        logger.warning(f"Пропущена некорректная строка {idx}: {row}")
                        continue

                # Определяем строки для удаления
                rows_to_delete = set()

                # 1. Строки для обновления (internal_id есть и в таблице, и в новом файле)
                rows_to_update = {
                    idx for internal_id, idx in developer_records.items()
                    if internal_id in new_internal_ids
                }
                rows_to_delete.update(rows_to_update)
                
                # 2. Строки для удаления (internal_id есть в таблице, но нет в новом файле)
                rows_to_remove = {
                    idx for internal_id, idx in developer_records.items()
                    if internal_id not in new_internal_ids
                }
                rows_to_delete.update(rows_to_remove)

                # Удаляем строки батчами
                if rows_to_delete:
                    logger.info(f"Всего найдено {len(rows_to_delete)} записей для обработки:")
                    logger.info(f"- {len(rows_to_update)} записей для обновления")
                    logger.info(f"- {len(rows_to_remove)} записей для удаления")
                    
                    # Используем batch-удаление
                    self._delete_rows_batch(worksheet, rows_to_delete)

                # Подготавливаем новые записи
                new_rows = []
                for _, row in df.iterrows():
                    try:
                        row_values = [self.processor.safe_str(row.get(col, '')) for col in header]
                        new_rows.append(row_values)
                    except Exception as e:
                        logger.error(f"Ошибка при подготовке строки: {e}")
                        continue

                # Добавляем новые записи батчами
                if new_rows:
                    total_added = 0
                    for i in range(0, len(new_rows), self.BATCH_SIZE):
                        batch = new_rows[i:i + self.BATCH_SIZE]
                        try:
                            worksheet.append_rows(batch)
                            total_added += len(batch)
                        except Exception as e:
                            logger.error(f"Ошибка при добавлении батча записей: {e}")
                            continue
                    
                    logger.info(f"Итоги обработки:")
                    logger.info(f"- Обновлено существующих записей: {len(rows_to_update)}")
                    logger.info(f"- Удалено устаревших записей: {len(rows_to_remove)}")
                    logger.info(f"- Добавлено новых записей: {total_added}")
                    return total_added, []
                else:
                    return 0, ["Нет данных для добавления"]

            except Exception as e:
                error_msg = f"Ошибка при обновлении данных: {e}"
                logger.error(error_msg)
                return 0, [error_msg]
            
        except Exception as e:
            error_msg = f"[ERROR] update_sheet_with_excel: {e}"
            logger.error(error_msg)
            return 0, [error_msg]

    def get_developer_data(self, worksheet: gspread.Worksheet, developer_id: str = None) -> List[Dict]:
        """Получает данные определенного застройщика или все данные."""
        try:
            # Получаем заголовки
            headers = worksheet.row_values(1)
            if not headers:
                return []
                
            # Получаем все записи
            records = worksheet.get_all_records(expected_headers=headers)
            
            # Фильтруем по developer_id, если указан
            if developer_id:
                return [
                    record for record in records 
                    if self.processor.safe_str(record.get('developer_telegram_id')) == str(developer_id)
                ]
            return records
            
        except Exception as e:
            logger.error(f"Ошибка при получении данных: {e}")
            return [] 
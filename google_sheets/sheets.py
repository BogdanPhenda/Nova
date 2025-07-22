import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
import logging
import os

logger = logging.getLogger(__name__)

EXPECTED_COLUMNS = [
    'developer_telegram_id', 'internal_id', 'property_type', 'category',
    'creation_date', 'address', 'price', 'currency', 'area_total',
    'area_living', 'area_kitchen', 'windows_view', 'number', 'price_sale',
    'description', 'floor', 'floors_total', 'building_name', 'built_year',
    'image_urls'
]

def get_sheet_client(credentials_path, sheet_name):
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
        client = gspread.authorize(creds)
        spreadsheet = client.open(sheet_name)
        worksheet = spreadsheet.sheet1
        return worksheet
    except Exception as e:
        logger.error(f"Ошибка при подключении к Google Sheets: {e}")
        return None

def update_sheet_with_excel(worksheet, excel_path, developer_id):
    try:
        logger.info("=== [START] update_sheet_with_excel ===")
        df = pd.read_excel(excel_path)
        df['developer_telegram_id'] = developer_id
        df = df.reindex(columns=EXPECTED_COLUMNS)
        header = worksheet.row_values(1)
        if not header:
            worksheet.update([EXPECTED_COLUMNS], 'A1')
        # --- Новая логика: удаление только строк с совпадающими developer_id и internal_id ---
        all_records = worksheet.get_all_records()
        rows_to_delete = []
        # Собираем set из internal_id новых данных
        new_internal_ids = set(str(x) for x in df['internal_id'].dropna().astype(str))
        logger.info(f"Будут обновлены объекты с internal_id: {new_internal_ids}")
        for idx, rec in enumerate(all_records, start=2):  # start=2, т.к. первая строка — заголовок
            if str(rec.get('developer_telegram_id')) == str(developer_id) and str(rec.get('internal_id')) in new_internal_ids:
                rows_to_delete.append(idx)
        logger.info(f"Найдено {len(rows_to_delete)} строк для удаления (по developer_id и internal_id)")
        for row_idx in sorted(rows_to_delete, reverse=True):
            worksheet.delete_rows(row_idx)
        logger.info(f"Удалено {len(rows_to_delete)} строк из Google Таблицы.")
        # --- Конец новой логики ---
        data_to_append = df.fillna('').values.tolist()
        worksheet.append_rows(data_to_append)
        logger.info(f"Добавлено {len(data_to_append)} строк в Google Таблицу.")
        logger.info("=== [END] update_sheet_with_excel ===")
        return len(data_to_append)
    except Exception as e:
        logger.error(f"[ERROR] update_sheet_with_excel: {e}")
        return 0 
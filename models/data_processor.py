import pandas as pd
from datetime import datetime
from typing import Dict, Any, Tuple, List, Union
import numpy as np

class DataProcessor:
    """Класс для обработки и нормализации данных перед работой с Google Sheets."""

    @staticmethod
    def safe_str(value: Any) -> str:
        """Безопасное преобразование любого значения в строку."""
        if pd.isna(value) or value is None:
            return ''
        if isinstance(value, bool):
            return str(int(value))  # True -> '1', False -> '0'
        if isinstance(value, (int, float)):
            if isinstance(value, float) and np.isnan(value):
                return ''
            if float(value).is_integer():
                return str(int(value))
            return str(float(value))
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value).strip()

    @staticmethod
    def normalize_dataframe(df: pd.DataFrame, developer_id: str) -> pd.DataFrame:
        """Нормализует DataFrame для работы с Google Sheets."""
        # Создаем копию DataFrame
        normalized_df = df.copy()
        
        # Преобразуем все значения в строки до добавления новых столбцов
        for column in normalized_df.columns:
            normalized_df[column] = normalized_df[column].astype(str).apply(lambda x: DataProcessor.safe_str(x))
        
        # Добавляем служебные поля (уже как строки)
        normalized_df.insert(0, 'developer_telegram_id', str(developer_id))
        normalized_df.insert(1, 'creation_date', datetime.now().isoformat())
        
        return normalized_df

    @staticmethod
    def prepare_row_values(values: Union[Dict[str, Any], pd.Series], header: List[str]) -> List[str]:
        """Подготавливает список значений в соответствии с заголовками."""
        result = []
        for col in header:
            if isinstance(values, dict):
                val = values.get(col, '')
            else:
                val = values[col] if col in values.index else ''
            result.append(DataProcessor.safe_str(val))
        return result

    @staticmethod
    def prepare_for_batch_update(rows: List[Union[Dict[str, Any], pd.Series]], 
                               header: List[str], 
                               start_row: int) -> Dict[str, List[str]]:
        """Подготавливает данные для пакетного обновления."""
        updates = {}
        for idx, row in enumerate(rows, start=start_row):
            range_name = f'A{idx}:{chr(65 + len(header) - 1)}{idx}'
            values = DataProcessor.prepare_row_values(row, header)
            updates[range_name] = values
        return updates

    @staticmethod
    def convert_to_string_dict(data: Union[Dict[str, Any], pd.Series]) -> Dict[str, str]:
        """Преобразует словарь или Series в словарь со строковыми значениями."""
        if isinstance(data, pd.Series):
            data = data.to_dict()
        return {str(k): DataProcessor.safe_str(v) for k, v in data.items()} 
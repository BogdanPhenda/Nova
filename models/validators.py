from typing import List, Dict, Any, Tuple
import pandas as pd
from models.real_estate import (
    ResidentialComplex, Building, Property, Location, Price, Area, Image,
    RenovationType, ParkingType, ConstructionType
)
import logging
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class ExcelValidator:
    """Валидатор для Excel файлов с данными о недвижимости."""
    
    REQUIRED_COLUMNS = {
        'internal_id': str,
        'address': str,
        'price': float,
        'area_total': float,
    }
    
    OPTIONAL_COLUMNS = {
        'property_type': str,
        'category': str,
        'area_living': float,
        'area_kitchen': float,
        'windows_view': str,
        'number': str,
        'description': str,
        'floor': int,
        'floors_total': int,
        'building_name': str,
        'built_year': int,
        'image_urls': str,
        'ceiling_height': float,
        'renovation_type': str,
        'balcony_type': str,
        'has_parking': bool,
        'rooms': int,
        'metro_station': str,
        'distance_to_metro': int,
        'mortgage_available': bool,
        'initial_payment': float,
        'construction_type': str,
        'elevator_count': int,
        'developer_name': str,
    }

    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate_dataframe(self, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """Проверяет DataFrame на соответствие требованиям."""
        self.errors = []
        self.warnings = []

        # Базовая валидация
        self._validate_required_fields(df)
        self._validate_data_types(df)
        self._validate_numeric_values(df)
        self._validate_business_rules(df)
        self._validate_hierarchy(df)
        
        return len(self.errors) == 0, self.errors + self.warnings

    def _validate_required_fields(self, df: pd.DataFrame):
        """Проверка обязательных полей."""
        for col in self.REQUIRED_COLUMNS:
            if col not in df.columns:
                self.errors.append(f"Отсутствует обязательная колонка: {col}")
            elif df[col].isnull().any():
                rows = df[df[col].isnull()].index.tolist()
                self.errors.append(f"Пустые значения в обязательной колонке {col} в строках: {rows}")

    def _validate_data_types(self, df: pd.DataFrame):
        """Проверка типов данных."""
        for col, dtype in {**self.REQUIRED_COLUMNS, **self.OPTIONAL_COLUMNS}.items():
            if col in df.columns:
                try:
                    # Пропускаем пустые значения в опциональных полях
                    mask = df[col].notna()
                    if dtype == bool:
                        df.loc[mask, col] = df.loc[mask, col].astype(str).str.lower().isin(['true', '1', 'yes', 'да'])
                    else:
                        df.loc[mask, col] = df.loc[mask, col].astype(dtype)
                except Exception as e:
                    self.errors.append(f"Ошибка в колонке {col}: неверный тип данных, ожидается {dtype}")

    def _validate_numeric_values(self, df: pd.DataFrame):
        """Проверка числовых значений."""
        # Проверка цен
        if 'price' in df.columns:
            if (df['price'] < 0).any():
                self.errors.append("Найдены отрицательные значения в поле 'price'")
            
            # Проверка цены за метр
            if 'area_total' in df.columns:
                price_per_meter = df['price'] / df['area_total']
                if (price_per_meter < 50_000).any():
                    self.warnings.append("Найдены подозрительно низкие цены за квадратный метр")
                if (price_per_meter > 1_000_000).any():
                    self.warnings.append("Найдены подозрительно высокие цены за квадратный метр")

        # Проверка площадей
        for area_col in ['area_total', 'area_living', 'area_kitchen']:
            if area_col in df.columns:
                if (df[area_col] < 0).any():
                    self.errors.append(f"Найдены отрицательные значения в поле '{area_col}'")

        # Проверка соотношения площадей
        if all(col in df.columns for col in ['area_total', 'area_living', 'area_kitchen']):
            mask = df['area_living'].notna() & df['area_kitchen'].notna()
            invalid_areas = df[mask & (df['area_living'] + df['area_kitchen'] > df['area_total'])].index
            if not invalid_areas.empty:
                self.errors.append(f"Сумма жилой площади и кухни больше общей площади в строках: {list(invalid_areas)}")

    def _validate_business_rules(self, df: pd.DataFrame):
        """Проверка бизнес-правил."""
        # Проверка описания для дорогих объектов
        if all(col in df.columns for col in ['price', 'description']):
            expensive_threshold = df['price'].quantile(0.8)
            expensive_no_desc = df[
                (df['price'] > expensive_threshold) & 
                (df['description'].isna() | (df['description'] == ''))
            ].index
            if not expensive_no_desc.empty:
                self.warnings.append(f"Отсутствует описание для дорогих объектов в строках: {list(expensive_no_desc)}")

        # Проверка URL изображений
        if 'image_urls' in df.columns:
            for idx, urls in df['image_urls'].items():
                if pd.notna(urls):
                    for url in urls.split(','):
                        if not url.strip().startswith(('http://', 'https://')):
                            self.warnings.append(f"Некорректный URL изображения в строке {idx}: {url}")

        # Проверка этажности
        if all(col in df.columns for col in ['property_type', 'floor', 'floors_total']):
            invalid_floor = df[
                (df['property_type'] == 'квартира') & 
                (df['floor'] > df['floors_total'])
            ].index
            if not invalid_floor.empty:
                self.errors.append(f"Этаж больше общего количества этажей в строках: {list(invalid_floor)}")

        # Проверка заполненности рекомендуемых полей
        recommended_fields = ['rooms', 'renovation_type', 'windows_view']
        for field in recommended_fields:
            if field in df.columns:
                empty_fields = df[df[field].isna()].index
                if not empty_fields.empty:
                    self.warnings.append(f"Рекомендуется заполнить поле {field} в строках: {list(empty_fields)}")

    def _validate_hierarchy(self, df: pd.DataFrame):
        """Проверка иерархии и связности данных."""
        # Проверка уникальности ID
        if df['internal_id'].duplicated().any():
            duplicate_ids = df[df['internal_id'].duplicated()]['internal_id'].tolist()
            self.errors.append(f"Найдены дубликаты internal_id: {duplicate_ids}")

        # Проверка базовой структуры данных по корпусам
        if 'building_name' in df.columns:
            buildings = df['building_name'].unique()
            for building in buildings:
                building_data = df[df['building_name'] == building]
                
                # Проверяем только критически важные параметры
                if building_data.empty:
                    self.errors.append(f"Нет данных для корпуса {building}")
                elif not building_data['internal_id'].is_unique:
                    self.errors.append(f"Найдены дубликаты internal_id в корпусе {building}")

                # Добавляем предупреждения о возможных проблемах
                if building_data['address'].nunique() > 1:
                    self.warnings.append(f"В корпусе {building} используется несколько разных адресов")
                if 'built_year' in df.columns and building_data['built_year'].nunique() > 1:
                    self.warnings.append(f"В корпусе {building} указаны разные года постройки")

    def transform_to_models(self, df: pd.DataFrame, developer_id: str) -> List[ResidentialComplex]:
        """Преобразует DataFrame в модели данных."""
        complexes = {}
        
        for _, row in df.iterrows():
            try:
                # Создаем базовые компоненты
                location = Location(
                    address=row['address'],
                    country="Россия",
                    metro_station=row.get('metro_station'),
                    distance_to_metro=row.get('distance_to_metro')
                )
                
                price = Price(
                    value=float(row['price']),
                    currency="RUB",
                    price_per_meter=float(row['price']) / float(row['area_total']) if 'area_total' in row else None,
                    mortgage_available=row.get('mortgage_available'),
                    initial_payment=row.get('initial_payment')
                )
                
                area = Area(
                    total=float(row['area_total']),
                    living=float(row['area_living']) if 'area_living' in row and pd.notna(row['area_living']) else None,
                    kitchen=float(row['area_kitchen']) if 'area_kitchen' in row and pd.notna(row['area_kitchen']) else None
                )
                
                # Создаем объект недвижимости
                images = []
                if 'image_urls' in row and pd.notna(row['image_urls']):
                    for idx, url in enumerate(str(row['image_urls']).split(',')):
                        images.append(Image(url=url.strip(), sort_order=idx))
                
                property_obj = Property(
                    internal_id=str(row['internal_id']),
                    location=location,
                    price=price,
                    area=area,
                    property_type=row.get('property_type', 'квартира'),
                    floor=int(row['floor']) if 'floor' in row and pd.notna(row['floor']) else None,
                    floors_total=int(row['floors_total']) if 'floors_total' in row and pd.notna(row['floors_total']) else None,
                    apartment_number=str(row['number']) if 'number' in row and pd.notna(row['number']) else None,
                    description=row.get('description'),
                    windows_view=row.get('windows_view'),
                    images=images,
                    rooms=row.get('rooms'),
                    ceiling_height=row.get('ceiling_height'),
                    renovation_type=RenovationType(row['renovation_type']) if pd.notna(row.get('renovation_type')) else None,
                    balcony_type=row.get('balcony_type'),
                    has_parking=row.get('has_parking')
                )
                
                # Определяем корпус
                building_name = row.get('building_name', 'Корпус 1')
                building_id = f"{building_name}_{developer_id}"
                
                if building_id not in complexes:
                    building = Building(
                        id=building_id,
                        name=building_name,
                        complex_id=developer_id,
                        built_year=int(row['built_year']) if 'built_year' in row and pd.notna(row['built_year']) else None,
                        properties=[property_obj],
                        construction_type=ConstructionType(row['construction_type']) if pd.notna(row.get('construction_type')) else None,
                        elevator_count=row.get('elevator_count')
                    )
                    
                    # Создаем или обновляем ЖК
                    if developer_id not in complexes:
                        complexes[developer_id] = ResidentialComplex(
                            id=developer_id,
                            name=f"ЖК от застройщика {developer_id}",
                            developer_id=developer_id,
                            developer_name=row.get('developer_name'),
                            location=location,
                            buildings=[building]
                        )
                    else:
                        complexes[developer_id].buildings.append(building)
                else:
                    # Добавляем объект в существующий корпус
                    for building in complexes[developer_id].buildings:
                        if building.id == building_id:
                            building.properties.append(property_obj)
                            break
            
            except Exception as e:
                logger.error(f"Ошибка при обработке строки {row['internal_id']}: {e}")
                continue
        
        return list(complexes.values()) 
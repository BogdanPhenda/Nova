import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

class TestDataGenerator:
    def __init__(self):
        self.cities = {
            'Москва': {
                'districts': ['Пресненский', 'Хамовники', 'Раменки', 'Очаково-Матвеевское'],
                'metro': ['Киевская', 'Парк Победы', 'Фили', 'Кутузовская', 'Студенческая'],
                'streets': ['Кутузовский проспект', 'Мосфильмовская улица', 'Минская улица', 'Большая Дорогомиловская']
            }
        }
        
        self.developers = [
            {'name': 'СтройИнвест', 'complexes': ['Солнечный', 'Речной']},
            {'name': 'ГрадСтрой', 'complexes': ['Парковый', 'Центральный']},
            {'name': 'МегаСтрой', 'complexes': ['Престиж', 'Комфорт']}
        ]
        
        self.renovation_types = ['без отделки', 'черновая', 'чистовая']
        self.balcony_types = ['нет', 'балкон', 'лоджия', 'два балкона', 'балкон и лоджия']
        self.window_views = ['во двор', 'на улицу', 'на парк', 'во двор и на улицу']
        self.construction_types = ['монолит', 'панель', 'кирпич', 'монолит-кирпич']

    def generate_address(self, city):
        district = random.choice(self.cities[city]['districts'])
        street = random.choice(self.cities[city]['streets'])
        building = random.randint(1, 20)
        return f"г. {city}, {district} район, {street}, д. {building}"

    def generate_price(self, area, is_premium=False):
        base_price = 250000 if is_premium else 180000  # цена за м²
        variation = random.uniform(0.9, 1.1)
        return int(area * base_price * variation)

    def generate_complex_data(self, rows=100):
        data = []
        current_date = datetime.now()

        for developer in self.developers:
            for complex_name in developer['complexes']:
                # Для каждого ЖК создаем 2-3 корпуса
                num_buildings = random.randint(2, 3)
                for building_num in range(1, num_buildings + 1):
                    # В каждом корпусе 15-20 объектов
                    num_objects = random.randint(15, 20)
                    
                    # Общие характеристики корпуса
                    address = self.generate_address('Москва')
                    metro = random.choice(self.cities['Москва']['metro'])
                    distance_to_metro = random.randint(5, 15) * 100
                    construction_type = random.choice(self.construction_types)
                    built_year = random.randint(2024, 2026)
                    floors_total = random.randint(12, 25)
                    elevator_count = random.randint(2, 4)
                    
                    for obj_num in range(1, num_objects + 1):
                        # Генерируем характеристики объекта
                        floor = random.randint(1, floors_total)
                        rooms = random.randint(1, 4)
                        
                        # Площади
                        area_total = 35 + (rooms * random.randint(15, 20))
                        area_living = area_total * 0.6
                        area_kitchen = area_total * 0.15
                        
                        # Генерируем уникальный ID
                        internal_id = f"{complex_name[:3]}_{building_num}_{obj_num:03d}"
                        
                        # Создаем объект
                        obj = {
                            'internal_id': internal_id,
                            'property_type': 'квартира',
                            'category': 'продажа',
                            'address': address,
                            'price': self.generate_price(area_total, complex_name in ['Престиж', 'Центральный']),
                            'currency': 'RUB',
                            'area_total': round(area_total, 1),
                            'area_living': round(area_living, 1),
                            'area_kitchen': round(area_kitchen, 1),
                            'description': f"{'Просторная' if area_total > 60 else 'Уютная'} {rooms}-комнатная квартира в ЖК {complex_name}, корпус {building_num}. {random.choice(['Отличная планировка', 'Функциональная планировка', 'Эргономичная планировка'])}. {random.choice(['Развитая инфраструктура', 'Все необходимое рядом', 'Отличная транспортная доступность'])}.",
                            'floor': floor,
                            'floors_total': floors_total,
                            'building_name': f"Корпус {building_num}",
                            'built_year': built_year,
                            'windows_view': random.choice(self.window_views),
                            'number': f"{floor}{obj_num:02d}",
                            'image_urls': f"https://example.com/{internal_id}_1.jpg,https://example.com/{internal_id}_2.jpg",
                            'rooms': rooms,
                            'ceiling_height': round(random.uniform(2.7, 3.2), 1),
                            'renovation_type': random.choice(self.renovation_types),
                            'balcony_type': random.choice(self.balcony_types),
                            'has_parking': random.choice([True, True, False]),  # 66% вероятность наличия парковки
                            'metro_station': metro,
                            'distance_to_metro': distance_to_metro,
                            'mortgage_available': True,
                            'initial_payment': round(self.generate_price(area_total) * 0.15, -4),  # округляем до десятков тысяч
                            'construction_type': construction_type,
                            'elevator_count': elevator_count,
                            'developer_name': developer['name']
                        }
                        data.append(obj)

        # Если нужно точное количество строк, обрезаем или дополняем
        if len(data) > rows:
            data = data[:rows]
        
        return pd.DataFrame(data)

    def save_to_excel(self, filename='test_catalog.xlsx'):
        df = self.generate_complex_data()
        
        # Сохраняем в Excel с форматированием
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Каталог')
            worksheet = writer.sheets['Каталог']
            
            # Форматируем ширину колонок
            for column in worksheet.columns:
                max_length = 0
                column = [cell for cell in column]
                try:
                    max_length = max(len(str(cell.value)) for cell in column)
                except:
                    pass
                adjusted_width = (max_length + 2)
                worksheet.column_dimensions[column[0].column_letter].width = adjusted_width

if __name__ == '__main__':
    generator = TestDataGenerator()
    generator.save_to_excel('uploads/test_catalog.xlsx')
    print("Тестовый файл создан: uploads/test_catalog.xlsx") 
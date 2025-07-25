import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

def create_partner_template():
    """
    Генерирует шаблон Excel для партнеров с 100 строками тестовых данных и всеми поддерживаемыми полями.
    price и price_sale идут рядом.
    """
    # Определяем порядок полей
    columns = [
        'internal_id', 'address', 'property_type', 'category',
        'area_total', 'area_living', 'area_kitchen',
        'floor', 'floors_total', 'building_name', 'built_year', 'section',
        'price', 'price_sale', 'currency',
        'description', 'windows_view', 'number', 'rooms',
        'ceiling_height', 'renovation_type', 'balcony_type', 'has_parking',
        'image_urls', 'metro_station', 'distance_to_metro',
        'mortgage_available', 'initial_payment',
        'construction_type', 'elevator_count', 'developer_name'
    ]

    # Создаем данные для каждого корпуса с одинаковыми параметрами
    building_data = {
        'Корпус 1': {
            'address': 'г. Москва, ул. Тестовая, д. 1',
            'built_year': 2024,
            'floors_total': 16,
            'metro_station': 'Проспект Вернадского',
            'distance_to_metro': 800,
            'construction_type': 'монолит-кирпич',
            'elevator_count': 2
        },
        'Корпус 2': {
            'address': 'г. Москва, ул. Тестовая, д. 2',
            'built_year': 2024,
            'floors_total': 20,
            'metro_station': 'Киевская',
            'distance_to_metro': 1200,
            'construction_type': 'монолит',
            'elevator_count': 3
        },
        'Корпус 3': {
            'address': 'г. Москва, ул. Тестовая, д. 3',
            'built_year': 2023,
            'floors_total': 12,
            'metro_station': 'Парк Победы',
            'distance_to_metro': 1500,
            'construction_type': 'панель',
            'elevator_count': 2
        },
        'Корпус 4': {
            'address': 'г. Москва, ул. Тестовая, д. 4',
            'built_year': 2025,
            'floors_total': 25,
            'metro_station': 'Проспект Вернадского',
            'distance_to_metro': 950,
            'construction_type': 'монолит-кирпич',
            'elevator_count': 4
        },
        'Корпус 5': {
            'address': 'г. Москва, ул. Тестовая, д. 5',
            'built_year': 2024,
            'floors_total': 18,
            'metro_station': 'Киевская',
            'distance_to_metro': 1100,
            'construction_type': 'кирпич',
            'elevator_count': 2
        }
    }

    data = []
    for i in range(1, 101):
        # Выбираем корпус
        building_name = f'Корпус {(i-1) % 5 + 1}'
        building_info = building_data[building_name]
        
        # Генерируем данные с учетом ограничений корпуса
        total_area = round(random.uniform(30, 120), 2)
        living_area = round(total_area * random.uniform(0.5, 0.8), 2)
        kitchen_area = round(total_area * random.uniform(0.1, 0.2), 2)
        price = int(total_area * random.uniform(120_000, 250_000))
        price_sale = price - random.randint(100_000, 500_000) if random.random() > 0.2 else ''
        
        # Этаж не может быть больше общего количества этажей
        floor = random.randint(1, building_info['floors_total'])
        
        section = f'Секция {random.randint(1, 4)}'
        currency = 'RUB'
        description = f'Тестовое описание квартиры {i}'
        windows_view = random.choice(['во двор', 'на парк', 'на улицу'])
        number = f'{random.randint(1, 20)}{random.randint(1, 9)}{random.randint(0, 9)}'
        rooms = random.randint(1, 4)
        ceiling_height = round(random.uniform(2.5, 3.2), 2)
        renovation_type = random.choice(['чистовая', 'черновая', 'без отделки'])
        balcony_type = random.choice(['балкон', 'лоджия', 'нет'])
        has_parking = random.choice([True, False])
        image_urls = 'https://example.com/img1.jpg,https://example.com/img2.jpg'
        mortgage_available = random.choice([True, False])
        initial_payment = random.randint(500_000, 3_000_000)
        developer_name = random.choice(['Строй Инвест', 'Город Девелопмент', 'Новый Дом'])
        property_type = 'квартира'
        category = 'продажа'

        row = {
            'internal_id': f'test_{i}',
            'address': building_info['address'],
            'property_type': property_type,
            'category': category,
            'area_total': total_area,
            'area_living': living_area,
            'area_kitchen': kitchen_area,
            'floor': floor,
            'floors_total': building_info['floors_total'],
            'building_name': building_name,
            'built_year': building_info['built_year'],
            'section': section,
            'price': price,
            'price_sale': price_sale,
            'currency': currency,
            'description': description,
            'windows_view': windows_view,
            'number': number,
            'rooms': rooms,
            'ceiling_height': ceiling_height,
            'renovation_type': renovation_type,
            'balcony_type': balcony_type,
            'has_parking': has_parking,
            'image_urls': image_urls,
            'metro_station': building_info['metro_station'],
            'distance_to_metro': building_info['distance_to_metro'],
            'mortgage_available': mortgage_available,
            'initial_payment': initial_payment,
            'construction_type': building_info['construction_type'],
            'elevator_count': building_info['elevator_count'],
            'developer_name': developer_name
        }
        data.append(row)

    df = pd.DataFrame(data, columns=columns)

    with pd.ExcelWriter('templates/partner_template.xlsx', engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Каталог')
        worksheet = writer.sheets['Каталог']
        for column in worksheet.columns:
            max_length = 0
            column = [cell for cell in column]
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2)
            worksheet.column_dimensions[column[0].column_letter].width = adjusted_width

if __name__ == '__main__':
    create_partner_template() 
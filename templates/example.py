import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def create_example_excel():
    """Создает пример Excel файла с данными о недвижимости."""
    
    # Создаем данные для ЖК "Солнечный"
    data = []
    
    # Общие данные о ЖК
    developer_name = "Строй Инвест"
    metro_station = "Проспект Вернадского"
    construction_type = "монолит-кирпич"
    
    # Корпус 1
    for i in range(1, 4):
        data.append({
            'internal_id': f'sun1_{i}',
            'property_type': 'квартира',
            'category': 'продажа',
            'address': 'г. Москва, ул. Солнечная, д. 1',
            'price': 8_500_000 + i * 500_000,
            'currency': 'RUB',
            'area_total': 45 + i * 5,
            'area_living': 30 + i * 3,
            'area_kitchen': 12 + i,
            'description': f'Светлая {i+1}-комнатная квартира с отличным видом',
            'floor': i + 1,
            'floors_total': 12,
            'building_name': 'Корпус 1',
            'built_year': 2024,
            'windows_view': 'во двор',
            'number': f'10{i}',
            'image_urls': 'https://example.com/img1.jpg,https://example.com/img2.jpg',
            'rooms': i + 1,
            'ceiling_height': 2.8,
            'renovation_type': 'чистовая',
            'balcony_type': 'лоджия',
            'has_parking': True,
            'metro_station': metro_station,
            'distance_to_metro': 800,
            'mortgage_available': True,
            'initial_payment': 2_000_000,
            'construction_type': construction_type,
            'elevator_count': 2,
            'developer_name': developer_name
        })
    
    # Корпус 2
    for i in range(1, 3):
        data.append({
            'internal_id': f'sun2_{i}',
            'property_type': 'квартира',
            'category': 'продажа',
            'address': 'г. Москва, ул. Солнечная, д. 2',
            'price': 12_000_000 + i * 1_000_000,
            'currency': 'RUB',
            'area_total': 75 + i * 10,
            'area_living': 55 + i * 7,
            'area_kitchen': 15 + i * 2,
            'description': f'Просторная {i+2}-комнатная квартира с панорамными окнами',
            'floor': i + 5,
            'floors_total': 12,
            'building_name': 'Корпус 2',
            'built_year': 2024,
            'windows_view': 'на парк',
            'number': f'20{i}',
            'image_urls': 'https://example.com/img3.jpg,https://example.com/img4.jpg',
            'rooms': i + 2,
            'ceiling_height': 3.0,
            'renovation_type': 'без отделки',
            'balcony_type': 'балкон',
            'has_parking': True,
            'metro_station': metro_station,
            'distance_to_metro': 950,
            'mortgage_available': True,
            'initial_payment': 3_000_000,
            'construction_type': construction_type,
            'elevator_count': 3,
            'developer_name': developer_name
        })
    
    # Создаем DataFrame
    df = pd.DataFrame(data)
    
    # Сохраняем в Excel с форматированием
    with pd.ExcelWriter('templates/example_catalog.xlsx', engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Каталог')
        worksheet = writer.sheets['Каталог']
        
        # Форматируем ширину колонок
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
    create_example_excel() 
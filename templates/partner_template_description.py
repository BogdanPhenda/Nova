import pandas as pd
import numpy as np
from datetime import datetime

def generate_example_data():
    """Генерирует пример данных для шаблона."""
    
    # Создаем данные для двух ЖК с разными корпусами
    data = []
    
    # ЖК 1
    complex_1 = {
        'complex_name': 'ЖК Солнечный',
        'address': 'г. Москва, ул. Ленина, д. 10',
        'metro_station': 'Сокольники',
        'distance_to_metro': 7,
        'developer_name': 'СтройИнвест'
    }
    
    # Корпус 1 ЖК Солнечный
    for i in range(1, 6):
        data.append({
            'internal_id': f'F{100+i}',
            'complex_name': complex_1['complex_name'],
            'building_name': 'Корпус 1',
            'address': complex_1['address'],
            'property_type': 'квартира',
            'category': 'продажа',
            'price': 8_500_000 + i * 500_000,
            'area_total': 54.2 + i * 10,
            'area_living': 32.1 + i * 7,
            'area_kitchen': 12.3 + i * 2,
            'floor': i + 1,
            'floors_total': 12,
            'rooms': min(i, 4),
            'renovation_type': 'чистовая',
            'metro_station': complex_1['metro_station'],
            'distance_to_metro': complex_1['distance_to_metro'],
            'section': '1',
            'ceiling_height': 2.8,
            'balcony_type': 'лоджия',
            'has_parking': 'да',
            'windows_view': 'во двор',
            'description': f'Светлая {min(i, 4)}-комнатная квартира с качественной отделкой',
            'developer_name': complex_1['developer_name'],
            'image_urls': 'http://example.com/img1.jpg,http://example.com/img2.jpg'
        })
    
    # ЖК 2
    complex_2 = {
        'complex_name': 'ЖК Парковый',
        'address': 'г. Москва, ул. Парковая, д. 5',
        'metro_station': 'Измайловская',
        'distance_to_metro': 5,
        'developer_name': 'ГородСтрой'
    }
    
    # Коммерческие помещения
    for i in range(1, 4):
        data.append({
            'internal_id': f'C{100+i}',
            'complex_name': complex_2['complex_name'],
            'building_name': 'Корпус 2',
            'address': complex_2['address'],
            'property_type': 'коммерция',
            'category': 'продажа',
            'price': 15_000_000 + i * 1_000_000,
            'area_total': 80.0 + i * 20,
            'floor': 1,
            'floors_total': 25,
            'renovation_type': 'без отделки',
            'metro_station': complex_2['metro_station'],
            'distance_to_metro': complex_2['distance_to_metro'],
            'section': '1',
            'ceiling_height': 3.2,
            'has_parking': 'да',
            'windows_view': 'на улицу',
            'description': f'Коммерческое помещение {i} с отдельным входом',
            'developer_name': complex_2['developer_name'],
            'image_urls': 'http://example.com/commercial1.jpg'
        })

    return pd.DataFrame(data)

def save_template(output_path='partner_template.xlsx'):
    """Создает Excel файл с примером данных и описанием полей."""
    
    # Создаем Excel writer
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # Генерируем и сохраняем пример данных
        df = generate_example_data()
        df.to_excel(writer, sheet_name='Пример данных', index=False)
        
        # Настраиваем ширину столбцов
        worksheet = writer.sheets['Пример данных']
        for idx, col in enumerate(df.columns):
            max_length = max(
                df[col].astype(str).apply(len).max(),
                len(col)
            )
            worksheet.column_dimensions[chr(65 + idx)].width = max_length + 2

if __name__ == '__main__':
    save_template() 
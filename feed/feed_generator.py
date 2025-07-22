import xml.etree.ElementTree as ET
from xml.dom import minidom
import datetime
import logging
import pandas as pd
from typing import Union, List
from models.real_estate import ResidentialComplex

logger = logging.getLogger(__name__)

class XMLFeedGenerator:
    """Генератор XML-фида для объектов недвижимости."""
    
    def __init__(self):
        self.namespace = "http://webmaster.yandex.ru/schemas/feed/realty/2010-06"
    
    def create_xml_feed(self, data: Union[pd.DataFrame, List[dict]], output_path: str, developer_id: str = None) -> bool:
        """
        Генерирует XML-фид на основе данных.
        :param data: DataFrame или список записей из Google Sheets
        :param output_path: Путь для сохранения итогового XML-файла
        :param developer_id: ID застройщика (если нужно отфильтровать данные)
        """
        try:
            # Преобразуем данные в DataFrame, если это список словарей
            if isinstance(data, list):
                df = pd.DataFrame(data)
            else:
                df = data

            # Проверяем, есть ли данные
            if len(df) == 0:
                logger.warning("Нет данных для генерации XML фида")
                return False

            # Фильтруем данные по застройщику, если указан ID
            if developer_id:
                df = df[df['developer_telegram_id'].astype(str) == str(developer_id)]
                if len(df) == 0:
                    logger.warning(f"Нет данных для застройщика {developer_id}")
                    return False

            # Создаем корневой элемент
            realty_feed = ET.Element('realty-feed')
            realty_feed.set('xmlns', self.namespace)
            
            # Добавляем дату генерации
            ET.SubElement(realty_feed, 'generation-date').text = datetime.datetime.now().isoformat()
            
            # Для каждой записи создаем offer
            for _, row in df.iterrows():
                offer = ET.SubElement(realty_feed, 'offer')
                offer.set('internal-id', str(row['internal_id']))
                
                # Основные характеристики объекта
                ET.SubElement(offer, 'type').text = 'продажа'
                ET.SubElement(offer, 'property-type').text = str(row.get('property_type', 'квартира'))
                ET.SubElement(offer, 'category').text = str(row.get('category', 'жилая'))
                if 'creation_date' in row:
                    ET.SubElement(offer, 'creation-date').text = str(row['creation_date'])
                
                # Местоположение
                location = ET.SubElement(offer, 'location')
                ET.SubElement(location, 'country').text = 'Россия'
                ET.SubElement(location, 'address').text = str(row['address'])
                
                # Цена
                price_element = ET.SubElement(offer, 'price')
                ET.SubElement(price_element, 'value').text = str(row['price'])
                ET.SubElement(price_element, 'currency').text = str(row.get('currency', 'RUB'))
                
                # Площади
                area_element = ET.SubElement(offer, 'area')
                ET.SubElement(area_element, 'value').text = str(row['area_total'])
                ET.SubElement(area_element, 'unit').text = 'кв. м'
                
                if pd.notna(row.get('area_living')):
                    living_space = ET.SubElement(offer, 'living-space')
                    ET.SubElement(living_space, 'value').text = str(row['area_living'])
                    ET.SubElement(living_space, 'unit').text = 'кв. м'
                
                if pd.notna(row.get('area_kitchen')):
                    kitchen_space = ET.SubElement(offer, 'kitchen-space')
                    ET.SubElement(kitchen_space, 'value').text = str(row['area_kitchen'])
                    ET.SubElement(kitchen_space, 'unit').text = 'кв. м'
                
                # Этажность
                if pd.notna(row.get('floor')):
                    ET.SubElement(offer, 'floor').text = str(row['floor'])
                if pd.notna(row.get('floors_total')):
                    ET.SubElement(offer, 'floors-total').text = str(row['floors_total'])
                
                # Информация о здании
                if pd.notna(row.get('building_name')):
                    ET.SubElement(offer, 'building-name').text = str(row['building_name'])
                if pd.notna(row.get('built_year')):
                    ET.SubElement(offer, 'built-year').text = str(row['built_year'])
                
                # Дополнительная информация
                if pd.notna(row.get('windows_view')):
                    ET.SubElement(offer, 'window-view').text = str(row['windows_view'])
                if pd.notna(row.get('number')):
                    ET.SubElement(offer, 'apartment-number').text = str(row['number'])
                if pd.notna(row.get('description')):
                    ET.SubElement(offer, 'description').text = str(row['description'])
                
                # Изображения
                if pd.notna(row.get('image_urls')):
                    for url in str(row['image_urls']).split(','):
                        if url.strip():
                            image_element = ET.SubElement(offer, 'image')
                            image_element.text = url.strip()
            
            # Форматируем и сохраняем XML
            xml_str = ET.tostring(realty_feed, 'utf-8')
            dom = minidom.parseString(xml_str)
            pretty_xml = dom.toprettyxml(indent='  ', encoding='utf-8')
            
            with open(output_path, 'wb') as f:
                f.write(pretty_xml)
                
            logger.info(f"XML-фид успешно сгенерирован и сохранён в: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при генерации XML-фида: {e}")
            return False 
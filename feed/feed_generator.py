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
    
    def generate_feed(self, data: Union[pd.DataFrame, List[dict]], developer_id: str = None) -> str:
        """
        Генерирует XML-фид на основе данных и возвращает его как строку.
        :param data: DataFrame или список записей из Google Sheets
        :param developer_id: ID застройщика (если нужно отфильтровать данные)
        :return: XML-фид в виде строки
        """
        try:
            # Преобразуем данные в DataFrame, если это список словарей
            if isinstance(data, list):
                df = pd.DataFrame(data)
            else:
                df = data

            if len(df) == 0:
                logger.warning("Нет данных для генерации XML фида")
                return ""

            if developer_id:
                df = df[df['developer_telegram_id'].astype(str) == str(developer_id)]
                if len(df) == 0:
                    logger.warning(f"Нет данных для застройщика {developer_id}")
                    return ""

            # Создаем корневой элемент
            realty_feed = ET.Element('realty-feed')
            realty_feed.set('xmlns', self.namespace)
            ET.SubElement(realty_feed, 'generation-date').text = datetime.datetime.now().isoformat()

            # Группируем по ЖК, корпусу и застройщику
            if 'complex_name' in df.columns:
                # Сначала группируем по ЖК
                for complex_name, complex_group in df.groupby('complex_name'):
                    complex_element = ET.SubElement(realty_feed, 'complex')
                    complex_id = f"complex_{complex_name}"
                    if 'developer_id' in df.columns:
                        developer_id_val = complex_group['developer_id'].iloc[0]
                        complex_id = f"complex_{developer_id_val}_{complex_name}"
                    
                    ET.SubElement(complex_element, 'id').text = complex_id
                    ET.SubElement(complex_element, 'name').text = str(complex_name)
                    
                    # Затем группируем по корпусам внутри ЖК
                    if 'building_name' in df.columns:
                        for building_name, building_group in complex_group.groupby('building_name'):
                            building_element = ET.SubElement(complex_element, 'building')
                            ET.SubElement(building_element, 'id').text = f"building_{complex_id}_{building_name}"
                            ET.SubElement(building_element, 'name').text = str(building_name)
                            
                            # Добавляем квартиры в корпус
                            for _, row in building_group.iterrows():
                                self._add_offer(building_element, row)
                    else:
                        # Если нет корпусов, добавляем квартиры напрямую в ЖК
                        for _, row in complex_group.iterrows():
                            self._add_offer(complex_element, row)
            
            elif 'building_name' in df.columns:
                # Если нет ЖК, но есть корпуса
                for building_name, building_group in df.groupby('building_name'):
                    building_element = ET.SubElement(realty_feed, 'building')
                    ET.SubElement(building_element, 'id').text = f"building_{building_name}"
                    ET.SubElement(building_element, 'name').text = str(building_name)
                    
                    # Добавляем квартиры в корпус
                    for _, row in building_group.iterrows():
                        self._add_offer(building_element, row)
            
            else:
                # Если нет ни ЖК, ни корпусов - добавляем объекты напрямую
                for _, row in df.iterrows():
                    self._add_offer(realty_feed, row)

            # Преобразуем в строку с отступами
            xml_str = ET.tostring(realty_feed, 'utf-8')
            dom = minidom.parseString(xml_str)
            pretty_xml = dom.toprettyxml(indent='  ', encoding='utf-8')
            
            return pretty_xml.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Ошибка при генерации XML-фида: {e}")
            raise

    def create_xml_feed(self, data: Union[pd.DataFrame, List[dict]], output_path: str, developer_id: str = None) -> bool:
        """
        Генерирует XML-фид и сохраняет его в файл.
        :param data: DataFrame или список записей из Google Sheets
        :param output_path: Путь для сохранения итогового XML-файла
        :param developer_id: ID застройщика (если нужно отфильтровать данные)
        :return: True если фид успешно создан, иначе False
        """
        try:
            xml_content = self.generate_feed(data, developer_id)
            if not xml_content:
                return False
                
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
                
            logger.info(f"XML-фид успешно сгенерирован и сохранён в: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении XML-фида: {e}")
            return False

    def _add_offer(self, realty_feed, row):
        offer = ET.SubElement(realty_feed, 'offer')
        offer.set('internal-id', str(row.get('internal_id', '')))
        # Основные характеристики
        ET.SubElement(offer, 'type').text = str(row.get('category', 'продажа'))
        ET.SubElement(offer, 'property-type').text = str(row.get('property_type', 'квартира'))
        ET.SubElement(offer, 'category').text = str(row.get('category', 'жилая'))
        if 'creation_date' in row and pd.notna(row.get('creation_date')):
            ET.SubElement(offer, 'creation-date').text = str(row['creation_date'])
        # Местоположение
        location = ET.SubElement(offer, 'location')
        ET.SubElement(location, 'country').text = 'Россия'
        if pd.notna(row.get('address')):
            ET.SubElement(location, 'address').text = str(row['address'])
        if pd.notna(row.get('metro_station')):
            ET.SubElement(location, 'metro-station').text = str(row['metro_station'])
        if pd.notna(row.get('distance_to_metro')):
            ET.SubElement(location, 'distance-to-metro').text = str(row['distance_to_metro'])
        # Цена
        if pd.notna(row.get('price')):
            price_element = ET.SubElement(offer, 'price')
            ET.SubElement(price_element, 'value').text = str(row['price'])
            ET.SubElement(price_element, 'currency').text = str(row.get('currency', 'RUB'))
        if pd.notna(row.get('price_sale')):
            ET.SubElement(offer, 'price-sale').text = str(row['price_sale'])
        # Площади
        if pd.notna(row.get('area_total')):
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
        if pd.notna(row.get('section')):
            ET.SubElement(offer, 'section').text = str(row['section'])
        if pd.notna(row.get('construction_type')):
            ET.SubElement(offer, 'construction-type').text = str(row['construction_type'])
        if pd.notna(row.get('elevator_count')):
            ET.SubElement(offer, 'elevator-count').text = str(row['elevator_count'])
        # Квартира
        if pd.notna(row.get('number')):
            ET.SubElement(offer, 'apartment-number').text = str(row['number'])
        if pd.notna(row.get('rooms')):
            ET.SubElement(offer, 'rooms').text = str(row['rooms'])
        if pd.notna(row.get('ceiling_height')):
            ET.SubElement(offer, 'ceiling-height').text = str(row['ceiling_height'])
        if pd.notna(row.get('renovation_type')):
            ET.SubElement(offer, 'renovation-type').text = str(row['renovation_type'])
        if pd.notna(row.get('balcony_type')):
            ET.SubElement(offer, 'balcony-type').text = str(row['balcony_type'])
        if pd.notna(row.get('has_parking')):
            ET.SubElement(offer, 'has-parking').text = str(row['has_parking'])
        if pd.notna(row.get('windows_view')):
            ET.SubElement(offer, 'window-view').text = str(row['windows_view'])
        if pd.notna(row.get('description')):
            ET.SubElement(offer, 'description').text = str(row['description'])
        # Ипотека и застройщик
        if pd.notna(row.get('mortgage_available')):
            ET.SubElement(offer, 'mortgage-available').text = str(row['mortgage_available'])
        if pd.notna(row.get('initial_payment')):
            ET.SubElement(offer, 'initial-payment').text = str(row['initial_payment'])
        if pd.notna(row.get('developer_name')):
            ET.SubElement(offer, 'developer-name').text = str(row['developer_name'])
        # Изображения
        if pd.notna(row.get('image_urls')):
            for url in str(row['image_urls']).split(','):
                if url.strip():
                    image_element = ET.SubElement(offer, 'image')
                    image_element.text = url.strip() 
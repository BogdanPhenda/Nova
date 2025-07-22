import xml.etree.ElementTree as ET
from xml.dom import minidom
import datetime
import logging
import os

def create_xml_feed(records: list[dict], output_path: str):
    """
    Генерирует XML-фид на основе данных из Google Таблицы.
    :param records: Список словарей, где каждый словарь - строка из таблицы.
    :param output_path: Путь для сохранения итогового XML-файла.
    """
    try:
        realty_feed = ET.Element('realty-feed')
        realty_feed.set('xmlns', 'http://webmaster.yandex.ru/schemas/feed/realty/2010-06')
        ET.SubElement(realty_feed, 'generation-date').text = datetime.datetime.now().isoformat()
        for record in records:
            offer = ET.SubElement(realty_feed, 'offer')
            offer.set('internal-id', str(record.get('internal_id', '')))
            field_map = {
                'type': 'продажа',
                'property-type': record.get('property_type'),
                'category': record.get('category'),
                'creation-date': record.get('creation_date'),
                'location': {
                    'country': 'Россия',
                    'address': record.get('address')
                },
                'price': {
                    'value': str(record.get('price', '')),
                    'currency': record.get('currency')
                },
                'area': {'value': str(record.get('area_total', '')), 'unit': 'кв. м'},
                'living-space': {'value': str(record.get('area_living', '')), 'unit': 'кв. м'},
                'kitchen-space': {'value': str(record.get('area_kitchen', '')), 'unit': 'кв. м'},
                'description': record.get('description'),
                'floor': str(record.get('floor', '')),
                'floors-total': str(record.get('floors_total', '')),
                'building-name': record.get('building_name'),
                'built-year': str(record.get('built_year', '')),
                'windows-view': record.get('windows_view'),
                'apartment-number': record.get('number'),
                'price-sale': str(record.get('price_sale', '')),
            }
            for key, value in field_map.items():
                if value is None or value == '': continue
                if isinstance(value, dict):
                    parent_element = ET.SubElement(offer, key)
                    for sub_key, sub_value in value.items():
                        if sub_value is not None and sub_value != '':
                            ET.SubElement(parent_element, sub_key).text = str(sub_value)
                else:
                    ET.SubElement(offer, key).text = str(value)
            images_str = record.get('image_urls', '')
            if images_str:
                for url in images_str.split(','):
                    ET.SubElement(offer, 'image').text = url.strip()
        xml_str = ET.tostring(realty_feed, 'utf-8')
        dom = minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent='  ', encoding='utf-8')
        with open(output_path, 'wb') as f:
            f.write(pretty_xml)
        logging.info(f"XML-фид успешно сгенерирован и сохранён в: {output_path}")
        return True
    except Exception as e:
        logging.error(f"Ошибка при генерации XML-фида: {e}")
        return False 
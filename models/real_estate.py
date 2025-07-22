from typing import Optional, List
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum

class RenovationType(str, Enum):
    """Типы отделки помещения."""
    NONE = "без отделки"
    ROUGH = "черновая"
    FINISHED = "чистовая"

class ParkingType(str, Enum):
    """Типы парковки."""
    GROUND = "наземная"
    UNDERGROUND = "подземная"
    MULTILEVEL = "многоуровневая"
    NONE = "отсутствует"

class ConstructionType(str, Enum):
    """Типы конструкции здания."""
    MONOLITHIC = "монолит"
    PANEL = "панель"
    BRICK = "кирпич"
    MONOLITHIC_BRICK = "монолит-кирпич"

class Location(BaseModel):
    """Модель для представления местоположения объекта."""
    country: str = Field(default="Россия")
    region: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    address: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_to_metro: Optional[int] = None  # расстояние до метро в метрах
    metro_station: Optional[str] = None  # название станции метро

class Price(BaseModel):
    """Модель для представления цены объекта."""
    value: float
    currency: str = Field(default="RUB")
    price_per_meter: Optional[float] = None
    discount: Optional[float] = None
    mortgage_available: Optional[bool] = None
    initial_payment: Optional[float] = None  # минимальный первоначальный взнос
    
    @validator('value')
    def validate_price(cls, v):
        if v <= 0:
            raise ValueError("Цена должна быть положительным числом")
        return v

class Area(BaseModel):
    """Модель для представления площади помещения."""
    total: float
    living: Optional[float] = None
    kitchen: Optional[float] = None
    balcony: Optional[float] = None
    unit: str = Field(default="кв. м")
    
    @validator('total')
    def validate_total_area(cls, v):
        if v <= 0:
            raise ValueError("Общая площадь должна быть положительным числом")
        return v
    
    @validator('living')
    def validate_living_area(cls, v, values):
        if v is not None:
            if v <= 0:
                raise ValueError("Жилая площадь должна быть положительным числом")
            if 'total' in values and v >= values['total']:
                raise ValueError("Жилая площадь не может быть больше общей")
        return v

class Image(BaseModel):
    """Модель для представления изображения объекта."""
    url: str
    sort_order: Optional[int] = None
    description: Optional[str] = None
    is_plan: Optional[bool] = None  # является ли изображение планировкой
    
    @validator('url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError("URL должен начинаться с http:// или https://")
        return v

class Property(BaseModel):
    """Модель для представления объекта недвижимости."""
    internal_id: str
    property_type: str = Field(default="квартира")
    category: str = Field(default="продажа")
    creation_date: datetime = Field(default_factory=datetime.now)
    location: Location
    price: Price
    area: Area
    description: Optional[str] = None
    floor: Optional[int] = None
    floors_total: Optional[int] = None
    rooms: Optional[int] = None
    apartment_number: Optional[str] = None
    images: List[Image] = Field(default_factory=list)
    windows_view: Optional[str] = None
    ceiling_height: Optional[float] = None
    renovation_type: Optional[RenovationType] = None
    balcony_type: Optional[str] = None
    has_parking: Optional[bool] = None
    
    @validator('floor')
    def validate_floor(cls, v, values):
        if v is not None:
            if v < 1:
                raise ValueError("Этаж должен быть положительным числом")
            if 'floors_total' in values and values['floors_total'] is not None:
                if v > values['floors_total']:
                    raise ValueError("Этаж не может быть больше общего количества этажей")
        return v

class Building(BaseModel):
    """Модель для представления корпуса/здания."""
    id: str
    name: str
    complex_id: str
    status: str = Field(default="строится")
    built_year: Optional[int] = None
    floors: Optional[int] = None
    properties: List[Property] = Field(default_factory=list)
    description: Optional[str] = None
    parking_type: Optional[ParkingType] = None
    elevator_count: Optional[int] = None
    construction_type: Optional[ConstructionType] = None
    facade_type: Optional[str] = None
    
    @validator('built_year')
    def validate_built_year(cls, v):
        if v is not None:
            current_year = datetime.now().year
            if v < 1900 or v > current_year + 10:
                raise ValueError(f"Год постройки должен быть между 1900 и {current_year + 10}")
        return v

class ResidentialComplex(BaseModel):
    """Модель для представления жилого комплекса."""
    id: str
    name: str
    developer_id: str
    developer_name: Optional[str] = None
    status: str = Field(default="строится")
    completion_date: Optional[datetime] = None
    description: Optional[str] = None
    location: Location
    buildings: List[Building] = Field(default_factory=list)
    infrastructure: List[str] = Field(default_factory=list)
    transport_accessibility: List[str] = Field(default_factory=list)
    sales_office_address: Optional[str] = None
    website: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        } 
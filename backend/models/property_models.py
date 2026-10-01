from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any, Dict
from datetime import datetime
from uuid import UUID

class UnitTypeItem(BaseModel):
    type: str
    config: str
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    price_per_sqyd_min: Optional[float] = None
    price_per_sqyd_max: Optional[float] = None
    land_sqyd: Optional[float] = None
    built_sqft: Optional[float] = None
    possession: Optional[str] = None
    price_is_reference: bool = False

    @field_validator('price_max')
    def check_price_range(cls, v, info):
        price_min = info.data.get('price_min')
        if v is not None and price_min is not None and v < price_min:
            raise ValueError('price_max cannot be less than price_min')
        return v
        
    @field_validator('price_per_sqyd_max')
    def check_price_sqyd_range(cls, v, info):
        price_min = info.data.get('price_per_sqyd_min')
        if v is not None and price_min is not None and v < price_min:
            raise ValueError('price_per_sqyd_max cannot be less than price_per_sqyd_min')
        return v

class PropertyCreateRequest(BaseModel):
    name: str
    aliases: List[str] = Field(default_factory=list)
    city: str
    region: Optional[str] = None
    property_type: str
    unit_types: List[UnitTypeItem] = Field(default_factory=list)
    facts: Dict[str, Any] = Field(default_factory=dict)
    raw_text: Optional[str] = None

class PropertyUpdateRequest(BaseModel):
    name: Optional[str] = None
    aliases: Optional[List[str]] = None
    city: Optional[str] = None
    region: Optional[str] = None
    property_type: Optional[str] = None
    unit_types: Optional[List[UnitTypeItem]] = None
    facts: Optional[Dict[str, Any]] = None
    raw_text: Optional[str] = None

class PropertyReviewConfirmRequest(BaseModel):
    unit_types: List[UnitTypeItem]
    facts: Dict[str, Any]

class PropertyOut(BaseModel):
    property_id: UUID
    dealer_id: UUID
    name: str
    aliases: List[str]
    city: str
    region: Optional[str]
    property_type: str
    unit_types: List[UnitTypeItem]
    facts: Dict[str, Any]
    raw_text: Optional[str]
    cleaned_text: Optional[str]
    extraction_warnings: List[str]
    status: str
    created_at: datetime
    updated_at: datetime

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PropertyRead(BaseModel):
    id: int
    parcel_id: str
    address: str | None
    city: str | None
    state: str | None
    zip_code: str | None
    latitude: float | None
    longitude: float | None
    assessed_value: Decimal | None
    source: str | None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str
    database: str


class HealthResponse(BaseModel):
    status: str
    database: str

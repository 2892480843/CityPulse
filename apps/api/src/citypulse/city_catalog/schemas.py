import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict


class CityView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    province: str
    valid_from: date | None
    valid_to: date | None
    aliases: list[str]


class CityListResponse(BaseModel):
    items: list[CityView]
    total: int

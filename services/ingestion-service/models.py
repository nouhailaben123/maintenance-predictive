from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class Values(BaseModel):
    temperature_c: float
    vibration_mms: float
    power_kw: float
    rpm: float


class Measure(BaseModel):
    message_id: UUID
    machine_id: str
    seq: int = Field(ge=0)          # entier >= 0
    timestamp: datetime
    status: Literal["running", "idle", "stopped"]
    values: Values
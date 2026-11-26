from enum import Enum
from typing import Literal
from uuid import UUID
from pydantic import AwareDatetime, BaseModel, Field


class Values(BaseModel):
    temperature_c: float = Field(ge=-50, le=500)
    vibration_mms: float = Field(ge=0, le=100)
    power_kw: float = Field(ge=0, le=1000)
    rpm: int = Field(ge=0, le=20000)


class Measure(BaseModel):
    message_id: UUID
    machine_id: str = Field(min_length=1, max_length=32)
    seq: int = Field(ge=0)
    timestamp: AwareDatetime
    status: Literal["running", "idle", "stopped"]
    values: Values


class MeasureBatch(BaseModel):
    measures: list[Measure] = Field(min_length=1, max_length=500)
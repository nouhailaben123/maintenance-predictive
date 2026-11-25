from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, field_validator

class Values(BaseModel):
    temperature_c: float
    vibration_mms: float
    power_kw: float
    rpm: float

class MeasureMsg(BaseModel):
    message_id: str
    machine_id: str
    seq: int
    timestamp: datetime

    @field_validator("timestamp")
    @classmethod
    def _as_utc(cls, v: datetime) -> datetime:
        # Le contrat impose l'UTC. L'ingestion accepte aussi une date sans fuseau :
        # on l'interprète comme UTC (sinon les comparaisons de dates échouent).
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v
    status: Literal["running", "idle", "stopped"]
    values: Values
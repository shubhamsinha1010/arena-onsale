from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateGaReservationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str = Field(min_length=1, max_length=128)
    quantity: int = Field(ge=1)


class GaReservationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    match_id: UUID
    quantity: int
    status: str
    expires_at: datetime

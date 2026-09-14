from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateHoldRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str = Field(min_length=1, max_length=128)
    seat_ids: list[UUID] = Field(min_length=1)


class HeldSeat(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    section: str
    row: str
    number: str


class HoldResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    match_id: UUID
    status: str
    expires_at: datetime
    seats: list[HeldSeat]

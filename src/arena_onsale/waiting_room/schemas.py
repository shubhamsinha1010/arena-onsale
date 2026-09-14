from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class JoinRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    visitor_id: str = Field(min_length=1, max_length=128)


class WaitingRoomResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: str
    visitor_id: str
    token: str | None = None
    expires_at: datetime | None = None
    position: int | None = None
    estimated_wait_seconds: int | None = None
    queued: int
    admitted: int


class WaitingRoomStats(BaseModel):
    model_config = ConfigDict(frozen=True)

    queued: int
    admitted: int
    admit_per_minute: int
    bulkhead: int

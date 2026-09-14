from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GaSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    available: int
    capacity: int
    approximate: bool = True


class MatchSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    slug: str
    name: str
    venue: str
    starts_at: datetime
    ga: GaSummary | None = None


class SeatMapResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    match_id: UUID
    slug: str
    approximate: bool
    from_cache: bool = False
    ttl_seconds: int
    assigned_available: int
    assigned_total: int
    ga: GaSummary | None
    sections: dict[str, dict[str, list[dict[str, str]]]] = Field(
        description="Display-only seat colours. Holds are confirmed on reserve, not from this map."
    )

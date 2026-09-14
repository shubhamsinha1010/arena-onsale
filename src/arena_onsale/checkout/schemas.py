from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str = Field(min_length=1, max_length=128)
    hold_id: UUID | None = None
    ga_reservation_id: UUID | None = None

    @model_validator(mode="after")
    def exactly_one_reservation(self) -> "CheckoutRequest":
        if (self.hold_id is None) == (self.ga_reservation_id is None):
            raise ValueError("provide exactly one of hold_id or ga_reservation_id")
        return self


class CheckoutResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    status: str
    amount_cents: int
    currency: str
    created_at: datetime

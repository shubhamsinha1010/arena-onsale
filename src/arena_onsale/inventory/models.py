from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from arena_onsale.catalog.models import Match
from arena_onsale.shared.persistence import Base


class HoldStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CONFIRMED = "CONFIRMED"
    EXPIRED = "EXPIRED"
    RELEASED = "RELEASED"


class Hold(Base):
    __tablename__ = "holds"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_holds_idempotency_key"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    match_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[HoldStatus] = mapped_column(
        Enum(HoldStatus, name="hold_status", native_enum=True),
        default=HoldStatus.ACTIVE,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    match: Mapped[Match] = relationship()


class GaReservation(Base):
    __tablename__ = "ga_reservations"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ga_reservations_idempotency_key"),
        CheckConstraint("quantity >= 1", name="ck_ga_reservation_quantity_positive"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    match_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[HoldStatus] = mapped_column(
        Enum(HoldStatus, name="hold_status", native_enum=True, create_type=False),
        default=HoldStatus.ACTIVE,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    match: Mapped[Match] = relationship()

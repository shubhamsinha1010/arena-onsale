from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from arena_onsale.shared.persistence import Base


class SeatStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    HELD = "HELD"
    SOLD = "SOLD"


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    venue: Mapped[str] = mapped_column(String(160))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    seats: Mapped[list["Seat"]] = relationship(back_populates="match")
    ga: Mapped["GeneralAdmission | None"] = relationship(back_populates="match", uselist=False)


class Seat(Base):
    __tablename__ = "seats"
    __table_args__ = (
        UniqueConstraint("match_id", "section", "row", "number", name="uq_seat_location"),
        Index("ix_seats_match_status", "match_id", "status"),
        CheckConstraint("version >= 1", name="ck_seat_version_positive"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    match_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )
    section: Mapped[str] = mapped_column(String(16), nullable=False)
    row: Mapped[str] = mapped_column(String(8), nullable=False)
    number: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[SeatStatus] = mapped_column(
        Enum(SeatStatus, name="seat_status", native_enum=True),
        default=SeatStatus.AVAILABLE,
        nullable=False,
    )
    hold_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    held_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    match: Mapped[Match] = relationship(back_populates="seats")


class GeneralAdmission(Base):
    __tablename__ = "ga_inventory"
    __table_args__ = (
        CheckConstraint("available >= 0", name="ck_ga_available_non_negative"),
        CheckConstraint("available <= capacity", name="ck_ga_available_lte_capacity"),
        CheckConstraint("version >= 1", name="ck_ga_version_positive"),
    )

    match_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True
    )
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    available: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    match: Mapped[Match] = relationship(back_populates="ga")

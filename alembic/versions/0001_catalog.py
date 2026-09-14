"""Catalog matches, assigned seats, and general-admission inventory.

Revision ID: 0001_catalog
Revises:
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_catalog"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

seat_status = postgresql.ENUM("AVAILABLE", "HELD", "SOLD", name="seat_status")


def upgrade() -> None:
    seat_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("venue", sa.String(length=160), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slug", name="uq_matches_slug"),
    )
    op.create_table(
        "seats",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section", sa.String(length=16), nullable=False),
        sa.Column("row", sa.String(length=8), nullable=False),
        sa.Column("number", sa.String(length=8), nullable=False),
        sa.Column("status", seat_status, nullable=False),
        sa.Column("hold_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("held_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("match_id", "section", "row", "number", name="uq_seat_location"),
        sa.CheckConstraint("version >= 1", name="ck_seat_version_positive"),
    )
    op.create_index("ix_seats_match_status", "seats", ["match_id", "status"])
    op.create_table(
        "ga_inventory",
        sa.Column("match_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("available", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ondelete="CASCADE"),
        sa.CheckConstraint("available >= 0", name="ck_ga_available_non_negative"),
        sa.CheckConstraint("available <= capacity", name="ck_ga_available_lte_capacity"),
        sa.CheckConstraint("version >= 1", name="ck_ga_version_positive"),
    )


def downgrade() -> None:
    op.drop_table("ga_inventory")
    op.drop_index("ix_seats_match_status", table_name="seats")
    op.drop_table("seats")
    op.drop_table("matches")
    seat_status.drop(op.get_bind(), checkfirst=True)

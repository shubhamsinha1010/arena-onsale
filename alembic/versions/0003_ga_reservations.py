"""General-admission reservations with an optimistic version counter.

Revision ID: 0003_ga_reservations
Revises: 0002_holds
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_ga_reservations"
down_revision: str | None = "0002_holds"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    hold_status = postgresql.ENUM(
        "ACTIVE",
        "CONFIRMED",
        "EXPIRED",
        "RELEASED",
        name="hold_status",
        create_type=False,
    )
    op.create_table(
        "ga_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", hold_status, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("idempotency_key", name="uq_ga_reservations_idempotency_key"),
        sa.CheckConstraint("quantity >= 1", name="ck_ga_reservation_quantity_positive"),
    )
    op.create_index("ix_ga_reservations_match_id", "ga_reservations", ["match_id"])


def downgrade() -> None:
    op.drop_index("ix_ga_reservations_match_id", table_name="ga_reservations")
    op.drop_table("ga_reservations")

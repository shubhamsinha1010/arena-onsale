"""Holds for assigned-seat pessimistic reservations.

Revision ID: 0002_holds
Revises: 0001_catalog
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_holds"
down_revision: str | None = "0001_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

hold_status = postgresql.ENUM("ACTIVE", "CONFIRMED", "EXPIRED", "RELEASED", name="hold_status")


def upgrade() -> None:
    hold_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "holds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("status", hold_status, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("idempotency_key", name="uq_holds_idempotency_key"),
    )
    op.create_index("ix_holds_match_id", "holds", ["match_id"])
    op.create_index("ix_seats_hold_id", "seats", ["hold_id"])
    op.create_foreign_key(
        "fk_seats_hold_id",
        "seats",
        "holds",
        ["hold_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_seats_hold_id", "seats", type_="foreignkey")
    op.drop_index("ix_seats_hold_id", table_name="seats")
    op.drop_index("ix_holds_match_id", table_name="holds")
    op.drop_table("holds")
    hold_status.drop(op.get_bind(), checkfirst=True)

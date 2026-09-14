"""Orders, payments, and the transactional outbox.

Revision ID: 0004_checkout
Revises: 0003_ga_reservations
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_checkout"
down_revision: str | None = "0003_ga_reservations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

order_status = postgresql.ENUM(
    "PAYMENT_PENDING",
    "CONFIRMED",
    "PAYMENT_FAILED",
    "COMPENSATED",
    "EXPIRED",
    name="order_status",
)
payment_status = postgresql.ENUM("PENDING", "CAPTURED", "FAILED", "REFUNDED", name="payment_status")


def upgrade() -> None:
    order_status.create(op.get_bind(), checkfirst=True)
    payment_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("hold_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ga_reservation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", order_status, nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="INR"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["hold_id"], ["holds.id"]),
        sa.ForeignKeyConstraint(["ga_reservation_id"], ["ga_reservations.id"]),
        sa.UniqueConstraint("idempotency_key", name="uq_orders_idempotency_key"),
        sa.CheckConstraint(
            "(hold_id IS NOT NULL AND ga_reservation_id IS NULL)"
            " OR (hold_id IS NULL AND ga_reservation_id IS NOT NULL)",
            name="ck_orders_one_reservation",
        ),
        sa.CheckConstraint("version >= 1", name="ck_orders_version_positive"),
        sa.CheckConstraint("amount_cents > 0", name="ck_orders_amount_positive"),
    )
    op.create_index(
        "uq_orders_hold_id",
        "orders",
        ["hold_id"],
        unique=True,
        postgresql_where=sa.text("hold_id IS NOT NULL"),
    )
    op.create_index(
        "uq_orders_ga_reservation_id",
        "orders",
        ["ga_reservation_id"],
        unique=True,
        postgresql_where=sa.text("ga_reservation_id IS NOT NULL"),
    )
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("psp_ref", sa.String(length=128), nullable=True),
        sa.Column("status", payment_status, nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("idempotency_key", name="uq_payments_idempotency_key"),
        sa.UniqueConstraint("psp_ref", name="uq_payments_psp_ref"),
    )
    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_outbox_unpublished", "outbox_events", ["published_at"])


def downgrade() -> None:
    op.drop_index("ix_outbox_unpublished", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_table("payments")
    op.drop_index("uq_orders_ga_reservation_id", table_name="orders")
    op.drop_index("uq_orders_hold_id", table_name="orders")
    op.drop_table("orders")
    payment_status.drop(op.get_bind(), checkfirst=True)
    order_status.drop(op.get_bind(), checkfirst=True)

"""Process-wide configuration.

Application traffic always goes through PgBouncer in transaction pooling
mode. Migrations use DATABASE_ADMIN_URL so they talk to Postgres directly —
prepared statements and transaction pooling do not mix.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "arena-onsale"
    environment: str = "local"

    database_url: str = "postgresql+asyncpg://arena:arena@127.0.0.1:6432/arena"
    database_admin_url: str = "postgresql+asyncpg://arena:arena@127.0.0.1:5432/arena"

    # Sized per uvicorn worker. PgBouncer sits in front and multiplexes onto
    # a smaller Postgres max_connections budget.
    db_pool_size: int = 10
    db_max_overflow: int = 5
    db_pool_timeout_seconds: float = 5.0
    db_pool_recycle_seconds: int = 1800

    redis_url: str = "redis://127.0.0.1:6379/0"

    hold_ttl_seconds: int = 600
    seat_map_ttl_seconds: int = 3
    ga_max_attempts: int = 3
    ga_retry_min_ms: int = 50
    ga_retry_max_ms: int = 200
    ga_max_quantity: int = 8
    ticket_price_cents: int = 15_000
    waiting_room_admit_per_minute: int = 50_000
    checkout_concurrency_limit: int = 3_000
    shopping_ttl_seconds: int = 900
    worker_poll_seconds: float = 2.0
    worker_batch_size: int = 50


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

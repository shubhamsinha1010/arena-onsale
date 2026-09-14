from arena_onsale.shared.db import PGBOUNCER_CONNECT_ARGS, create_engine
from arena_onsale.shared.settings import Settings


def test_pgbouncer_connect_args_disable_prepared_statements() -> None:
    assert PGBOUNCER_CONNECT_ARGS == {"statement_cache_size": 0}


def test_engine_pool_size_follows_settings() -> None:
    settings = Settings(db_pool_size=8, db_max_overflow=3)
    engine = create_engine(settings)
    try:
        assert engine.sync_engine.pool.size() == 8
    finally:
        engine.sync_engine.dispose()


def test_hold_ttl_is_ten_minutes() -> None:
    assert Settings().hold_ttl_seconds == 600

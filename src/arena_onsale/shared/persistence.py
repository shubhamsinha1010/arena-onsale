from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared metadata so Alembic sees every bounded context."""

"""Database engine and session factory.

Uses psycopg (v3) driver, which supports both sync and async via
`postgresql+psycopg`. SQLAlchemy 2.0+ async engine is used throughout.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.core.config import get_settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


_settings = get_settings()

engine = create_async_engine(
    _settings.database_url,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

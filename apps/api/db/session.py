from __future__ import annotations

import os

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def _require_database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://crosslist:crosslist@localhost:5433/crosslist",
    )


def _with_driver(database_url: str, drivername: str) -> str:
    url: URL = make_url(database_url)
    if url.drivername == drivername:
        return url.render_as_string(hide_password=False)

    return url.set(drivername=drivername).render_as_string(hide_password=False)


def get_async_database_url() -> str:
    return _with_driver(_require_database_url(), "postgresql+asyncpg")


def get_sync_database_url() -> str:
    return _with_driver(_require_database_url(), "postgresql")


async_engine = create_async_engine(get_async_database_url(), future=True)
async_session_factory = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)

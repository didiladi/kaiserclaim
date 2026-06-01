"""
Shared test fixtures for KaiserClaim API tests.

Uses the local docker PostgreSQL (exposed on localhost:5432 via docker-compose).
A fresh SQLAlchemy engine is created per-test so there are no event-loop-bound
pool conflicts between tests.
"""
import os

# Must be set before any app import so lru_cache picks up the right URL.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://kaiserclaim:secret@localhost:5432/kaiserclaim",
)
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-used-in-tests")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
os.environ.setdefault("STORAGE_ROOT", "/tmp/kaiserclaim-test-storage")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("MERKUR_USERNAME", "")
os.environ.setdefault("MERKUR_PASSWORD", "")

from core.config import get_settings
get_settings.cache_clear()

import uuid
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from main import app
from core.database import get_db

# Hardcoded seed user — must exist in the local docker postgres.
TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_TEST_DB_URL = "postgresql+asyncpg://kaiserclaim:secret@localhost:5432/kaiserclaim"


@pytest_asyncio.fixture
async def client():
    """
    HTTPX async client pointed at the FastAPI app (in-process).

    Creates a fresh SQLAlchemy engine per test so there are no event-loop-bound
    connection pool conflicts between tests when using function-scoped loops.
    """
    test_engine = create_async_engine(_TEST_DB_URL, pool_pre_ping=True)
    TestSession = async_sessionmaker(test_engine, expire_on_commit=False)

    async def _override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c

    app.dependency_overrides.pop(get_db, None)
    await test_engine.dispose()


def api_url(path: str) -> str:
    """Append the mandatory user_id query param."""
    sep = "&" if "?" in path else "?"
    return f"/api/v1{path}{sep}user_id={TEST_USER_ID}"

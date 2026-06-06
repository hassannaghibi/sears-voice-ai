"""Pytest configuration: async test DB, HTTP client, Twilio signature mock."""
from __future__ import annotations

import base64
import hashlib
import hmac
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.main import app
from app.models.base import Base
from app.models import appointment, call_session, technician  # noqa: F401 — register models

# SQLite in-memory for tests (no Postgres required)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Session-scoped async SQLite engine with all tables created."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Per-test async session with rollback isolation."""
    TestSession = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with TestSession() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client wired to the test DB session."""

    async def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def mock_twilio_signature():
    """Return a helper that computes a valid X-Twilio-Signature for test payloads."""
    from app.core.config import settings

    def compute(url: str, params: dict) -> str:
        sorted_str = "".join(f"{k}{v}" for k, v in sorted(params.items()))
        s = url + sorted_str
        mac = hmac.new(
            settings.twilio_auth_token.encode(), s.encode(), hashlib.sha1
        )
        return base64.b64encode(mac.digest()).decode()

    return compute

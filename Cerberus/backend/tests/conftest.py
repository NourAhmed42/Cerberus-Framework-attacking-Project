"""
Test Configuration — Shared fixtures for pytest.
"""

import asyncio  # noqa: I001
from collections.abc import AsyncGenerator
import uuid

import pytest  # type: ignore[import-not-found]
import pytest_asyncio  # type: ignore[import-not-found]
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession, create_async_engine

from app.core.config import settings
from app.db.session import Base, get_db
from app.main import app

# Use a test database
TEST_DATABASE_URL = settings.DATABASE_URL.replace("cerberus", "cerberus_test")

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create and drop test database tables."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(autouse=True)
async def _isolate_redis_abuse_state():
    """The abuse detector keeps failed-login and 403 counters in Redis under
    ``abuse:*`` keys. Those survive between tests (the in-memory reset above
    does not touch Redis), so one test's failed logins can block 127.0.0.1 for
    the next. Remove only the ``abuse:*`` keys before and after each test.

    Point REDIS_URL at a disposable Redis for the test run, as the test guide
    requires; this fixture never touches keys outside the ``abuse:`` prefix.
    """
    from app.core.abuse_detector import AbuseDetector

    async def _clear_abuse_keys() -> None:
        client = AbuseDetector.get_client()
        if client is None:
            return
        try:
            async for key in client.scan_iter(match="abuse:*", count=500):
                await client.delete(key)
        except Exception:
            AbuseDetector.mark_redis_down()

    await _clear_abuse_keys()
    yield
    await _clear_abuse_keys()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:  # noqa: UP043
    """Provide a test database session."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture(autouse=True)
def _isolate_rate_limits_and_defense():
    """The RateLimitMiddleware keeps in-memory buckets (per IP per
    surface: login vs general) for the whole app lifetime, and the
    3-tier defense keeps in-memory state too (abuse counters, block
    list, IP history, behavioral baselines, metrics). Tests share the
    app, so clear ALL of it around every test to keep them hermetic
    (login allows 5/min per IP; 5 failed logins flag the IP)."""
    from app.api.v1.middleware.defense_middleware import reset_defense_state
    from app.api.v1.middleware.rate_limiter import RateLimitMiddleware

    RateLimitMiddleware.reset_all()
    reset_defense_state(app)
    yield
    RateLimitMiddleware.reset_all()
    reset_defense_state(app)


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:  # noqa: UP043
    """Provide a test HTTP client."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


def generate_test_email() -> str:
    return f"test_{uuid.uuid4().hex[:8]}@cerberus-test.com"

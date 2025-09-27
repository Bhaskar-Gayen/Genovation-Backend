import asyncio
import pytest
from typing import AsyncGenerator, Tuple

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base
from app.routes import auth as auth_routes
from app.routes import users as users_routes
from app.routes import chatrooms as chatrooms_routes
from app.database import get_db
from app.utils import jwt as jwt_utils


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop


@pytest.fixture(scope="session")
async def test_engine():

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", echo=False, future=True
    )
   
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    SessionLocal = async_sessionmaker(
        bind=test_engine,
        expire_on_commit=False,
        class_=AsyncSession,
        autoflush=True,
        autocommit=False,
    )
    async with SessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="function")
async def app_client(db_session: AsyncSession, monkeypatch) -> AsyncGenerator[Tuple[FastAPI, AsyncClient], None]:
    # Mock Redis utilities to avoid real Redis
    class FakeRedis:
        def __init__(self):
            self._store = {}
        async def incr(self, key):
            self._store[key] = int(self._store.get(key, 0)) + 1
            return self._store[key]
        async def expire(self, key, seconds):
            return True
        async def setex(self, key, exp, value):
            self._store[key] = value
            return True
        async def exists(self, key):
            return 1 if key in self._store else 0
        async def ping(self):
            return True
        async def close(self):
            return True
        async def get(self, key):
            return self._store.get(key)
        async def set(self, key, value, ex=None):
            self._store[key] = value
            return True
        async def delete(self, key):
            self._store.pop(key, None)
            return 1

    async def fake_get_redis():
        return FakeRedis()

    monkeypatch.setattr("app.redis_client.get_redis", fake_get_redis)
    
    async def fake_is_blacklisted(token: str) -> bool:
        return False
    monkeypatch.setattr("app.utils.jwt.is_token_blacklisted", fake_is_blacklisted)

    
    app = FastAPI(title="TestApp")
    app.include_router(auth_routes.router)
    app.include_router(users_routes.router)
    app.include_router(chatrooms_routes.router)

    
    async def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield app, client


@pytest.fixture(scope="function")
async def test_user_token(db_session: AsyncSession) -> Tuple[str, dict]:
    
    from app.models.user import User

    user = User(mobile_number="9998887777", password_hash="hash", full_name="Test User", email="test@example.com", is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = jwt_utils.create_access_token({"sub": str(user.id)})
    return token, {"id": str(user.id), "mobile_number": user.mobile_number}

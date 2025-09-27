from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

def get_async_database_url(url: str) -> str:
    """Convert database URL to use asyncpg driver for async operations."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif not url.startswith("postgresql+asyncpg://"):
        return url
    return url

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600,  
    pool_pre_ping=True,
    connect_args={
        "command_timeout": 60,
        "server_settings": {
            "jit": "off",  
        },
    }
)

# Create async sessionmaker
SessionLocal = async_sessionmaker(
    bind=engine, 
    expire_on_commit=False, 
    class_=AsyncSession,
    autoflush=True,
    autocommit=False
)

# Create Base class for models
Base = declarative_base()

# Dependency to get async database session
async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

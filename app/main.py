from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.middlewares import RateLimitMiddleware
from app.routes import auth, chatrooms, users
from app.config import settings
from app.redis_client import redis_health_check, close_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("Database connected and tables ready")
    except Exception as e:
        print(f"Database connection failed: {e}")
        raise e

    try:
        if await redis_health_check():
            print("Redis connected")
        else:
            print("Redis ping failed")
            raise ConnectionError("Redis ping failed")
    except Exception as e:
        print(f"Redis connection failed: {e}")
        raise e

    yield 

    await close_redis()
    print("Redis connection closed")

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version=settings.version,
    description="FastAPI Backend with PostgreSQL, Redis, and Celery",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    RateLimitMiddleware,
    exclude_paths=[
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/auth",
        "/"
    ]
)


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(chatrooms.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.version,
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.version
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )

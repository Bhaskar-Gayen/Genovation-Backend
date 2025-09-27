import redis.asyncio as aioredis
from app.config import settings

_redis = None

async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True, max_connections=10)
    return _redis

async def redis_health_check() -> bool:
    try:
        redis = await get_redis()
        pong = await redis.ping()
        return pong is True
    except Exception:
        return False

async def close_redis():
    global _redis
    if _redis:
        await _redis.close()
        _redis = None
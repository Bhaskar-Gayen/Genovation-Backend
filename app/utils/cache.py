import json
import functools
import hashlib
from typing import Any, Callable, Awaitable, Optional, TypeVar, Coroutine
from redis_client import get_redis
import asyncio

T = TypeVar("T")

# Utility to generate a cache key based on function name and arguments
def make_cache_key(func: Callable, args: tuple, kwargs: dict) -> str:
    key_base = f"{func.__module__}:{func.__qualname__}:{args}:{kwargs}"
    return hashlib.sha256(key_base.encode()).hexdigest()

# Async cache decorator
def cache(ttl: int = 300):
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            cache_key = make_cache_key(func, args, kwargs)
            redis = await get_redis()
            cached = await redis.get(cache_key)
            if cached is not None:
                return json.loads(cached)
            result = await func(*args, **kwargs)
            await redis.set(cache_key, json.dumps(result, default=str), ex=ttl)
            return result
        return wrapper
    return decorator

# TTL management
async def set_ttl(key: str, ttl: int) -> None:
    redis = await get_redis()
    await redis.expire(key, ttl)

async def get_ttl(key: str) -> Optional[int]:
    redis = await get_redis()
    return await redis.ttl(key)

# Cache invalidation
async def invalidate_cache(key: str) -> None:
    redis = await get_redis()
    await redis.delete(key)

async def invalidate_cache_by_prefix(prefix: str) -> None:
    redis = await get_redis()
    keys = await redis.keys(f"{prefix}*")
    if keys:
        await redis.delete(*keys) 
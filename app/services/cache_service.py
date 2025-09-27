from app.redis_client import get_redis
from typing import Any, Optional
import json

class CacheService:
    @staticmethod
    async def get_user_chatrooms_cache(user_id: str) -> Optional[Any]:
        redis = await get_redis()
        key = f"user:{user_id}:chatrooms"
        data = await redis.get(key)
        if data:
            return json.loads(data)
        return None

    @staticmethod
    async def set_user_chatrooms_cache(user_id: str, data: Any, ttl: int = 600) -> None:
        redis = await get_redis()
        key = f"user:{user_id}:chatrooms"
        await redis.set(key, json.dumps(data, default=str), ex=ttl)

    @staticmethod
    async def invalidate_user_chatrooms_cache(user_id: str) -> None:
        redis = await get_redis()
        key = f"user:{user_id}:chatrooms"
        await redis.delete(key) 
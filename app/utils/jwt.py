from jose import jwt
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from app.config import settings
from app.redis_client import get_redis

SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
REFRESH_TOKEN_EXPIRE_MINUTES = settings.refresh_token_expire_minutes

# Create JWT access token
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# Create refresh token
def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now() + (expires_delta or timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# Verify and decode JWT token
def verify_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

# Check if token payload represents a refresh token
def is_refresh_token_payload(payload: Dict[str, Any]) -> bool:
    return payload is not None and payload.get("type") == "refresh"

# Blacklist token in Redis
async def blacklist_token(token: str, expires_in: int) -> None:
    redis = await get_redis()
    await redis.setex(f"blacklist:{token}", expires_in, "1")

# Check if token is blacklisted
async def is_token_blacklisted(token: str) -> bool:
    redis = await get_redis()
    return await redis.exists(f"blacklist:{token}") == 1 
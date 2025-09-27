from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.utils.jwt import verify_token, is_token_blacklisted
from app.services.user_service import UserService
from app.models.user import User
from functools import wraps
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.redis_client import get_redis

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = credentials.credentials
    payload = verify_token(token)
    if payload is None:
        raise credentials_exception
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    if await is_token_blacklisted(token):
        raise HTTPException(status_code=401, detail="Token is blacklisted")
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    user = await UserService.get_profile(db, user_id=user_id)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# Optional authentication decorator
def optional_auth(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except HTTPException as e:
            if e.status_code == 401:
                return None
            raise
    return wrapper

# Rate limiting middleware
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        redis = await get_redis()
        key = f"rate_limit:{client_ip}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, self.window_seconds)
        if count > self.max_requests:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
        return await call_next(request)

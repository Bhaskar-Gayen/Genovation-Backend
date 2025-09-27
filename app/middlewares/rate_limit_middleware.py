from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.usage_service import UsageService
from app.utils.auth import get_current_user_from_token, validate_token_format
import logging
from typing import Callable

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce rate limiting based on user subscription tier
    Only applies to message-sending endpoints
    """

   
    RATE_LIMITED_ENDPOINTS = [
        "/chatroom/{id}/message", 
    ]

    def __init__(self, app, exclude_paths: list = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/webhook",
            "/auth",
            "/",
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and apply rate limiting if needed"""

        # Skip rate limiting for excluded paths
        if self._should_skip_rate_limiting(request):
            return await call_next(request)

        # Only apply rate limiting to POST requests on message endpoints
        if not self._is_rate_limited_endpoint(request):
            return await call_next(request)

        try:
            # Get user from token
            user = await self._get_user_from_request(request)
            if not user:
                # Let the endpoint handle authentication
                return await call_next(request)

            # Get database session - improved session handling
            db_gen = get_db()
            db = next(db_gen)

            try:
                # Check if user can send message
                can_send, usage_info = UsageService.can_user_send_message(user.id, db)

                if not can_send:
                    return await self._create_rate_limit_response(usage_info)

                # Process the request
                response = await call_next(request)

                # If request was successful (2xx status), increment usage
                if 200 <= response.status_code < 300:
                    UsageService.record_message_sent(user.id)
                    logger.info(f"Message sent by user {user.id}, usage recorded")

                return response

            finally:
                # Properly close the database session
                try:
                    db.close()
                except Exception as e:
                    logger.warning(f"Error closing database session: {e}")

        except Exception as e:
            logger.error(f"Rate limiting middleware error: {e}")
            # Continue with request if middleware fails
            return await call_next(request)

    def _should_skip_rate_limiting(self, request: Request) -> bool:
        """Check if request should skip rate limiting"""
        path = request.url.path

        # Skip excluded paths
        for exclude_path in self.exclude_paths:
            if path.startswith(exclude_path):
                return True

        return False

    def _is_rate_limited_endpoint(self, request: Request) -> bool:
        """Check if request is to a rate-limited endpoint"""
        if request.method != "POST":
            return False

        path = request.url.path

        # Check for message sending endpoints
        if "/message" in path and "/chatroom/" in path:
            return True

        return False

    async def _get_user_from_request(self, request: Request):
        """Extract user from request token"""
        try:
            # Get Authorization header
            auth_header = request.headers.get("Authorization")
            token = validate_token_format(auth_header)

            if not token:
                return None

            # Get database session - improved session handling
            db_gen = get_db()
            db = next(db_gen)

            try:
                user = get_current_user_from_token(token, db)
                return user
            finally:
                # Properly close the database session
                try:
                    db.close()
                except Exception as e:
                    logger.warning(f"Error closing database session in _get_user_from_request: {e}")

        except Exception as e:
            logger.warning(f"Failed to get user from request: {e}")
            return None

    async def _create_rate_limit_response(self, usage_info: dict) -> JSONResponse:
        """Create rate limit exceeded response"""
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "Rate limit exceeded",
                "message": f"Daily limit of {usage_info['daily_limit']} messages reached. Upgrade to Pro for unlimited messages.",
                "details": {
                    "tier": usage_info["tier"],
                    "daily_limit": usage_info["daily_limit"],
                    "daily_used": usage_info["daily_used"],
                    "remaining": usage_info["remaining"]
                },
                "upgrade_info": {
                    "message": "Upgrade to Pro for unlimited messages",
                    "upgrade_endpoint": "/subscribe/pro"
                }
            }
        )


# Standalone rate limiting decorator for specific endpoints
def rate_limit_required(func):
    """
    Decorator to apply rate limiting to specific endpoint functions
    Alternative to middleware for more granular control
    """

    async def wrapper(*args, **kwargs):
        # Extract request and user info from kwargs
        # This assumes the endpoint has access to current_user
        try:
            if "current_user" in kwargs and "db" in kwargs:
                user = kwargs["current_user"]
                db = kwargs["db"]

                # Check rate limit
                can_send, usage_info = SubscriptionService.can_user_send_message(user.id, db)

                if not can_send:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail={
                            "error": "Rate limit exceeded",
                            "message": f"Daily limit of {usage_info['daily_limit']} messages reached.",
                            "usage": usage_info
                        }
                    )

                # Execute the function
                result = await func(*args, **kwargs)

                # Record usage after successful execution
                UsageService.record_message_sent(user.id)

                return result
            else:
                # If required parameters not found, execute without rate limiting
                return await func(*args, **kwargs)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Rate limiting decorator error: {e}")
            # Execute function if rate limiting fails
            return await func(*args, **kwargs)

    return wrapper


# Rate limiting check function for manual use
async def check_rate_limit(user_id: int, db: Session) -> tuple[bool, dict]:
    """
    Manual rate limit check function
    Returns: (can_proceed, usage_info)
    """
    try:
        can_send, usage_info = SubscriptionService.can_user_send_message(user_id, db)
        return can_send, usage_info
    except Exception as e:
        logger.error(f"Rate limit check error: {e}")
        # Allow request if check fails
        return True, {"error": "Rate limit check failed"}


# Usage tracking function for manual use
def record_usage(user_id: int) -> dict:
    """
    Manual usage recording function
    """
    try:
        return UsageService.record_message_sent(user_id)
    except Exception as e:
        logger.error(f"Usage recording error: {e}")
        return {"success": False, "error": str(e)}


# Alternative: Context manager for rate limiting
class RateLimitContext:
    """Context manager for manual rate limiting in endpoints"""

    def __init__(self, user_id: int, db: Session):
        self.user_id = user_id
        self.db = db
        self.can_proceed = False
        self.usage_info = {}

    async def __aenter__(self):
        """Check rate limit on entry"""
        self.can_proceed, self.usage_info = await check_rate_limit(self.user_id, self.db)

        if not self.can_proceed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Rate limit exceeded",
                    "message": f"Daily limit reached.",
                    "usage": self.usage_info
                }
            )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Record usage on successful exit"""
        if exc_type is None:  # No exception occurred
            record_usage(self.user_id)


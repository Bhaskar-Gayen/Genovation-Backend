"""
Custom exception classes for the FastAPI application.
"""
from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class BaseCustomException(HTTPException):
    """Base class for all custom exceptions."""
    
    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: str,
        headers: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.error_code = error_code
        self.user_message = user_message or detail


class AuthenticationError(BaseCustomException):
    """Raised when authentication fails."""
    
    def __init__(
        self,
        detail: str = "Authentication failed",
        error_code: str = "AUTH_001",
        user_message: str = "Please log in to access this resource"
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code=error_code,
            user_message=user_message,
            headers={"WWW-Authenticate": "Bearer"}
        )


class AuthorizationError(BaseCustomException):
    """Raised when user lacks required permissions."""
    
    def __init__(
        self,
        detail: str = "Insufficient permissions",
        error_code: str = "AUTH_002",
        user_message: str = "You don't have permission to access this resource"
    ):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code=error_code,
            user_message=user_message
        )


class ValidationError(BaseCustomException):
    """Raised when request validation fails."""
    
    def __init__(
        self,
        detail: str = "Validation failed",
        error_code: str = "VAL_001",
        user_message: str = "Please check your input and try again",
        field_errors: Optional[Dict[str, str]] = None
    ):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            error_code=error_code,
            user_message=user_message
        )
        self.field_errors = field_errors or {}


class RateLimitError(BaseCustomException):
    """Raised when rate limit is exceeded."""
    
    def __init__(
        self,
        detail: str = "Rate limit exceeded",
        error_code: str = "RATE_001",
        user_message: str = "Too many requests. Please try again later",
        retry_after: Optional[int] = None
    ):
        headers = {"Retry-After": str(retry_after)} if retry_after else None
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            error_code=error_code,
            user_message=user_message,
            headers=headers
        )
        self.retry_after = retry_after



class ReplicateAPIError(BaseCustomException):
    """Raised when Replicate API encounters an error."""
    
    def __init__(
        self,
        detail: str = "Replicate API error",
        error_code: str = "REPLICATE_001",
        user_message: str = "AI service is temporarily unavailable. Please try again later",
        api_error_code: Optional[str] = None
    ):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
            error_code=error_code,
            user_message=user_message
        )
        self.api_error_code = api_error_code


class DatabaseError(BaseCustomException):
    """Raised when database operations fail."""
    
    def __init__(
        self,
        detail: str = "Database operation failed",
        error_code: str = "DB_001",
        user_message: str = "A database error occurred. Please try again"
    ):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            error_code=error_code,
            user_message=user_message
        )


class ExternalServiceError(BaseCustomException):
    """Raised when external service calls fail."""
    
    def __init__(
        self,
        detail: str = "External service error",
        error_code: str = "EXT_001",
        user_message: str = "External service is temporarily unavailable",
        service_name: Optional[str] = None
    ):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
            error_code=error_code,
            user_message=user_message
        )
        self.service_name = service_name


class BusinessLogicError(BaseCustomException):
    """Raised when business logic validation fails."""
    
    def __init__(
        self,
        detail: str = "Business logic error",
        error_code: str = "BIZ_001",
        user_message: str = "Operation cannot be completed due to business rules"
    ):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code=error_code,
            user_message=user_message
        )

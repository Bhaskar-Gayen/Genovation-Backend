"""
Global error handler middleware for FastAPI application.
Provides consistent error response format and comprehensive logging.
"""
import logging
import traceback
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Union
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError as PydanticValidationError

from app.exceptions.custom_exceptions import (
    BaseCustomException,
    AuthenticationError,
    AuthorizationError,
    ValidationError,
    ReplicateAPIError,
    DatabaseError,
    ExternalServiceError,
    BusinessLogicError
)

# Configure logger
logger = logging.getLogger(__name__)


class ErrorResponse:
    """Standard error response format."""
    
    def __init__(
        self,
        error_code: str,
        message: str,
        user_message: str,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        timestamp: Optional[str] = None
    ):
        self.error_code = error_code
        self.message = message
        self.user_message = user_message
        self.details = details or {}
        self.request_id = request_id or str(uuid.uuid4())
        self.timestamp = timestamp or datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        return {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "user_message": self.user_message,
                "details": self.details,
                "request_id": self.request_id,
                "timestamp": self.timestamp
            }
        }


class GlobalErrorHandler(BaseHTTPMiddleware):
    """Global error handling middleware."""
    
    def __init__(self, app, debug: bool = False):
        super().__init__(app)
        self.debug = debug
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and handle any exceptions."""
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            return await self._handle_exception(request, exc, request_id)
    
    async def _handle_exception(
        self, 
        request: Request, 
        exc: Exception, 
        request_id: str
    ) -> JSONResponse:
        """Handle different types of exceptions."""
        
        # Log the exception
        await self._log_exception(request, exc, request_id)
        
        # Handle custom exceptions
        if isinstance(exc, BaseCustomException):
            return await self._handle_custom_exception(exc, request_id)
        
        # Handle FastAPI HTTPException
        elif isinstance(exc, HTTPException):
            return await self._handle_http_exception(exc, request_id)
        
        # Handle validation errors
        elif isinstance(exc, (RequestValidationError, PydanticValidationError)):
            return await self._handle_validation_exception(exc, request_id)
        
        # Handle database errors
        elif isinstance(exc, SQLAlchemyError):
            return await self._handle_database_exception(exc, request_id)
        
        # Handle unexpected errors
        else:
            return await self._handle_unexpected_exception(exc, request_id)
    
    async def _handle_custom_exception(
        self, 
        exc: BaseCustomException, 
        request_id: str
    ) -> JSONResponse:
        """Handle custom application exceptions."""
        error_response = ErrorResponse(
            error_code=exc.error_code,
            message=exc.detail,
            user_message=exc.user_message,
            details=getattr(exc, 'field_errors', {}),
            request_id=request_id
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.to_dict(),
            headers=exc.headers
        )
    
    async def _handle_http_exception(
        self, 
        exc: HTTPException, 
        request_id: str
    ) -> JSONResponse:
        """Handle FastAPI HTTPException."""
        # Map status codes to error codes
        error_code_map = {
            400: "HTTP_400",
            401: "HTTP_401",
            403: "HTTP_403",
            404: "HTTP_404",
            405: "HTTP_405",
            409: "HTTP_409",
            422: "HTTP_422",
            429: "HTTP_429",
            500: "HTTP_500",
            502: "HTTP_502",
            503: "HTTP_503"
        }
        
        error_code = error_code_map.get(exc.status_code, f"HTTP_{exc.status_code}")
        
        error_response = ErrorResponse(
            error_code=error_code,
            message=str(exc.detail),
            user_message=self._get_user_friendly_message(exc.status_code),
            request_id=request_id
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.to_dict(),
            headers=exc.headers
        )
    
    async def _handle_validation_exception(
        self, 
        exc: Union[RequestValidationError, PydanticValidationError], 
        request_id: str
    ) -> JSONResponse:
        """Handle validation errors."""
        field_errors = {}
        
        if isinstance(exc, RequestValidationError):
            for error in exc.errors():
                field_name = ".".join(str(loc) for loc in error["loc"])
                field_errors[field_name] = error["msg"]
        
        error_response = ErrorResponse(
            error_code="VAL_001",
            message="Request validation failed",
            user_message="Please check your input and try again",
            details={"field_errors": field_errors},
            request_id=request_id
        )
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response.to_dict()
        )
    
    async def _handle_database_exception(
        self, 
        exc: SQLAlchemyError, 
        request_id: str
    ) -> JSONResponse:
        """Handle database errors."""
        error_response = ErrorResponse(
            error_code="DB_001",
            message="Database operation failed",
            user_message="A database error occurred. Please try again",
            details={"db_error": str(exc) if self.debug else "Database error"},
            request_id=request_id
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.to_dict()
        )
    
    async def _handle_unexpected_exception(
        self, 
        exc: Exception, 
        request_id: str
    ) -> JSONResponse:
        """Handle unexpected errors."""
        error_response = ErrorResponse(
            error_code="SYS_001",
            message="Internal server error",
            user_message="An unexpected error occurred. Please try again later",
            details={"error": str(exc) if self.debug else "Internal server error"},
            request_id=request_id
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.to_dict()
        )
    
    async def _log_exception(
        self, 
        request: Request, 
        exc: Exception, 
        request_id: str
    ) -> None:
        """Log exception details."""
        log_data = {
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown"),
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
        }
        
        # Add user information if available
        if hasattr(request.state, 'user'):
            log_data["user_id"] = getattr(request.state.user, 'id', None)
        
        # Log based on exception severity
        if isinstance(exc, (BaseCustomException, HTTPException)):
            if exc.status_code >= 500:
                logger.error(
                    f"Server error: {exc}",
                    extra=log_data,
                    exc_info=True
                )
            elif exc.status_code >= 400:
                logger.warning(
                    f"Client error: {exc}",
                    extra=log_data
                )
        else:
            logger.error(
                f"Unexpected error: {exc}",
                extra=log_data,
                exc_info=True
            )
    
    def _get_user_friendly_message(self, status_code: int) -> str:
        """Get user-friendly message for HTTP status codes."""
        messages = {
            400: "Bad request. Please check your input",
            401: "Authentication required. Please log in",
            403: "Access denied. You don't have permission",
            404: "Resource not found",
            405: "Method not allowed",
            409: "Conflict. Resource already exists",
            422: "Invalid input. Please check your data",
            429: "Too many requests. Please try again later",
            500: "Internal server error. Please try again later",
            502: "Service temporarily unavailable",
            503: "Service temporarily unavailable"
        }
        return messages.get(status_code, "An error occurred")


# Exception handlers for specific cases
async def custom_exception_handler(request: Request, exc: BaseCustomException):
    """Handler for custom exceptions."""
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
    
    error_response = ErrorResponse(
        error_code=exc.error_code,
        message=exc.detail,
        user_message=exc.user_message,
        details=getattr(exc, 'field_errors', {}),
        request_id=request_id
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.to_dict(),
        headers=exc.headers
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handler for validation exceptions."""
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
    
    field_errors = {}
    for error in exc.errors():
        field_name = ".".join(str(loc) for loc in error["loc"])
        field_errors[field_name] = error["msg"]
    
    error_response = ErrorResponse(
        error_code="VAL_001",
        message="Request validation failed",
        user_message="Please check your input and try again",
        details={"field_errors": field_errors},
        request_id=request_id
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.to_dict()
    )

"""
Comprehensive logging middleware for FastAPI application.
Provides request/response logging, performance timing, user activity tracking,
API usage analytics, and security event logging.
"""
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Set
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse
import asyncio

# Configure loggers
request_logger = logging.getLogger("request")
performance_logger = logging.getLogger("performance")
security_logger = logging.getLogger("security")
analytics_logger = logging.getLogger("analytics")

# Sensitive headers to exclude from logging
SENSITIVE_HEADERS = {
    "authorization", "cookie", "x-api-key", "x-auth-token",
    "authentication", "proxy-authorization"
}

# Sensitive fields to exclude from request/response body logging
SENSITIVE_FIELDS = {
    "password", "token", "secret", "key", "authorization",
    "credit_card", "ssn", "social_security"
}


class LoggingMiddleware(BaseHTTPMiddleware):
    """Comprehensive logging middleware."""
    
    def __init__(
        self,
        app,
        log_requests: bool = True,
        log_responses: bool = True,
        log_request_body: bool = True,
        log_response_body: bool = False,
        max_body_size: int = 1024 * 10,  # 10KB
        exclude_paths: Optional[Set[str]] = None,
        include_headers: bool = True
    ):
        super().__init__(app)
        self.log_requests = log_requests
        self.log_responses = log_responses
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.max_body_size = max_body_size
        self.exclude_paths = exclude_paths or {"/health", "/metrics", "/favicon.ico"}
        self.include_headers = include_headers
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and log relevant information."""
        # Skip logging for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # Generate request ID if not exists
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        request.state.request_id = request_id
        
        # Start timing
        start_time = time.time()
        
        # Log request
        if self.log_requests:
            await self._log_request(request, request_id)
        
        # Log security events
        await self._log_security_events(request, request_id)
        
        # Process request
        try:
            response = await call_next(request)
        except Exception as exc:
            # Log exception and re-raise
            await self._log_exception(request, exc, request_id, time.time() - start_time)
            raise
        
        # Calculate response time
        process_time = time.time() - start_time
        
        # Add timing header
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-Request-ID"] = request_id
        
        # Log response
        if self.log_responses:
            await self._log_response(request, response, request_id, process_time)
        
        # Log performance metrics
        await self._log_performance(request, response, request_id, process_time)
        
        # Log analytics
        await self._log_analytics(request, response, request_id, process_time)
        
        return response
    
    async def _log_request(self, request: Request, request_id: str) -> None:
        """Log incoming request details."""
        log_data = {
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("user-agent", ""),
            "referer": request.headers.get("referer", ""),
            "content_type": request.headers.get("content-type", ""),
            "content_length": request.headers.get("content-length", "0")
        }
        
        # Add headers (excluding sensitive ones)
        if self.include_headers:
            log_data["headers"] = self._filter_sensitive_headers(dict(request.headers))
        
        # Add user information if available
        if hasattr(request.state, 'user'):
            user = request.state.user
            log_data["user"] = {
                "id": getattr(user, 'id', None),
                "email": getattr(user, 'email', None),
                "role": getattr(user, 'role', None)
            }
        
        # Add request body if enabled and appropriate
        if self.log_request_body and self._should_log_body(request):
            try:
                body = await self._get_request_body(request)
                if body:
                    log_data["body"] = self._filter_sensitive_data(body)
            except Exception as e:
                log_data["body_error"] = str(e)
        
        request_logger.info("Incoming request", extra=log_data)
    
    async def _log_response(
        self, 
        request: Request, 
        response: Response, 
        request_id: str, 
        process_time: float
    ) -> None:
        """Log outgoing response details."""
        log_data = {
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
            "method": request.method,
            "url": str(request.url),
            "status_code": response.status_code,
            "process_time": process_time,
            "response_size": len(response.body) if hasattr(response, 'body') else 0
        }
        
        # Add response headers (excluding sensitive ones)
        if self.include_headers:
            log_data["headers"] = self._filter_sensitive_headers(dict(response.headers))
        
        # Add response body if enabled and appropriate
        if self.log_response_body and self._should_log_response_body(response):
            try:
                body = await self._get_response_body(response)
                if body:
                    log_data["body"] = self._filter_sensitive_data(body)
            except Exception as e:
                log_data["body_error"] = str(e)
        
        # Determine log level based on status code
        if response.status_code >= 500:
            request_logger.error("Response sent", extra=log_data)
        elif response.status_code >= 400:
            request_logger.warning("Response sent", extra=log_data)
        else:
            request_logger.info("Response sent", extra=log_data)
    
    async def _log_performance(
        self, 
        request: Request, 
        response: Response, 
        request_id: str, 
        process_time: float
    ) -> None:
        """Log performance metrics."""
        log_data = {
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "process_time": process_time,
            "slow_request": process_time > 1.0,  # Flag slow requests
        }
        
        # Add user information if available
        if hasattr(request.state, 'user'):
            log_data["user_id"] = getattr(request.state.user, 'id', None)
        
        performance_logger.info("Performance metrics", extra=log_data)
        
        # Log slow requests separately
        if process_time > 1.0:
            performance_logger.warning(
                f"Slow request detected: {process_time:.2f}s",
                extra=log_data
            )
    
    async def _log_security_events(self, request: Request, request_id: str) -> None:
        """Log security-related events."""
        security_events = []
        
        # Check for suspicious patterns
        user_agent = request.headers.get("user-agent", "").lower()
        if any(bot in user_agent for bot in ["bot", "crawler", "spider", "scraper"]):
            security_events.append("bot_detected")
        
        # Check for suspicious IPs (this could be enhanced with IP reputation services)
        client_ip = self._get_client_ip(request)
        if self._is_suspicious_ip(client_ip):
            security_events.append("suspicious_ip")
        
        # Check for SQL injection patterns in query parameters
        query_string = str(request.url.query).lower()
        sql_patterns = ["union", "select", "drop", "insert", "delete", "update", "--", ";"]
        if any(pattern in query_string for pattern in sql_patterns):
            security_events.append("potential_sql_injection")
        
        # Check for XSS patterns
        if any(pattern in query_string for pattern in ["<script", "javascript:", "onerror="]):
            security_events.append("potential_xss")
        
        # Log security events if any found
        if security_events:
            log_data = {
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat(),
                "client_ip": client_ip,
                "method": request.method,
                "url": str(request.url),
                "user_agent": request.headers.get("user-agent", ""),
                "events": security_events
            }
            
            security_logger.warning("Security events detected", extra=log_data)
    
    async def _log_analytics(
        self, 
        request: Request, 
        response: Response, 
        request_id: str, 
        process_time: float
    ) -> None:
        """Log analytics data for API usage tracking."""
        log_data = {
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
            "method": request.method,
            "endpoint": request.url.path,
            "status_code": response.status_code,
            "process_time": process_time,
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("user-agent", ""),
            "referer": request.headers.get("referer", ""),
        }
        
        # Add user information for usage tracking
        if hasattr(request.state, 'user'):
            user = request.state.user
            log_data["user_id"] = getattr(user, 'id', None)
            log_data["user_role"] = getattr(user, 'role', None)
        
        # Add API-specific metrics
        if request.url.path.startswith("/api/"):
            log_data["api_version"] = self._extract_api_version(request.url.path)
            log_data["api_endpoint"] = self._normalize_endpoint(request.url.path)
        
        analytics_logger.info("API usage", extra=log_data)
    
    async def _log_exception(
        self, 
        request: Request, 
        exc: Exception, 
        request_id: str, 
        process_time: float
    ) -> None:
        """Log exception details."""
        log_data = {
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
            "method": request.method,
            "url": str(request.url),
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "process_time": process_time,
            "client_ip": self._get_client_ip(request)
        }
        
        if hasattr(request.state, 'user'):
            log_data["user_id"] = getattr(request.state.user, 'id', None)
        
        request_logger.error("Request exception", extra=log_data, exc_info=True)
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address, considering proxies."""
        # Check for forwarded headers
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def _filter_sensitive_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Filter out sensitive headers."""
        return {
            key: value if key.lower() not in SENSITIVE_HEADERS else "[REDACTED]"
            for key, value in headers.items()
        }
    
    def _filter_sensitive_data(self, data: Any) -> Any:
        """Filter sensitive data from request/response bodies."""
        if isinstance(data, dict):
            return {
                key: "[REDACTED]" if key.lower() in SENSITIVE_FIELDS else self._filter_sensitive_data(value)
                for key, value in data.items()
            }
        elif isinstance(data, list):
            return [self._filter_sensitive_data(item) for item in data]
        else:
            return data
    
    def _should_log_body(self, request: Request) -> bool:
        """Determine if request body should be logged."""
        content_type = request.headers.get("content-type", "")
        content_length = int(request.headers.get("content-length", "0"))
        
        # Don't log large bodies
        if content_length > self.max_body_size:
            return False
        
        # Only log JSON and form data
        return any(ct in content_type for ct in ["application/json", "application/x-www-form-urlencoded"])
    
    def _should_log_response_body(self, response: Response) -> bool:
        """Determine if response body should be logged."""
        content_type = response.headers.get("content-type", "")
        
        # Only log JSON responses
        return "application/json" in content_type
    
    async def _get_request_body(self, request: Request) -> Optional[Dict[str, Any]]:
        """Get request body as dictionary."""
        try:
            if request.headers.get("content-type", "").startswith("application/json"):
                body = await request.body()
                if body:
                    return json.loads(body.decode())
        except Exception:
            pass
        return None
    
    async def _get_response_body(self, response: Response) -> Optional[Dict[str, Any]]:
        """Get response body as dictionary."""
        try:
            if hasattr(response, 'body') and response.body:
                return json.loads(response.body.decode())
        except Exception:
            pass
        return None
    
    def _is_suspicious_ip(self, ip: str) -> bool:
        """Check if IP is suspicious (placeholder implementation)."""
        # This could be enhanced with IP reputation services
        suspicious_patterns = ["127.0.0.1", "localhost"]
        return any(pattern in ip for pattern in suspicious_patterns)
    
    def _extract_api_version(self, path: str) -> Optional[str]:
        """Extract API version from path."""
        parts = path.split("/")
        for part in parts:
            if part.startswith("v") and part[1:].isdigit():
                return part
        return None
    
    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path for analytics."""
        # Replace IDs with placeholders for better grouping
        import re
        # Replace UUIDs
        path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{id}', path)
        # Replace numeric IDs
        path = re.sub(r'/\d+', '/{id}', path)
        return path


class UserActivityLogger:
    """Specialized logger for user activity tracking."""
    
    @staticmethod
    async def log_user_action(
        user_id: str,
        action: str,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> None:
        """Log user activity."""
        log_data = {
            "user_id": user_id,
            "action": action,
            "resource": resource,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request_id
        }
        
        analytics_logger.info("User activity", extra=log_data)
    
    @staticmethod
    async def log_authentication_event(
        user_id: Optional[str],
        event_type: str,
        success: bool,
        client_ip: str,
        user_agent: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log authentication events."""
        log_data = {
            "user_id": user_id,
            "event_type": event_type,
            "success": success,
            "client_ip": client_ip,
            "user_agent": user_agent,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        security_logger.info("Authentication event", extra=log_data)

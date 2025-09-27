"""
Enhanced FastAPI application with comprehensive security middleware and production configurations.
"""
import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import redis.asyncio as redis

from database import engine, Base, get_db
from routes import auth, chatrooms, users
from config import settings

# Import middleware components
from middlewares import (
    GlobalErrorHandler,
    LoggingMiddleware,
    ValidationMiddleware,
    ValidationConfig,
    custom_exception_handler,
    validation_exception_handler
)

# Import security middleware
from middlewares.security_middleware import (
    SecurityHeadersMiddleware,
    HTTPSRedirectMiddleware,
    TrustedHostMiddleware,
    RequestIDMiddleware,
    IPRateLimitMiddleware,
    AuthTokenValidationMiddleware,
    ContentLengthValidationMiddleware
)

# Import custom exceptions
from exceptions import BaseCustomException

# Import health checks
from utils.health_checks import health_manager

# Import security configuration
from config.security_config import security_settings, logging_settings

# Configure logging based on environment
def setup_logging():
    """Setup logging configuration based on environment."""
    log_level = getattr(logging, logging_settings.log_level.upper(), logging.INFO)
    
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=logging_settings.log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                logging_settings.log_file_path,
                maxBytes=logging_settings.log_file_max_size,
                backupCount=logging_settings.log_file_backup_count
            ) if logging_settings.enable_file_logging else logging.NullHandler()
        ]
    )
    
    # Set specific logger levels
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.debug else logging.WARNING
    )

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Global Redis client for rate limiting
redis_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with startup and shutdown events."""
    # Startup
    logger.info("Starting up FastAPI application...")
    
    try:
        # Initialize database
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully")
        
        # Initialize Redis connection for rate limiting
        global redis_client
        redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
            retry_on_timeout=True
        )
        await redis_client.ping()
        logger.info("Redis connection established successfully")
        
        # Log startup configuration
        logger.info(f"Application started in {security_settings.environment.value} mode")
        logger.info(f"Debug mode: {security_settings.debug}")
        logger.info(f"HTTPS enforcement: {security_settings.force_https}")
        logger.info(f"Rate limiting: {security_settings.rate_limit_enabled}")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down FastAPI application...")
    
    try:
        # Close Redis connection
        if redis_client:
            await redis_client.close()
        logger.info("Redis connection closed")
        
        # Close database connections
        await engine.dispose()
        logger.info("Database connections closed")
        
    except Exception as e:
        logger.error(f"Shutdown error: {e}")

# Create FastAPI app with enhanced configuration
app = FastAPI(
    title=f"{settings.app_name} - Enhanced",
    debug=security_settings.debug,
    version=settings.version,
    description="FastAPI Backend with Comprehensive Security Middleware System",
    lifespan=lifespan,
    docs_url="/docs" if not security_settings.is_production() else None,
    redoc_url="/redoc" if not security_settings.is_production() else None,
    openapi_url="/openapi.json" if not security_settings.is_production() else None
)

# Configure validation middleware
validation_config = ValidationConfig(
    max_request_size=security_settings.max_request_size,
    max_json_depth=security_settings.max_json_depth,
    max_array_length=security_settings.max_array_length,
    max_string_length=security_settings.max_string_length,
    enable_xss_protection=security_settings.enable_xss_protection,
    enable_sql_injection_protection=security_settings.enable_sql_injection_protection,
    enable_input_sanitization=security_settings.enable_input_sanitization,
    sanitize_html=security_settings.sanitize_html
)

# Add middleware in correct order (LIFO - Last In, First Out)
# The order is crucial as middleware executes in reverse order of addition

# 1. CORS middleware (executed first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=security_settings.get_cors_origins_for_environment(),
    allow_credentials=security_settings.cors_allow_credentials,
    allow_methods=security_settings.cors_allow_methods,
    allow_headers=security_settings.cors_allow_headers,
    expose_headers=security_settings.cors_expose_headers,
)

# 2. Security headers middleware
app.add_middleware(
    SecurityHeadersMiddleware,
    hsts_max_age=security_settings.hsts_max_age,
    hsts_include_subdomains=security_settings.hsts_include_subdomains,
    hsts_preload=security_settings.hsts_preload,
    frame_options=security_settings.frame_options,
    csp_policy=security_settings.get_content_security_policy()
)

# 3. HTTPS redirect middleware (production only)
if security_settings.force_https:
    app.add_middleware(
        HTTPSRedirectMiddleware,
        enabled=security_settings.force_https,
        permanent=security_settings.https_redirect_permanent
    )

# 4. Trusted host validation
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=security_settings.trusted_hosts,
    allow_any=security_settings.allow_any_host
)

# 5. Request ID generation
app.add_middleware(RequestIDMiddleware)

# 6. Content length validation
app.add_middleware(
    ContentLengthValidationMiddleware,
    max_content_length=security_settings.max_request_size,
    max_multipart_length=security_settings.max_multipart_size
)

# 7. IP-based rate limiting
if security_settings.rate_limit_enabled:
    app.add_middleware(
        IPRateLimitMiddleware,
        requests_per_minute=security_settings.rate_limit_requests_per_minute,
        requests_per_hour=security_settings.rate_limit_requests_per_hour,
        requests_per_day=security_settings.rate_limit_requests_per_day,
        burst_limit=security_settings.rate_limit_burst_limit,
        whitelist_ips=security_settings.rate_limit_whitelist_ips,
        blacklist_ips=security_settings.rate_limit_blacklist_ips,
        redis_client=redis_client
    )

# 8. Authentication token validation
app.add_middleware(
    AuthTokenValidationMiddleware,
    require_fresh_token=security_settings.require_fresh_tokens,
    max_token_age=security_settings.max_token_age_seconds
)

# 9. Global error handler
app.add_middleware(
    GlobalErrorHandler,
    debug=security_settings.debug
)

# 10. Logging middleware
app.add_middleware(
    LoggingMiddleware,
    log_requests=security_settings.log_requests,
    log_responses=security_settings.log_responses,
    log_request_body=security_settings.log_request_body,
    log_response_body=security_settings.log_response_body,
    max_body_size=security_settings.max_log_body_size,
    exclude_paths={"/health", "/healthz", "/metrics", "/favicon.ico"},
    include_headers=True
)

# 11. Validation middleware (should be last to validate first)
app.add_middleware(
    ValidationMiddleware,
    config=validation_config
)

# Add exception handlers
app.add_exception_handler(BaseCustomException, custom_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(chatrooms.router, prefix="/api/v1")

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with system information."""
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.version,
        "status": "running",
        "environment": security_settings.environment.value,
        "security": {
            "https_enforced": security_settings.force_https,
            "rate_limiting": security_settings.rate_limit_enabled,
            "input_validation": True,
            "security_headers": True,
            "request_logging": security_settings.log_requests
        },
        "features": {
            "async_database": True,
            "connection_pooling": True,
            "comprehensive_logging": True,
            "health_monitoring": True
        }
    }

# Basic health check endpoint
@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    try:
        health_result = await health_manager.run_basic_checks()
        
        status_code = 200 if health_result["status"] == "healthy" else 503
        
        return JSONResponse(
            status_code=status_code,
            content={
                "status": health_result["status"],
                "service": settings.app_name,
                "version": settings.version,
                "timestamp": health_result["timestamp"],
                "checks": health_result["checks"]
            }
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": settings.app_name,
                "version": settings.version,
                "error": "Health check failed"
            }
        )

# Detailed health check endpoint
@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with all services."""
    try:
        health_result = await health_manager.run_all_checks(
            timeout=security_settings.health_check_timeout
        )
        
        status_code = 200 if health_result["status"] == "healthy" else 503
        
        return JSONResponse(
            status_code=status_code,
            content=health_result
        )
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": settings.app_name,
                "version": settings.version,
                "error": "Detailed health check failed"
            }
        )

# Readiness probe endpoint
@app.get("/ready")
async def readiness_check():
    """Kubernetes readiness probe endpoint."""
    try:
        # Check critical services only
        async with get_db() as db:
            await db.execute("SELECT 1")
        
        return {"status": "ready", "service": settings.app_name}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "error": str(e)}
        )

# Liveness probe endpoint
@app.get("/live")
async def liveness_check():
    """Kubernetes liveness probe endpoint."""
    return {"status": "alive", "service": settings.app_name}

# Metrics endpoint (basic)
@app.get("/metrics")
async def metrics():
    """Basic metrics endpoint."""
    try:
        # This could be enhanced with Prometheus metrics
        return {
            "service": settings.app_name,
            "version": settings.version,
            "environment": security_settings.environment.value,
            "uptime": "calculated_uptime_here",  # Implement uptime calculation
            "requests_total": "implement_counter",  # Implement request counter
            "errors_total": "implement_error_counter"  # Implement error counter
        }
    except Exception as e:
        logger.error(f"Metrics endpoint failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Metrics unavailable"}
        )

# Security test endpoints (development only)
if security_settings.is_development():
    @app.get("/test/security/error")
    async def test_error_handling():
        """Test error handling middleware."""
        from exceptions import ValidationError
        raise ValidationError(
            detail="This is a test validation error",
            error_code="TEST_001",
            user_message="This is a test error for development"
        )
    
    @app.post("/test/security/validation")
    async def test_validation(data: Dict[str, Any]):
        """Test validation middleware."""
        return {
            "message": "Validation passed successfully",
            "data": data,
            "security_checks": "passed"
        }
    
    @app.get("/test/security/rate-limit")
    async def test_rate_limit():
        """Test rate limiting."""
        return {"message": "Rate limit test endpoint"}

if __name__ == "__main__":
    import uvicorn
    
    # Production-ready uvicorn configuration
    uvicorn_config = {
        "app": "main_enhanced:app",
        "host": settings.host,
        "port": settings.port,
        "reload": security_settings.debug and security_settings.is_development(),
        "log_level": logging_settings.log_level.lower(),
        "access_log": True,
        "use_colors": security_settings.is_development(),
        "server_header": False,  # Don't expose server information
        "date_header": False,    # Don't expose date header
    }
    
    # SSL configuration for production
    if security_settings.force_https and security_settings.is_production():
        ssl_keyfile = os.getenv("SSL_KEYFILE")
        ssl_certfile = os.getenv("SSL_CERTFILE")
        
        if ssl_keyfile and ssl_certfile:
            uvicorn_config.update({
                "ssl_keyfile": ssl_keyfile,
                "ssl_certfile": ssl_certfile,
                "ssl_version": 2,  # TLS 1.2+
                "ssl_cert_reqs": 2,  # CERT_REQUIRED
            })
            logger.info("SSL/TLS configuration enabled")
    
    logger.info(f"Starting server with configuration: {uvicorn_config}")
    uvicorn.run(**uvicorn_config)

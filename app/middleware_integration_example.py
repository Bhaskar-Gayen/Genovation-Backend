"""
Example integration of comprehensive middleware system with FastAPI.
This file shows how to properly integrate all middleware components.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from database import engine, Base
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

# Import custom exceptions
from exceptions import BaseCustomException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

# Create separate loggers for different purposes
request_logger = logging.getLogger("request")
performance_logger = logging.getLogger("performance")
security_logger = logging.getLogger("security")
analytics_logger = logging.getLogger("analytics")

# Configure validation
validation_config = ValidationConfig(
    max_request_size=10 * 1024 * 1024,  
    max_json_depth=10,
    max_array_length=1000,
    max_string_length=10000,
    enable_xss_protection=True,
    enable_sql_injection_protection=True,
    enable_input_sanitization=True,
    sanitize_html=True,
    validate_responses=False  
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    pass

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version=settings.version,
    description="FastAPI Backend with Comprehensive Middleware System",
    lifespan=lifespan
)

# Add middleware in the correct order (LIFO - Last In, First Out)
# The order matters! Middleware is executed in reverse order of addition

# 1. CORS middleware (should be last to be executed first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Global error handler (should catch all errors)
app.add_middleware(
    GlobalErrorHandler,
    debug=settings.debug
)

# 3. Logging middleware (should log all requests/responses)
app.add_middleware(
    LoggingMiddleware,
    log_requests=True,
    log_responses=True,
    log_request_body=True,
    log_response_body=False,  # Set to True if needed, but be careful with sensitive data
    max_body_size=1024 * 10,  # 10KB
    exclude_paths={"/health", "/metrics", "/favicon.ico"},
    include_headers=True
)

# 4. Validation middleware (should validate before processing)
app.add_middleware(
    ValidationMiddleware,
    config=validation_config
)

# Add exception handlers
app.add_exception_handler(BaseCustomException, custom_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(chatrooms.router)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.version,
        "status": "running",
        "middleware": {
            "error_handling": "enabled",
            "logging": "enabled",
            "validation": "enabled",
            "security": "enabled"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.version,
        "middleware_status": "operational"
    }

@app.get("/test-error")
async def test_error():
    """Test endpoint for error handling"""
    from exceptions import ValidationError
    raise ValidationError(
        detail="This is a test error",
        error_code="TEST_001",
        user_message="This is a test error for demonstration"
    )

@app.post("/test-validation")
async def test_validation(data: dict):
    """Test endpoint for validation middleware"""
    return {"message": "Validation passed", "data": data}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "middleware_integration_example:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )

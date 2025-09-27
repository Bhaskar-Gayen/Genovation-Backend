# Comprehensive Middleware System

This FastAPI application includes a comprehensive middleware system that provides error handling, logging, validation, and security features.

## Components

### 1. Custom Exceptions (`exceptions/custom_exceptions.py`)

Custom exception classes with proper error codes and user-friendly messages:

- `AuthenticationError` - Authentication failures (401)
- `AuthorizationError` - Permission issues (403)
- `ValidationError` - Input validation failures (422)
- `RateLimitError` - Rate limit exceeded (429)
- `ReplicateAPIError` - AI service errors (503)
- `DatabaseError` - Database operation failures (500)
- `ExternalServiceError` - External service failures (503)
- `BusinessLogicError` - Business rule violations (400)

### 2. Error Handler Middleware (`middlewares/error_handler.py`)

Global exception handling with:
- Consistent error response format
- Request ID tracking
- Comprehensive error logging
- User-friendly error messages
- HTTP status code mapping

**Error Response Format:**
```json
{
  "error": {
    "code": "AUTH_001",
    "message": "Authentication failed",
    "user_message": "Please log in to access this resource",
    "details": {},
    "request_id": "uuid-here",
    "timestamp": "2023-07-23T02:50:51Z"
  }
}
```

### 3. Logging Middleware (`middlewares/logging_middleware.py`)

Comprehensive logging system with:
- Request/response logging
- Performance timing
- User activity tracking
- API usage analytics
- Security event logging
- Sensitive data filtering

**Log Categories:**
- `request` - Request/response logs
- `performance` - Performance metrics
- `security` - Security events
- `analytics` - API usage analytics

### 4. Validation Middleware (`middlewares/validation_middleware.py`)

Input validation and security with:
- Request size limits
- Content-type validation
- XSS protection
- SQL injection protection
- Input sanitization
- JSON depth limits
- Array length limits

**Configuration Options:**
```python
ValidationConfig(
    max_request_size=10 * 1024 * 1024,  # 10MB
    max_json_depth=10,
    max_array_length=1000,
    max_string_length=10000,
    enable_xss_protection=True,
    enable_sql_injection_protection=True,
    enable_input_sanitization=True,
    sanitize_html=True
)
```

## Integration

### Basic Integration

```python
from fastapi import FastAPI
from middlewares import (
    GlobalErrorHandler,
    LoggingMiddleware,
    ValidationMiddleware,
    ValidationConfig
)
from exceptions import BaseCustomException

app = FastAPI()

# Add middleware (order matters - LIFO)
app.add_middleware(GlobalErrorHandler, debug=False)
app.add_middleware(LoggingMiddleware)
app.add_middleware(ValidationMiddleware, config=ValidationConfig())

# Add exception handlers
app.add_exception_handler(BaseCustomException, custom_exception_handler)
```

### Complete Integration Example

See `middleware_integration_example.py` for a complete integration example with proper configuration.

## Usage Examples

### Raising Custom Exceptions

```python
from exceptions import ValidationError, AuthenticationError

# Validation error with field details
raise ValidationError(
    detail="Invalid input data",
    error_code="VAL_001",
    user_message="Please check your input",
    field_errors={"email": "Invalid email format"}
)

# Authentication error
raise AuthenticationError(
    detail="Token expired",
    user_message="Please log in again"
)
```

### User Activity Logging

```python
from middlewares import UserActivityLogger

await UserActivityLogger.log_user_action(
    user_id="user123",
    action="create_chatroom",
    resource="chatroom",
    details={"chatroom_id": "room456"},
    request_id=request.state.request_id
)
```

### Manual Validation

```python
from middlewares import validate_email, sanitize_filename

# Validate email
if not validate_email("user@example.com"):
    raise ValidationError("Invalid email format")

# Sanitize filename
safe_filename = sanitize_filename("../../../etc/passwd")
```

## Security Features

### XSS Protection
- Detects script tags, event handlers, and dangerous URLs
- HTML sanitization with allowed tags/attributes
- HTML entity encoding

### SQL Injection Protection
- Detects common SQL injection patterns
- Validates query parameters and request bodies
- Logs suspicious activity

### Input Sanitization
- Recursive data structure sanitization
- String length limits
- HTML tag filtering
- Special character handling

## Logging Configuration

### File-based Logging

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
```

### Structured Logging

All logs include structured data for easy parsing:
- Request ID for tracing
- User information when available
- Performance metrics
- Security event details

## Performance Considerations

### Request Size Limits
- Default: 10MB maximum request size
- Configurable per endpoint if needed
- Early rejection of oversized requests

### Logging Performance
- Async logging operations
- Configurable body logging limits
- Sensitive data filtering
- Excluded paths for health checks

### Validation Performance
- Early validation failures
- Recursive depth limits
- Efficient pattern matching
- Configurable security checks

## Monitoring and Alerting

### Key Metrics to Monitor
- Error rates by endpoint
- Response times
- Security events
- Rate limit hits
- User activity patterns

### Log Analysis
- Use structured logs for analysis
- Monitor error patterns
- Track performance degradation
- Security incident detection

## Best Practices

1. **Error Handling**
   - Always provide user-friendly messages
   - Log detailed technical information
   - Use appropriate HTTP status codes
   - Include request IDs for tracing

2. **Logging**
   - Don't log sensitive information
   - Use appropriate log levels
   - Include context information
   - Monitor log volume

3. **Validation**
   - Validate at the boundary
   - Sanitize user input
   - Use whitelist approaches
   - Fail securely

4. **Security**
   - Regular security reviews
   - Update security patterns
   - Monitor for new threats
   - Implement defense in depth

## Troubleshooting

### Common Issues

1. **Middleware Order**
   - Middleware executes in reverse order of addition
   - Error handler should be added last
   - CORS should be first

2. **Logging Performance**
   - Disable body logging in production if needed
   - Use appropriate log levels
   - Monitor disk space

3. **Validation Errors**
   - Check configuration limits
   - Review security patterns
   - Verify input formats

### Debug Mode

Enable debug mode for detailed error information:
```python
app.add_middleware(GlobalErrorHandler, debug=True)
```

**Warning:** Never enable debug mode in production as it may expose sensitive information.

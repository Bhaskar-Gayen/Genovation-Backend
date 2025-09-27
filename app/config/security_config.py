"""
Security configuration for FastAPI application.
Environment-based security settings and production configurations.
"""
import os
from typing import List, Optional, Set
from pydantic import BaseSettings, validator
from enum import Enum


class Environment(str, Enum):
    """Application environment enumeration."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class SecuritySettings(BaseSettings):
    """Security-related configuration settings."""
    
    # Environment
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    
    # CORS Configuration
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    cors_allow_headers: List[str] = ["*"]
    cors_expose_headers: List[str] = ["X-Request-ID", "X-Process-Time"]
    
    # Security Headers
    hsts_max_age: int = 31536000  # 1 year
    hsts_include_subdomains: bool = True
    hsts_preload: bool = True
    frame_options: str = "DENY"
    content_security_policy: Optional[str] = None
    
    # HTTPS Configuration
    force_https: bool = False
    https_redirect_permanent: bool = True
    
    # Trusted Hosts
    trusted_hosts: List[str] = ["localhost", "127.0.0.1"]
    allow_any_host: bool = False
    
    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 60
    rate_limit_requests_per_hour: int = 1000
    rate_limit_requests_per_day: int = 10000
    rate_limit_burst_limit: int = 10
    rate_limit_whitelist_ips: Set[str] = set()
    rate_limit_blacklist_ips: Set[str] = set()
    
    # Request Validation
    max_request_size: int = 10 * 1024 * 1024  # 10MB
    max_multipart_size: int = 50 * 1024 * 1024  # 50MB
    max_json_depth: int = 10
    max_array_length: int = 1000
    max_string_length: int = 10000
    
    # Authentication
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 7
    require_fresh_tokens: bool = False
    max_token_age_seconds: int = 3600
    
    # Security Features
    enable_xss_protection: bool = True
    enable_sql_injection_protection: bool = True
    enable_input_sanitization: bool = True
    sanitize_html: bool = True
    
    # Logging
    log_requests: bool = True
    log_responses: bool = True
    log_request_body: bool = True
    log_response_body: bool = False
    log_sensitive_data: bool = False
    max_log_body_size: int = 1024 * 10  # 10KB
    
    # Health Checks
    health_check_timeout: float = 30.0
    enable_detailed_health_checks: bool = True
    
    class Config:
        env_file = ".env"
        env_prefix = "SECURITY_"
        case_sensitive = False
    
    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("cors_allow_methods", pre=True)
    def parse_cors_methods(cls, v):
        """Parse CORS methods from string or list."""
        if isinstance(v, str):
            return [method.strip().upper() for method in v.split(",")]
        return v
    
    @validator("cors_allow_headers", pre=True)
    def parse_cors_headers(cls, v):
        """Parse CORS headers from string or list."""
        if isinstance(v, str):
            return [header.strip() for header in v.split(",")]
        return v
    
    @validator("trusted_hosts", pre=True)
    def parse_trusted_hosts(cls, v):
        """Parse trusted hosts from string or list."""
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        return v
    
    @validator("rate_limit_whitelist_ips", pre=True)
    def parse_whitelist_ips(cls, v):
        """Parse whitelist IPs from string or set."""
        if isinstance(v, str):
            return set(ip.strip() for ip in v.split(",") if ip.strip())
        return v
    
    @validator("rate_limit_blacklist_ips", pre=True)
    def parse_blacklist_ips(cls, v):
        """Parse blacklist IPs from string or set."""
        if isinstance(v, str):
            return set(ip.strip() for ip in v.split(",") if ip.strip())
        return v
    
    @validator("debug")
    def validate_debug_mode(cls, v, values):
        """Ensure debug is False in production."""
        if values.get("environment") == Environment.PRODUCTION and v:
            raise ValueError("Debug mode must be disabled in production")
        return v
    
    @validator("force_https")
    def validate_https_in_production(cls, v, values):
        """Ensure HTTPS is enforced in production."""
        if values.get("environment") == Environment.PRODUCTION and not v:
            # Log warning but don't fail - allow override
            import logging
            logging.getLogger(__name__).warning(
                "HTTPS is not enforced in production environment"
            )
        return v
    
    def get_cors_origins_for_environment(self) -> List[str]:
        """Get CORS origins based on environment."""
        if self.environment == Environment.PRODUCTION:
            # Filter out localhost origins in production
            return [
                origin for origin in self.cors_origins 
                if not any(local in origin for local in ["localhost", "127.0.0.1"])
            ]
        return self.cors_origins
    
    def get_content_security_policy(self) -> str:
        """Get Content Security Policy based on environment."""
        if self.content_security_policy:
            return self.content_security_policy
        
        if self.environment == Environment.PRODUCTION:
            return (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' https:; "
                "connect-src 'self' https:; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self';"
            )
        else:
            return (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' https:; "
                "connect-src 'self' https: ws: wss:; "
                "frame-ancestors 'none';"
            )
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == Environment.PRODUCTION
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == Environment.DEVELOPMENT


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""
    
    # Connection Pool Settings
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600  # 1 hour
    pool_pre_ping: bool = True
    
    # Connection Settings
    connect_timeout: int = 10
    command_timeout: int = 60
    
    # SSL Settings
    ssl_require: bool = False
    ssl_ca_file: Optional[str] = None
    ssl_cert_file: Optional[str] = None
    ssl_key_file: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_prefix = "DB_"
        case_sensitive = False


class RedisSettings(BaseSettings):
    """Redis configuration settings."""
    
    # Connection Pool Settings
    max_connections: int = 50
    retry_on_timeout: bool = True
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    socket_keepalive: bool = True
    socket_keepalive_options: dict = {}
    
    # Connection Settings
    decode_responses: bool = True
    encoding: str = "utf-8"
    
    # SSL Settings
    ssl_cert_reqs: Optional[str] = None
    ssl_ca_certs: Optional[str] = None
    ssl_certfile: Optional[str] = None
    ssl_keyfile: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_prefix = "REDIS_"
        case_sensitive = False


class LoggingSettings(BaseSettings):
    """Logging configuration settings."""
    
    # Log Levels
    log_level: str = "INFO"
    root_log_level: str = "WARNING"
    
    # Log Formats
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    access_log_format: str = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
    
    # File Logging
    enable_file_logging: bool = True
    log_file_path: str = "logs/app.log"
    log_file_max_size: int = 10 * 1024 * 1024  # 10MB
    log_file_backup_count: int = 5
    
    # Structured Logging
    enable_json_logging: bool = False
    
    # Log Rotation
    enable_log_rotation: bool = True
    rotation_when: str = "midnight"
    rotation_interval: int = 1
    
    class Config:
        env_file = ".env"
        env_prefix = "LOG_"
        case_sensitive = False


# Global settings instances
security_settings = SecuritySettings()
database_settings = DatabaseSettings()
redis_settings = RedisSettings()
logging_settings = LoggingSettings()

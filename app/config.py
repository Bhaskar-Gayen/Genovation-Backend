from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    # App Config
    app_name: str
    debug: bool
    host: str
    port: int
    version: str
    
    # Database
    database_url: str

    # Redis
    redis_url:str

    # JWT
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int
    refresh_token_expire_minutes: int


    # Celery
    celery_broker_url: str
    celery_result_backend: str

    replicate_api_token: str


    # OTP
    otp_length: int
    otp_expire_minutes: int
    otp_max_attempts: int
    otp_rate_limit_per_hour: int

    # Rate Limits
    basic_tier_daily_limit: int
    pro_tier_daily_limit: int

    # Cache
    cache_ttl_chatrooms: int
    cache_ttl_user_data: int

    # Security
    cors_origins: str
    allowed_hosts: str

    # Pagination
    default_page_size: int
    max_page_size: int

    # Message
    max_message_length: int
    conversation_context_limit: int

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore", encoding="utf-8")


# Global settings instance
settings = Settings()

@lru_cache
def get_settings():
    return settings
    
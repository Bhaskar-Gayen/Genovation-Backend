import secrets
from redis_client import get_redis
from typing import Optional

OTP_LENGTH = 6
OTP_EXPIRY_SECONDS = 300  # 5 minutes
OTP_RATE_LIMIT = 3
OTP_RATE_LIMIT_WINDOW = 3600  # 1 hour

# Generate a 6-digit OTP
def generate_otp() -> str:
    return ''.join(secrets.choice('0123456789') for _ in range(OTP_LENGTH))

# Store OTP in Redis with expiration and rate limit
async def store_otp(mobile_number: str, otp: str) -> bool:
    redis = await get_redis()
    otp_key = f"otp:{mobile_number}"
    rate_key = f"otp_rate:{mobile_number}"
    # Rate limit check
    count = await redis.get(rate_key)
    if count and int(count) >= OTP_RATE_LIMIT:
        return False
    # Store OTP
    await redis.setex(otp_key, OTP_EXPIRY_SECONDS, otp)
    # Increment rate limit counter
    await redis.incr(rate_key)
    await redis.expire(rate_key, OTP_RATE_LIMIT_WINDOW)
    return True

# Verify OTP and cleanup
async def verify_otp(mobile_number: str, otp: str) -> bool:
    redis = await get_redis()
    otp_key = f"otp:{mobile_number}"
    stored_otp = await redis.get(otp_key)
    if stored_otp == otp:
        await redis.delete(otp_key)
        return True
    return False

# Get OTP TTL
async def get_otp_ttl(mobile_number: str) -> int:
    redis = await get_redis()
    otp_key = f"otp:{mobile_number}"
    ttl = await redis.ttl(otp_key)
    return ttl if ttl > 0 else 0 
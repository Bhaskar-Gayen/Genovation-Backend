from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.redis_client import get_redis
from fastapi import HTTPException
import secrets

from app.services.user_service import UserService


class OTPService:

    @classmethod
    def generate_otp(cls) -> str:
        return ''.join(secrets.choice('0123456789') for _ in range(settings.otp_length))

    @classmethod
    async def send_otp(cls, mobile_number: str, purpose: str = "login",  db: AsyncSession=None) -> dict:
        user = await UserService.get_profile_by_mobile_number(db, mobile_number=mobile_number)
        if user is None:
            raise HTTPException(status_code=400, detail="Mobile number not registered")
        redis = await get_redis()
        rate_key = f"otp_rate:{purpose}:{mobile_number}"
        otp_key = f"otp:{purpose}:{mobile_number}"
        count = await redis.get(rate_key)
        if count and int(count) >= settings.otp_rate_limit_per_hour:
            raise HTTPException(status_code=429, detail="Too many OTP requests. Please try again later.")
        otp = cls.generate_otp()
        await redis.setex(otp_key, settings.otp_expire_minutes*60, otp)
        await redis.incr(rate_key)
        await redis.expire(rate_key, settings.otp_expire_minutes*60)
        
        return {"message": f"OTP sent to {mobile_number}", "otp": otp, "expires_in": settings.otp_expire_minutes}

    @classmethod
    async def verify_otp(cls, mobile_number: str, otp: str, purpose: str = "login") -> bool:
        redis = await get_redis()
        otp_key = f"otp:{purpose}:{mobile_number}"
        stored_otp = await redis.get(otp_key)
        if stored_otp is None:
            raise HTTPException(status_code=400, detail="OTP expired or not found.")
        if stored_otp != otp:
            raise HTTPException(status_code=401, detail="Invalid OTP.")
        await redis.delete(otp_key)
        return True

    @classmethod
    async def get_otp_ttl(cls, mobile_number: str, purpose: str = "login") -> int:
        redis = await get_redis()
        otp_key = f"otp:{purpose}:{mobile_number}"
        ttl = await redis.ttl(otp_key)
        return ttl if ttl > 0 else 0

    @classmethod
    async def delete_otp(cls, mobile_number: str, purpose: str = "login") -> bool:
        redis = await get_redis()
        otp_key = f"otp:{purpose}:{mobile_number}"
        await redis.delete(otp_key)
        return True

import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from uuid import UUID

from app.redis_client import get_redis

logger = logging.getLogger("usage_service")

class UsageService:
    """Service for tracking and managing user usage limits"""

    @staticmethod
    def _get_daily_key(user_id: UUID) -> str:
        """Generate Redis key for daily usage tracking"""
        today = datetime.now().strftime("%Y-%m-%d")
        return f"usage:daily:{user_id}:{today}"

    @staticmethod
    def _get_monthly_key(user_id: UUID) -> str:
        """Generate Redis key for monthly usage tracking"""
        month = datetime.now().strftime("%Y-%m")
        return f"usage:monthly:{user_id}:{month}"

    @staticmethod
    async def get_daily_usage(user_id: UUID) -> int:
        """Get current daily usage count for user"""
        try:
            key = UsageService._get_daily_key(user_id)
            redis= await get_redis()
            usage = redis.get(key)
            return int(usage) if usage else 0
        except Exception as e:
            logger.error(f"Error getting daily usage for user {user_id}: {e}")
            return 0

    @staticmethod
    async def get_monthly_usage(user_id: UUID) -> int:
        """Get current monthly usage count for user"""
        try:
            key = UsageService._get_monthly_key(user_id)
            redis = await get_redis()
            usage = redis.get(key)
            return int(usage) if usage else 0
        except Exception as e:
            logger.error(f"Error getting monthly usage for user {user_id}: {e}")
            return 0

    @staticmethod
    async def increment_daily_usage(user_id: UUID, count: int = 1) -> int:
        """Increment daily usage counter for user"""
        try:
            key = UsageService._get_daily_key(user_id)

            redis = await get_redis()
            new_count = redis.incr(key, count)

            # Set expiration for midnight (next day)
            if new_count == count:  # First increment of the day
                # Calculate seconds until midnight
                now = datetime.now()
                midnight = (now + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                seconds_until_midnight = int((midnight - now).total_seconds())
                redis.expire(key, seconds_until_midnight)

            logger.info(f"Incremented daily usage for user {user_id}: {new_count}")
            return new_count

        except Exception as e:
            logger.error(f"Error incrementing daily usage for user {user_id}: {e}")
            return 0

    @staticmethod
    async def increment_monthly_usage(user_id: UUID, count: int = 1) -> int:
        """Increment monthly usage counter for user"""
        try:
            key = UsageService._get_monthly_key(user_id)

            redis = await get_redis()

            # Increment counter
            new_count = redis.incr(key, count)

            # Set expiration for end of month
            if new_count == count:  # First increment of the month
                # Calculate seconds until end of month
                now = datetime.now()
                if now.month == 12:
                    next_month = now.replace(year=now.year + 1, month=1, day=1)
                else:
                    next_month = now.replace(month=now.month + 1, day=1)
                next_month = next_month.replace(hour=0, minute=0, second=0, microsecond=0)
                seconds_until_month_end = int((next_month - now).total_seconds())
                redis.expire(key, seconds_until_month_end)

            return new_count

        except Exception as e:
            logger.error(f"Error incrementing monthly usage for user {user_id}: {e}")
            return 0

    @staticmethod
    async def reset_daily_usage(user_id: UUID) -> bool:
        """Reset daily usage counter for user"""
        try:
            key = UsageService._get_daily_key(user_id)
            redis = await get_redis()
            redis.delete(key)
            logger.info(f"Reset daily usage for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error resetting daily usage for user {user_id}: {e}")
            return False

    @staticmethod
    async def get_usage_stats(user_id: UUID) -> Dict[str, Any]:
        """Get comprehensive usage statistics for user"""
        try:
            daily_usage = UsageService.get_daily_usage(user_id)
            monthly_usage = UsageService.get_monthly_usage(user_id)
            redis = await get_redis()

            # Get TTL for daily key to show when it resets
            daily_key = UsageService._get_daily_key(user_id)
            daily_ttl = redis.ttl(daily_key)

            # Convert TTL to reset time
            reset_time = None
            if daily_ttl > 0:
                reset_time = (datetime.now() + timedelta(seconds=daily_ttl)).isoformat()

            return {
                "daily_usage": daily_usage,
                "monthly_usage": monthly_usage,
                "daily_reset_in_seconds": daily_ttl if daily_ttl > 0 else 0,
                "daily_reset_time": reset_time,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting usage stats for user {user_id}: {e}")
            return {
                "daily_usage": 0,
                "monthly_usage": 0,
                "daily_reset_in_seconds": 0,
                "daily_reset_time": None,
                "timestamp": datetime.now().isoformat()
            }

    @staticmethod
    async def get_all_users_usage(limit: int = 100) -> Dict[str, Any]:
        """Get usage statistics for all users (admin function)"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            pattern = f"usage:daily:*:{today}"

            redis = await get_redis()

            keys = redis.keys(pattern)

            users_usage = []
            for key in keys[:limit]:
                try:
                    # Extract user_id from key
                    parts = key.split(":")
                    if len(parts) >= 3:
                        user_id = int(parts[2])
                        usage = int(redis.get(key) or 0)

                        users_usage.append({
                            "user_id": user_id,
                            "daily_usage": usage,
                            "date": today
                        })
                except (ValueError, IndexError):
                    continue

            # Sort by usage (highest first)
            users_usage.sort(key=lambda x: x["daily_usage"], reverse=True)

            return {
                "date": today,
                "total_active_users": len(users_usage),
                "users": users_usage
            }

        except Exception as e:
            logger.error(f"Error getting all users usage: {e}")
            return {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "total_active_users": 0,
                "users": []
            }

    @staticmethod
    async def check_rate_limit(user_id: int, daily_limit: int) -> Dict[str, Any]:
        """Check if user has exceeded their daily rate limit"""
        try:
            current_usage = UsageService.get_daily_usage(user_id)

            if daily_limit == -1:
                return {
                    "allowed": True,
                    "current_usage": current_usage,
                    "daily_limit": daily_limit,
                    "remaining": -1,
                    "reset_time": None
                }

            # Check limit
            allowed = current_usage < daily_limit
            remaining = max(0, daily_limit - current_usage)
            redis = await get_redis()

            # Get reset time
            daily_key = UsageService._get_daily_key(user_id)
            daily_ttl = redis.ttl(daily_key)
            reset_time = None
            if daily_ttl > 0:
                reset_time = (datetime.now() + timedelta(seconds=daily_ttl)).isoformat()

            return {
                "allowed": allowed,
                "current_usage": current_usage,
                "daily_limit": daily_limit,
                "remaining": remaining,
                "reset_time": reset_time
            }

        except Exception as e:
            logger.error(f"Error checking rate limit for user {user_id}: {e}")
            return {
                "allowed": False,
                "current_usage": 0,
                "daily_limit": daily_limit,
                "remaining": 0,
                "reset_time": None
            }

    @staticmethod
    def record_message_sent(user_id: int) -> Dict[str, Any]:
        """Record that a message was sent by user"""
        try:
            daily_count = UsageService.increment_daily_usage(user_id)
            monthly_count = UsageService.increment_monthly_usage(user_id)

            logger.info(f"Recorded message for user {user_id}: daily={daily_count}, monthly={monthly_count}")

            return {
                "success": True,
                "daily_count": daily_count,
                "monthly_count": monthly_count,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error recording message for user {user_id}: {e}")
            return {
                "success": False,
                "daily_count": 0,
                "monthly_count": 0,
                "timestamp": datetime.now().isoformat()
            }

    @staticmethod
    async def health_check() -> Dict[str, Any]:
        """Check if Redis connection is healthy"""
        try:
            redis = await get_redis()
            redis.ping()
            return {
                "redis_connected": True,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "redis_connected": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
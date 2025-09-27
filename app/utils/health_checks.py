"""
Enhanced health check system for FastAPI application.
Provides comprehensive monitoring of database, Redis, Celery, and external services.
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum

import httpx
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from celery import Celery

from database import get_db
from config import settings

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health check status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class HealthCheckResult:
    """Health check result container."""
    
    def __init__(
        self,
        service: str,
        status: HealthStatus,
        response_time: float,
        message: str = "",
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ):
        self.service = service
        self.status = status
        self.response_time = response_time
        self.message = message
        self.details = details or {}
        self.timestamp = timestamp or datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "service": self.service,
            "status": self.status.value,
            "response_time_ms": round(self.response_time * 1000, 2),
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "healthy": self.status == HealthStatus.HEALTHY
        }


class DatabaseHealthCheck:
    """Database connectivity and performance health checks."""
    
    @staticmethod
    async def check_connection() -> HealthCheckResult:
        """Check database connection."""
        start_time = time.time()
        
        try:
            async with get_db() as db:
                # Simple connectivity test
                result = await db.execute(text("SELECT 1"))
                await result.fetchone()
                
                response_time = time.time() - start_time
                
                return HealthCheckResult(
                    service="database_connection",
                    status=HealthStatus.HEALTHY,
                    response_time=response_time,
                    message="Database connection successful"
                )
                
        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"Database health check failed: {e}")
            
            return HealthCheckResult(
                service="database_connection",
                status=HealthStatus.UNHEALTHY,
                response_time=response_time,
                message=f"Database connection failed: {str(e)}",
                details={"error": str(e)}
            )
    
    @staticmethod
    async def check_performance() -> HealthCheckResult:
        """Check database performance metrics."""
        start_time = time.time()
        
        try:
            async with get_db() as db:
                # Check connection pool status
                pool_info = {
                    "pool_size": db.bind.pool.size(),
                    "checked_in": db.bind.pool.checkedin(),
                    "checked_out": db.bind.pool.checkedout(),
                    "overflow": db.bind.pool.overflow(),
                    "invalid": db.bind.pool.invalid()
                }
                
                # Simple performance test
                await db.execute(text("SELECT COUNT(*) FROM information_schema.tables"))
                
                response_time = time.time() - start_time
                
                # Determine status based on response time
                if response_time < 0.1:
                    status = HealthStatus.HEALTHY
                    message = "Database performance is good"
                elif response_time < 0.5:
                    status = HealthStatus.DEGRADED
                    message = "Database performance is degraded"
                else:
                    status = HealthStatus.UNHEALTHY
                    message = "Database performance is poor"
                
                return HealthCheckResult(
                    service="database_performance",
                    status=status,
                    response_time=response_time,
                    message=message,
                    details={"pool_info": pool_info}
                )
                
        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"Database performance check failed: {e}")
            
            return HealthCheckResult(
                service="database_performance",
                status=HealthStatus.UNHEALTHY,
                response_time=response_time,
                message=f"Database performance check failed: {str(e)}",
                details={"error": str(e)}
            )


class RedisHealthCheck:
    """Redis connectivity and performance health checks."""
    
    @staticmethod
    async def check_connection() -> HealthCheckResult:
        """Check Redis connection."""
        start_time = time.time()
        
        try:
            redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Test basic operations
            await redis_client.ping()
            test_key = f"health_check_{int(time.time())}"
            await redis_client.set(test_key, "test", ex=10)
            value = await redis_client.get(test_key)
            await redis_client.delete(test_key)
            
            if value != "test":
                raise Exception("Redis read/write test failed")
            
            response_time = time.time() - start_time
            
            return HealthCheckResult(
                service="redis_connection",
                status=HealthStatus.HEALTHY,
                response_time=response_time,
                message="Redis connection successful"
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"Redis health check failed: {e}")
            
            return HealthCheckResult(
                service="redis_connection",
                status=HealthStatus.UNHEALTHY,
                response_time=response_time,
                message=f"Redis connection failed: {str(e)}",
                details={"error": str(e)}
            )
        finally:
            try:
                await redis_client.close()
            except:
                pass
    
    @staticmethod
    async def check_performance() -> HealthCheckResult:
        """Check Redis performance and memory usage."""
        start_time = time.time()
        
        try:
            redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Get Redis info
            info = await redis_client.info()
            memory_info = await redis_client.info("memory")
            
            response_time = time.time() - start_time
            
            # Calculate memory usage percentage
            used_memory = memory_info.get("used_memory", 0)
            max_memory = memory_info.get("maxmemory", 0)
            
            memory_usage_pct = 0
            if max_memory > 0:
                memory_usage_pct = (used_memory / max_memory) * 100
            
            # Determine status based on performance metrics
            if response_time < 0.01 and memory_usage_pct < 80:
                status = HealthStatus.HEALTHY
                message = "Redis performance is good"
            elif response_time < 0.05 and memory_usage_pct < 90:
                status = HealthStatus.DEGRADED
                message = "Redis performance is degraded"
            else:
                status = HealthStatus.UNHEALTHY
                message = "Redis performance is poor"
            
            details = {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": memory_info.get("used_memory_human", "unknown"),
                "memory_usage_percent": round(memory_usage_pct, 2),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "redis_version": info.get("redis_version", "unknown")
            }
            
            return HealthCheckResult(
                service="redis_performance",
                status=status,
                response_time=response_time,
                message=message,
                details=details
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"Redis performance check failed: {e}")
            
            return HealthCheckResult(
                service="redis_performance",
                status=HealthStatus.UNHEALTHY,
                response_time=response_time,
                message=f"Redis performance check failed: {str(e)}",
                details={"error": str(e)}
            )
        finally:
            try:
                await redis_client.close()
            except:
                pass


class CeleryHealthCheck:
    """Celery worker and queue health checks."""
    
    @staticmethod
    async def check_workers() -> HealthCheckResult:
        """Check Celery worker status."""
        start_time = time.time()
        
        try:
            from celery_app import celery_app
            
            # Get active workers
            inspect = celery_app.control.inspect()
            active_workers = inspect.active()
            registered_tasks = inspect.registered()
            
            response_time = time.time() - start_time
            
            if not active_workers:
                return HealthCheckResult(
                    service="celery_workers",
                    status=HealthStatus.UNHEALTHY,
                    response_time=response_time,
                    message="No active Celery workers found",
                    details={"active_workers": 0}
                )
            
            worker_count = len(active_workers)
            total_active_tasks = sum(len(tasks) for tasks in active_workers.values())
            
            # Determine status based on worker availability
            if worker_count >= 1:
                status = HealthStatus.HEALTHY
                message = f"Celery workers are healthy ({worker_count} active)"
            else:
                status = HealthStatus.DEGRADED
                message = "Limited Celery worker availability"
            
            details = {
                "active_workers": worker_count,
                "active_tasks": total_active_tasks,
                "worker_names": list(active_workers.keys()),
                "registered_tasks_count": len(registered_tasks) if registered_tasks else 0
            }
            
            return HealthCheckResult(
                service="celery_workers",
                status=status,
                response_time=response_time,
                message=message,
                details=details
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"Celery health check failed: {e}")
            
            return HealthCheckResult(
                service="celery_workers",
                status=HealthStatus.UNHEALTHY,
                response_time=response_time,
                message=f"Celery health check failed: {str(e)}",
                details={"error": str(e)}
            )
    
    @staticmethod
    async def check_queues() -> HealthCheckResult:
        """Check Celery queue status."""
        start_time = time.time()
        
        try:
            redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Check queue lengths
            queue_info = {}
            default_queues = ["celery", "high_priority", "low_priority"]
            
            for queue_name in default_queues:
                try:
                    length = await redis_client.llen(queue_name)
                    queue_info[queue_name] = length
                except:
                    queue_info[queue_name] = "unknown"
            
            response_time = time.time() - start_time
            
            # Calculate total pending tasks
            total_pending = sum(
                length for length in queue_info.values() 
                if isinstance(length, int)
            )
            
            # Determine status based on queue lengths
            if total_pending < 100:
                status = HealthStatus.HEALTHY
                message = "Celery queues are healthy"
            elif total_pending < 500:
                status = HealthStatus.DEGRADED
                message = "Celery queues have moderate load"
            else:
                status = HealthStatus.UNHEALTHY
                message = "Celery queues are overloaded"
            
            return HealthCheckResult(
                service="celery_queues",
                status=status,
                response_time=response_time,
                message=message,
                details={
                    "queue_lengths": queue_info,
                    "total_pending": total_pending
                }
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"Celery queue check failed: {e}")
            
            return HealthCheckResult(
                service="celery_queues",
                status=HealthStatus.UNHEALTHY,
                response_time=response_time,
                message=f"Celery queue check failed: {str(e)}",
                details={"error": str(e)}
            )
        finally:
            try:
                await redis_client.close()
            except:
                pass


class ExternalServiceHealthCheck:
    """External service health checks."""
    
    @staticmethod
    async def check_gemini_api() -> HealthCheckResult:
        """Check Gemini API availability."""
        start_time = time.time()
        
        try:
            # This is a placeholder - replace with actual Gemini API health check
            async with httpx.AsyncClient(timeout=10.0) as client:
                # You would replace this with actual Gemini API endpoint
                response = await client.get("https://generativelanguage.googleapis.com/")
                
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    status = HealthStatus.HEALTHY
                    message = "Gemini API is accessible"
                else:
                    status = HealthStatus.DEGRADED
                    message = f"Gemini API returned status {response.status_code}"
                
                return HealthCheckResult(
                    service="gemini_api",
                    status=status,
                    response_time=response_time,
                    message=message,
                    details={"status_code": response.status_code}
                )
                
        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"Gemini API health check failed: {e}")
            
            return HealthCheckResult(
                service="gemini_api",
                status=HealthStatus.UNHEALTHY,
                response_time=response_time,
                message=f"Gemini API check failed: {str(e)}",
                details={"error": str(e)}
            )
    
    @staticmethod
    async def check_stripe_api() -> HealthCheckResult:
        """Check Stripe API availability."""
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Stripe API status endpoint
                response = await client.get("https://status.stripe.com/api/v2/status.json")
                
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    data = response.json()
                    stripe_status = data.get("status", {}).get("indicator", "unknown")
                    
                    if stripe_status == "none":
                        status = HealthStatus.HEALTHY
                        message = "Stripe API is operational"
                    elif stripe_status in ["minor", "major"]:
                        status = HealthStatus.DEGRADED
                        message = f"Stripe API has {stripe_status} issues"
                    else:
                        status = HealthStatus.UNHEALTHY
                        message = "Stripe API has critical issues"
                    
                    return HealthCheckResult(
                        service="stripe_api",
                        status=status,
                        response_time=response_time,
                        message=message,
                        details={"stripe_status": stripe_status}
                    )
                else:
                    return HealthCheckResult(
                        service="stripe_api",
                        status=HealthStatus.DEGRADED,
                        response_time=response_time,
                        message=f"Stripe status API returned {response.status_code}",
                        details={"status_code": response.status_code}
                    )
                    
        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"Stripe API health check failed: {e}")
            
            return HealthCheckResult(
                service="stripe_api",
                status=HealthStatus.UNHEALTHY,
                response_time=response_time,
                message=f"Stripe API check failed: {str(e)}",
                details={"error": str(e)}
            )


class HealthCheckManager:
    """Centralized health check manager."""
    
    def __init__(self):
        self.checks = {
            "database_connection": DatabaseHealthCheck.check_connection,
            "database_performance": DatabaseHealthCheck.check_performance,
            "redis_connection": RedisHealthCheck.check_connection,
            "redis_performance": RedisHealthCheck.check_performance,
            "celery_workers": CeleryHealthCheck.check_workers,
            "celery_queues": CeleryHealthCheck.check_queues,
            "gemini_api": ExternalServiceHealthCheck.check_gemini_api,
            "stripe_api": ExternalServiceHealthCheck.check_stripe_api,
        }
    
    async def run_all_checks(self, timeout: float = 30.0) -> Dict[str, Any]:
        """Run all health checks with timeout."""
        start_time = time.time()
        results = {}
        
        try:
            # Run all checks concurrently with timeout
            tasks = [
                asyncio.create_task(check_func())
                for check_func in self.checks.values()
            ]
            
            completed_results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout
            )
            
            # Process results
            for i, (check_name, result) in enumerate(zip(self.checks.keys(), completed_results)):
                if isinstance(result, Exception):
                    results[check_name] = HealthCheckResult(
                        service=check_name,
                        status=HealthStatus.UNHEALTHY,
                        response_time=0,
                        message=f"Health check failed: {str(result)}",
                        details={"error": str(result)}
                    ).to_dict()
                else:
                    results[check_name] = result.to_dict()
            
        except asyncio.TimeoutError:
            logger.error(f"Health checks timed out after {timeout} seconds")
            for check_name in self.checks.keys():
                if check_name not in results:
                    results[check_name] = HealthCheckResult(
                        service=check_name,
                        status=HealthStatus.UNKNOWN,
                        response_time=timeout,
                        message="Health check timed out"
                    ).to_dict()
        
        # Calculate overall status
        total_time = time.time() - start_time
        overall_status = self._calculate_overall_status(results)
        
        return {
            "status": overall_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "total_response_time_ms": round(total_time * 1000, 2),
            "checks": results,
            "summary": self._generate_summary(results)
        }
    
    async def run_basic_checks(self) -> Dict[str, Any]:
        """Run basic health checks (connection only)."""
        basic_checks = {
            "database": DatabaseHealthCheck.check_connection,
            "redis": RedisHealthCheck.check_connection,
        }
        
        start_time = time.time()
        results = {}
        
        for check_name, check_func in basic_checks.items():
            try:
                result = await check_func()
                results[check_name] = result.to_dict()
            except Exception as e:
                results[check_name] = HealthCheckResult(
                    service=check_name,
                    status=HealthStatus.UNHEALTHY,
                    response_time=0,
                    message=f"Basic check failed: {str(e)}"
                ).to_dict()
        
        total_time = time.time() - start_time
        overall_status = self._calculate_overall_status(results)
        
        return {
            "status": overall_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "total_response_time_ms": round(total_time * 1000, 2),
            "checks": results
        }
    
    def _calculate_overall_status(self, results: Dict[str, Any]) -> HealthStatus:
        """Calculate overall system health status."""
        if not results:
            return HealthStatus.UNKNOWN
        
        statuses = [result.get("status", "unknown") for result in results.values()]
        
        if all(status == "healthy" for status in statuses):
            return HealthStatus.HEALTHY
        elif any(status == "unhealthy" for status in statuses):
            return HealthStatus.UNHEALTHY
        elif any(status == "degraded" for status in statuses):
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.UNKNOWN
    
    def _generate_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate health check summary."""
        total_checks = len(results)
        healthy_checks = sum(1 for r in results.values() if r.get("status") == "healthy")
        degraded_checks = sum(1 for r in results.values() if r.get("status") == "degraded")
        unhealthy_checks = sum(1 for r in results.values() if r.get("status") == "unhealthy")
        
        return {
            "total_checks": total_checks,
            "healthy": healthy_checks,
            "degraded": degraded_checks,
            "unhealthy": unhealthy_checks,
            "success_rate": round((healthy_checks / total_checks) * 100, 2) if total_checks > 0 else 0
        }


# Global health check manager instance
health_manager = HealthCheckManager()

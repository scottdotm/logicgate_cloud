"""
API Rate Limiting Middleware
Implements token bucket and sliding window rate limiting algorithms.
"""

import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from functools import wraps
from typing import Any

from logicgate_cloud.config.settings import get_settings
from logicgate_cloud.core.exceptions import RateLimitExceededException
from logicgate_cloud.infrastructure.cache import get_cache_manager
from logicgate_cloud.infrastructure.logging import LogLevel, get_logger


class RateLimitAlgorithm(StrEnum):
    """Rate limiting algorithms"""

    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW


class RateLimiter:
    """Rate limiter using token bucket algorithm"""

    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self.cache_manager = get_cache_manager()
        self.logger = get_logger("rate_limiter", LogLevel.INFO)
        self.settings = get_settings()

        # In-memory fallback for when cache is unavailable
        self._local_buckets: dict[str, dict] = defaultdict(dict)

    def _get_cache_key(self, identifier: str) -> str:
        """Generate cache key for rate limit data"""
        return f"rate_limit:{identifier}"

    def _get_bucket_data(self, identifier: str) -> dict[str, Any]:
        """Get bucket data from cache or local storage"""
        cache_key = self._get_cache_key(identifier)

        try:
            data = self.cache_manager.get(cache_key)
            if data:
                return data
        except Exception as e:
            self.logger.warning("Cache get failed, using local storage", error=str(e))

        # Fallback to local storage
        return self._local_buckets.get(
            identifier,
            {
                "tokens": self.config.burst_size,
                "last_update": time.time(),
                "request_count": 0,
                "window_start": time.time(),
            },
        )

    def _set_bucket_data(self, identifier: str, data: dict[str, Any]):
        """Set bucket data in cache and local storage"""
        cache_key = self._get_cache_key(identifier)

        # Set in cache with TTL
        try:
            self.cache_manager.set(cache_key, data, ttl=3600)
        except Exception as e:
            self.logger.warning("Cache set failed, using local storage", error=str(e))

        # Update local storage
        self._local_buckets[identifier] = data

    def check_rate_limit(self, identifier: str) -> bool:
        """Check if request is allowed"""
        if self.config.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
            return self._check_token_bucket(identifier)
        elif self.config.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
            return self._check_sliding_window(identifier)
        else:
            return self._check_fixed_window(identifier)

    def _check_token_bucket(self, identifier: str) -> bool:
        """Token bucket algorithm"""
        data = self._get_bucket_data(identifier)
        now = time.time()

        # Refill tokens
        time_passed = now - data["last_update"]
        refill_rate = self.config.requests_per_minute / 60.0  # tokens per second
        tokens_to_add = time_passed * refill_rate

        data["tokens"] = min(self.config.burst_size, data["tokens"] + tokens_to_add)
        data["last_update"] = now

        # Check if we have tokens
        if data["tokens"] >= 1:
            data["tokens"] -= 1
            self._set_bucket_data(identifier, data)
            return True
        else:
            self._set_bucket_data(identifier, data)
            return False

    def _check_sliding_window(self, identifier: str) -> bool:
        """Sliding window algorithm"""
        data = self._get_bucket_data(identifier)
        now = time.time()
        window_size = 60  # 1 minute window

        # Clean old requests
        if "requests" not in data:
            data["requests"] = []

        # Remove requests older than window
        data["requests"] = [
            req_time for req_time in data["requests"] if now - req_time < window_size
        ]

        # Check if under limit
        if len(data["requests"]) < self.config.requests_per_minute:
            data["requests"].append(now)
            self._set_bucket_data(identifier, data)
            return True
        else:
            self._set_bucket_data(identifier, data)
            return False

    def _check_fixed_window(self, identifier: str) -> bool:
        """Fixed window algorithm"""
        data = self._get_bucket_data(identifier)
        now = time.time()
        window_size = 60  # 1 minute window

        # Check if we need to reset window
        if now - data["window_start"] >= window_size:
            data["request_count"] = 0
            data["window_start"] = now

        # Check if under limit
        if data["request_count"] < self.config.requests_per_minute:
            data["request_count"] += 1
            self._set_bucket_data(identifier, data)
            return True
        else:
            self._set_bucket_data(identifier, data)
            return False

    def get_remaining_requests(self, identifier: str) -> int:
        """Get remaining requests for identifier"""
        data = self._get_bucket_data(identifier)

        if self.config.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
            if "requests" not in data:
                return self.config.requests_per_minute
            return max(0, self.config.requests_per_minute - len(data["requests"]))
        elif self.config.algorithm == RateLimitAlgorithm.FIXED_WINDOW:
            return max(0, self.config.requests_per_minute - data["request_count"])
        else:
            # Token bucket
            return int(data["tokens"])

    def reset_rate_limit(self, identifier: str):
        """Reset rate limit for identifier"""
        cache_key = self._get_cache_key(identifier)

        try:
            self.cache_manager.delete(cache_key)
        except Exception as e:
            self.logger.warning("Cache delete failed", error=str(e))

        if identifier in self._local_buckets:
            del self._local_buckets[identifier]

        self.logger.info("Rate limit reset", identifier=identifier)


def rate_limit(config: RateLimitConfig = None, identifier_func: Callable = None):
    """
    Decorator for rate limiting function calls

    Args:
        config: Rate limit configuration
        identifier_func: Function to extract identifier from request context
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            limiter = RateLimiter(config)

            # Get identifier
            if identifier_func:
                identifier = identifier_func(*args, **kwargs)
            else:
                # Default: use first argument as identifier
                identifier = str(args[0]) if args else "default"

            # Check rate limit
            if not limiter.check_rate_limit(identifier):
                remaining = limiter.get_remaining_requests(identifier)
                raise RateLimitExceededException(
                    service="api",
                    limit=config.requests_per_minute,
                    details={"identifier": identifier, "remaining": remaining},
                )

            # Call function
            return func(*args, **kwargs)

        return wrapper

    return decorator


class RateLimitMiddleware:
    """Middleware for rate limiting API requests"""

    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self.limiter = RateLimiter(self.config)
        self.logger = get_logger("rate_limit_middleware", LogLevel.INFO)
        self.settings = get_settings()

    def get_identifier(self, request: dict[str, Any]) -> str:
        """Extract identifier from request"""
        # Try to get user ID from request
        if "user_id" in request:
            return f"user:{request['user_id']}"

        # Try to get API key
        if "api_key" in request:
            return f"api_key:{request['api_key']}"

        # Try to get IP address
        if "ip_address" in request:
            return f"ip:{request['ip_address']}"

        # Fallback to session ID
        if "session_id" in request:
            return f"session:{request['session_id']}"

        # Default to unknown
        return "unknown"

    def process_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Process incoming request with rate limiting"""
        identifier = self.get_identifier(request)

        # Check rate limit
        if not self.limiter.check_rate_limit(identifier):
            remaining = self.limiter.get_remaining_requests(identifier)

            self.logger.warning("Rate limit exceeded", identifier=identifier, remaining=remaining)

            raise RateLimitExceededException(
                service="api",
                limit=self.config.requests_per_minute,
                details={"identifier": identifier, "remaining": remaining},
            )

        # Add rate limit headers to response
        remaining = self.limiter.get_remaining_requests(identifier)

        return {
            "rate_limit_remaining": remaining,
            "rate_limit_limit": self.config.requests_per_minute,
            "rate_limit_reset": int(time.time()) + 60,
        }

    def get_rate_limit_info(self, identifier: str) -> dict[str, Any]:
        """Get rate limit information for identifier"""
        return {
            "remaining": self.limiter.get_remaining_requests(identifier),
            "limit": self.config.requests_per_minute,
            "reset": int(time.time()) + 60,
            "algorithm": self.config.algorithm.value,
        }


# Global rate limit middleware instance
_rate_limit_middleware: RateLimitMiddleware | None = None


def get_rate_limit_middleware(config: RateLimitConfig = None) -> RateLimitMiddleware:
    """Get the singleton rate limit middleware instance"""
    global _rate_limit_middleware
    if _rate_limit_middleware is None:
        _rate_limit_middleware = RateLimitMiddleware(config)
    return _rate_limit_middleware

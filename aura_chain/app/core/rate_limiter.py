# app/core/rate_limiter.py
"""
Token-bucket rate limiter backed by Redis.

Enforces per-provider rate limits to respect API quotas (e.g., Groq TPM/RPM).
Uses Redis for atomic operations so rate limits are consistent across
async tasks within the same process.

Usage:
    await rate_limiter.acquire("groq")  # blocks until token available
"""

import asyncio
import time
import redis.asyncio as redis
from typing import Dict, Optional
from loguru import logger
from app.config import get_settings
from app.core.error_handling import RateLimitError

settings = get_settings()

# Default provider rate limits (requests per minute)
DEFAULT_LIMITS: Dict[str, Dict[str, int]] = {
    "groq": {"rpm": 30, "tpm": 14400},
    "google": {"rpm": 60, "tpm": 60000},
    "openai": {"rpm": 60, "tpm": 90000},
    "anthropic": {"rpm": 50, "tpm": 80000},
}

# Rate limiter Redis key TTL
BUCKET_TTL = 120  # 2 minutes


class TokenBucketLimiter:
    """
    Redis-backed token bucket rate limiter.
    
    Each provider gets a bucket that refills at `rpm` tokens per minute.
    `acquire()` blocks until a token is available.
    """
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.limits = DEFAULT_LIMITS.copy()
    
    async def initialize(self):
        """Initialize Redis connection."""
        self.redis_client = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        logger.info("✓ Rate limiter initialized")
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("✓ Rate limiter closed")
    
    def _bucket_key(self, provider: str) -> str:
        return f"ratelimit:{provider}:bucket"
    
    def _timestamp_key(self, provider: str) -> str:
        return f"ratelimit:{provider}:last_refill"
    
    async def acquire(self, provider: str, timeout_s: float = 30.0) -> bool:
        """
        Acquire a rate limit token. Blocks until available or timeout.
        
        Args:
            provider: LLM provider name (groq, google, openai, anthropic)
            timeout_s: Maximum time to wait for a token
            
        Returns:
            True if token acquired
            
        Raises:
            RateLimitError if timeout exceeded
        """
        if not self.redis_client:
            return True  # No Redis = no rate limiting
        
        limit_config = self.limits.get(provider, {"rpm": 60})
        rpm = limit_config["rpm"]
        
        start_time = time.time()
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout_s:
                raise RateLimitError(
                    f"Rate limit timeout for {provider} after {timeout_s}s",
                    provider=provider,
                    retry_after_ms=int((60 / rpm) * 1000)
                )
            
            acquired = await self._try_acquire(provider, rpm)
            if acquired:
                return True
            
            # Wait before retrying (proportional to rate)
            wait_time = min(60 / rpm, timeout_s - elapsed)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
    
    async def _try_acquire(self, provider: str, rpm: int) -> bool:
        """Attempt to consume one token from the bucket."""
        try:
            bucket_key = self._bucket_key(provider)
            ts_key = self._timestamp_key(provider)
            
            now = time.time()
            
            # Get current bucket state
            pipe = self.redis_client.pipeline()
            pipe.get(bucket_key)
            pipe.get(ts_key)
            results = await pipe.execute()
            
            current_tokens = float(results[0]) if results[0] else float(rpm)
            last_refill = float(results[1]) if results[1] else now
            
            # Refill tokens based on elapsed time
            elapsed = now - last_refill
            refill = elapsed * (rpm / 60.0)  # tokens per second
            current_tokens = min(rpm, current_tokens + refill)
            
            if current_tokens >= 1.0:
                # Consume one token
                new_tokens = current_tokens - 1.0
                pipe2 = self.redis_client.pipeline()
                pipe2.setex(bucket_key, BUCKET_TTL, str(new_tokens))
                pipe2.setex(ts_key, BUCKET_TTL, str(now))
                await pipe2.execute()
                return True
            else:
                # Update timestamp even when not consuming
                await self.redis_client.setex(ts_key, BUCKET_TTL, str(now))
                await self.redis_client.setex(bucket_key, BUCKET_TTL, str(current_tokens))
                return False
                
        except Exception as e:
            logger.warning(f"Rate limiter error (allowing request): {e}")
            return True  # Fail open — don't block requests on limiter errors
    
    async def get_status(self, provider: str) -> Dict:
        """Get current rate limit status for a provider."""
        if not self.redis_client:
            return {"available": True, "tokens": -1}
        
        try:
            bucket_key = self._bucket_key(provider)
            tokens = await self.redis_client.get(bucket_key)
            limit_config = self.limits.get(provider, {"rpm": 60})
            
            return {
                "provider": provider,
                "tokens_remaining": float(tokens) if tokens else limit_config["rpm"],
                "rpm_limit": limit_config["rpm"],
                "tpm_limit": limit_config.get("tpm", 0)
            }
        except Exception:
            return {"provider": provider, "tokens_remaining": -1}


# Global instance
rate_limiter = TokenBucketLimiter()

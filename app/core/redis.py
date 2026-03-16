# ==============================================================================
# core/redis.py
# ==============================================================================

import redis
import json
import logging

from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisClient:

    def __init__(self):
        # We configure short socket timeouts so Redis outages fail fast
        # and do not block the extraction request path.
        self.client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )
        self.ttl = settings.REDIS_CACHE_TTL
        logger.info("Redis Client Initialized with URL: %s", settings.REDIS_URL)

    def _build_key(self, manufacturer: str, model: str) -> str:
        """Normalize key to lowercase with dashes."""
        clean_manufacturer = manufacturer.strip().lower().replace(" ", "-")
        clean_model = model.strip().lower().replace(" ", "-")
        return f"equipment:{clean_manufacturer}:{clean_model}"

    def get(self, manufacturer: str, model: str) -> Optional[dict]:
        """Read from cache. Returns dict or None."""
        key = self._build_key(manufacturer, model)
        try:
            cached_value = self.client.get(key)
            if cached_value is None:
                logger.debug("Cache MISS for key: %s", key)
                return None
            # Cached payload is stored as JSON string and converted back to dict.
            logger.info("Cache HIT for key: %s", key)
            return json.loads(cached_value)
        except redis.RedisError as e:
            logger.error("Redis GET error for key %s: %s", key, str(e))
            return None

    def set(self, manufacturer: str, model: str, data: dict, ttl: Optional[int] = None) -> bool:
        """Write to cache with expiry."""
        key = self._build_key(manufacturer, model)
        expiry = ttl if ttl is not None else self.ttl
        try:
            json_data = json.dumps(data)
            self.client.set(key, json_data, ex=expiry)
            logger.info("Cache SET for key: %s (expires in %d seconds)", key, expiry)
            return True
        except redis.RedisError as e:
            logger.error("Redis SET error for key %s: %s", key, str(e))
            return False

    def delete(self, manufacturer: str, model: str) -> bool:
        """Remove from cache."""
        key = self._build_key(manufacturer, model)
        try:
            self.client.delete(key)
            logger.info("Cache DELETE for key: %s", key)
            return True
        except redis.RedisError as e:
            logger.error("Redis DELETE error for key %s: %s", key, str(e))
            return False

    def ping(self) -> bool:
        """Check if Redis is alive."""
        try:
            return self.client.ping()
        except redis.RedisError:
            return False


# Lazy-load Redis client on first use
_redis_client_instance = None

def get_redis_client():
    """Get or create Redis client lazily (defers 5-7 second connection delay until first use)"""
    global _redis_client_instance
    if _redis_client_instance is None:
        logger.info("⏳ Initializing Redis connection (first use)...")
        _redis_client_instance = RedisClient()
    return _redis_client_instance

# For backward compatibility with existing imports: from app.core.redis import redis_client
class LazyRedisClient:
    """Proxy that defers Redis connection until first use"""
    def __getattr__(self, name):
        # Delegate all attributes/methods to the real client instance once created.
        return getattr(get_redis_client(), name)

redis_client = LazyRedisClient()
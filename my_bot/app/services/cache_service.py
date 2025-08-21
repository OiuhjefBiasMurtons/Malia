from __future__ import annotations
import logging
from typing import Optional

try:
    from redis.asyncio import Redis
except Exception:  # pragma: no cover
    Redis = None  # type: ignore

from config.settings import settings

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self, url: Optional[str]):
        self.url = url
        self.redis: Optional[Redis] = None

    async def connect(self):
        if not self.url or Redis is None:
            logger.warning("Redis no disponible (sin URL o paquete)")
            return
        if self.redis is None:
            self.redis = Redis.from_url(self.url, decode_responses=True)
            try:
                await self.redis.ping()
                logger.info("Conectado a Redis")
            except Exception as e:
                logger.warning(f"No se pudo conectar a Redis: {e}")
                self.redis = None

    async def get(self, key: str) -> Optional[str]:
        if not self.redis:
            return None
        try:
            return await self.redis.get(key)
        except Exception:
            return None

    async def setex(self, key: str, ttl_seconds: int, value: str) -> None:
        if not self.redis:
            return
        try:
            await self.redis.setex(key, ttl_seconds, value)
        except Exception:
            pass

    # Rate limit: INCR con TTL en la misma clave
    async def incr_with_ttl(self, key: str, ttl_seconds: int) -> int:
        if not self.redis:
            return 0
        try:
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, ttl_seconds)
            res = await pipe.execute()
            return int(res[0])
        except Exception:
            return 0

cache_service = CacheService(settings.REDIS_URL)

# Sugerencia: en tu main.py añade un startup event para conectar
# @app.on_event("startup")
# async def _startup():
#     await cache_service.connect()
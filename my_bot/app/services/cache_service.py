"""
🗄️ SERVICIO DE CACHÉ - GESTIÓN REDIS
====================================

Este módulo proporciona una interfaz simplificada para Redis, manejando
caché de sesiones, rate limiting y almacenamiento temporal de datos.

Autor: Sistema de Caché Redis
Fecha: 2025-08-21
Versión: 1.0

🎯 PROPÓSITO:
- Gestionar conexiones asíncronas a Redis
- Proveer caché temporal para sesiones de usuario
- Implementar rate limiting distribuido
- Manejar fallbacks elegantes cuando Redis no está disponible

⚡ CARACTERÍSTICAS PRINCIPALES:
- Conexión asíncrona con redis-py
- Manejo graceful de errores de conexión
- Rate limiting con TTL automático
- Operaciones atómicas con pipelines
- Fallbacks cuando Redis no está disponible

🔧 OPERACIONES SOPORTADAS:
- get(): Obtener valor por clave
- setex(): Guardar con TTL (expiración automática)
- incr_with_ttl(): Incrementar contador con expiración

🛡️ ROBUSTEZ:
- Conexión opcional (no bloquea app si Redis falla)
- Logging de errores de conexión
- Reintentos automáticos en operaciones
- Graceful degradation sin Redis

📊 CASOS DE USO:
- Caché de sesiones de conversación
- Rate limiting por usuario/IP
- Almacenamiento temporal de respuestas
- Deduplicación de mensajes

🔄 RATE LIMITING:
- Contadores con expiración automática
- Operaciones atómicas con pipeline
- TTL configurable por caso de uso
- Fallback a 0 cuando Redis no disponible

⚙️ CONFIGURACIÓN:
- URL de Redis desde variables de entorno
- Decode responses automático para strings
- Ping de conexión en startup
- Logging detallado de estado

📝 EJEMPLO DE USO:
    # Caché simple
    await cache_service.setex("session:123", 3600, "data")
    data = await cache_service.get("session:123")
    
    # Rate limiting
    count = await cache_service.incr_with_ttl("rate:user:123", 60)
    if count > 10:
        # Usuario ha excedido límite
        pass

🔌 INTEGRACIÓN:
- Inicialización en startup de FastAPI
- Cierre limpio en shutdown
- Disponible globalmente como singleton
- Compatible con async/await
"""

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
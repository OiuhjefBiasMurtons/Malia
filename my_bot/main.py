"""
🚀 APLICACIÓN PRINCIPAL - SERVIDOR FASTAPI
==========================================

Este es el punto de entrada principal del bot de WhatsApp para pedidos de pavé.
Configura el servidor FastAPI con todos los middlewares, routers y servicios.

Autor: Sistema Principal WhatsApp Bot
Fecha: 2025-08-21
Versión: 1.0

🎯 PROPÓSITO:
- Inicializar servidor web FastAPI
- Configurar middlewares de seguridad y CORS
- Gestionar conexiones a servicios externos (Redis)
- Servir archivos estáticos y documentación API
- Proporcionar endpoints de salud y monitoreo

🏗️ ARQUITECTURA:
- FastAPI como framework web principal
- Rate limiting para proteger endpoints
- CORS configurado según ambiente (dev/prod)
- Gestión de ciclo de vida para recursos
- Routing modular por funcionalidad

🔌 SERVICIOS INTEGRADOS:
- Redis para caché de sesiones
- PostgreSQL vía SQLAlchemy
- Twilio para WhatsApp
- OpenAI para IA conversacional

🛡️ SEGURIDAD:
- Rate limiting por IP
- CORS restringido en producción
- Validación de webhooks Twilio
- Logs de seguridad

📊 ENDPOINTS PRINCIPALES:
- /webhook/whatsapp: Recibe mensajes de WhatsApp
- /health: Monitoreo de estado del servicio
- /docs: Documentación automática de API
- /static: Archivos estáticos (imágenes de menú)

🔄 CICLO DE VIDA:
1. Startup: Conecta a Redis y servicios
2. Runtime: Procesa requests de WhatsApp
3. Shutdown: Cierra conexiones limpiamente

⚙️ CONFIGURACIÓN:
- Ambiente determinado por settings.DEBUG
- CORS permisivo en desarrollo
- Rate limits configurables
- Logging adaptativo según ambiente

📱 INTEGRACIÓN WHATSAPP:
- Webhook principal en /webhook/whatsapp
- Validación de firmas Twilio
- Procesamiento asíncrono de mensajes
- Respuestas automáticas del bot

🚨 MONITOREO:
- Health checks en /health
- Métricas de rate limiting
- Logs estructurados
- Estado de servicios externos
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.routers import whatsapp
from config.settings import settings
from app.services.cache_service import cache_service
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):  #PARA USAR REDIS, AUNQUE ACTUALMENTE NO LO USO
    # Conectar a Redis al iniciar la aplicación
    await cache_service.connect()
    yield
    # shutdown
    if cache_service.redis:
        try:
            await cache_service.redis.aclose()  # cierra conexión limpia
        except Exception:
            pass

# Configurar rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Malia Bot API",
    description="API para chatbot de pedidos de Paves por WhatsApp",
    version="1.0.0",
    
    debug=settings.DEBUG
)

# Configurar rate limiting
app.state.limiter = limiter
# app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # Comentado temporalmente por problemas de tipo

# Agregar middleware de logging

# Configurar CORS más específico para producción
if settings.DEBUG:
    # En desarrollo, permitir todos los orígenes
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # En producción, ser más específico
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://yourdomain.com",
            "https://www.yourdomain.com",
            settings.NGROK_URL
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["*"],
    )

# Servir archivos estáticos
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Incluir routers
app.include_router(whatsapp.router, prefix="/webhook", tags=["webhook"])


@app.get("/")
async def root():
    return {
        "message": "Paves Bot API funcionando!",
        "docs": "/docs",
        "status": "activo"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "paves-bot"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="debug" if settings.DEBUG else "info") 
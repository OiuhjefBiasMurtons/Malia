from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Request,
    Form,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, constr, Field
from sqlalchemy.orm import Session
from sqlalchemy import select
from slowapi import Limiter
from slowapi.util import get_remote_address

from database.connection import get_db
from app.services.whatsapp_service import WhatsAppService
from app.services.new_enhanced_bot_service import NewEnhancedBotService
from app.services.cache_service import cache_service
from app.models.paves import Pave
from app.models.pedido import MedioPago
from config.settings import settings
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Rate limiting
# -----------------------------------------------------------------------------
# Nota: Twilio manda todas las requests desde sus IPs -> limitar por IP sirve poco.
# Mantenemos slowapi por simplicidad (protege contra floods),
# y dentro del handler aplicamos un RL por número con Redis cuando sea posible.
limiter = Limiter(key_func=get_remote_address)

router = APIRouter()

# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------
class WebhookJSONIn(BaseModel):
    From: str = Field(..., min_length=5, strip_whitespace=True,
                      description='ej. "whatsapp:+57..." o "+57..."')
    Body: str = Field(..., min_length=1, max_length=2000, strip_whitespace=True)
    MessageSid: Optional[str] = None
    SmsMessageSid: Optional[str] = None

class SendMessageIn(BaseModel):
    to_number: str = Field(..., min_length=5, strip_whitespace=True)
    message: str = Field(..., min_length=1, max_length=2000, strip_whitespace=True)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def effective_url(request: Request) -> str:
    """Reconstruye la URL tal como la vio Twilio detrás de proxies (nginx, CF)."""
    host = request.headers.get("x-forwarded-host") or request.url.hostname
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    return f"{proto}://{host}{request.url.path}"


def mask_number(num: str) -> str:
    if not num:
        return ""
    tail = num[-4:]
    return ("•" * max(len(num) - 4, 0)) + tail


async def send_with_retry(whatsapp: WhatsAppService, to: str, text: Optional[str] = None,
                          image_url: Optional[str] = None, caption: Optional[str] = None,
                          attempts: int = 3) -> None:
    """Envía mensajes con reintentos exponenciales básicos."""
    delay = 0.5
    for i in range(1, attempts + 1):
        try:
            if image_url:
                await whatsapp.send_image(to, image_url, caption or "")
            else:
                await whatsapp.send_message(to, text or "")
            return
        except TwilioRestException as e:
            if i == attempts:
                raise
            await asyncio.sleep(delay)
            delay *= 2


async def rl_check_per_number(from_number: str, limit_per_minute: int = 30) -> None:
    """Rate limit por número usando Redis si está disponible."""
    if not cache_service or not getattr(cache_service, "redis", None):
        return  # sin Redis, saltamos
    key = f"rl:wa:{from_number}:{int(time.time() // 60)}"  # ventana por minuto
    try:
        count = await cache_service.redis.incr(key)
        if count == 1:
            await cache_service.redis.expire(key, 70)  # TTL ~1m10s
        if count > limit_per_minute:
            raise HTTPException(status_code=429, detail="Rate limit excedido para este número")
    except Exception:  # si Redis falla, no bloquea el flujo
        logger.warning("Rate limit por número no disponible (Redis)")


# -----------------------------------------------------------------------------
# Núcleo de procesamiento
# -----------------------------------------------------------------------------
async def process_whatsapp_message(
    from_number: str,
    message_body: str,
    db: Session,
    request_payload: Optional[Dict[str, Any]] = None,
    message_sid: Optional[str] = None,
) -> Dict[str, Any]:
    """Procesa un mensaje entrante y envía la respuesta al usuario.

    - Dedupe por MessageSid (idempotencia)
    - RL por número (Redis)
    - Manejo de respuestas de texto / imágenes / combinadas
    """
    if not from_number or not message_body:
        raise HTTPException(status_code=400, detail="Datos incompletos")

    safe_from = mask_number(from_number)

    # Idempotencia: Twilio puede reintentar el mismo webhook
    if message_sid and cache_service and getattr(cache_service, "redis", None):
        if await cache_service.redis.get(f"dup:{message_sid}"):
            logger.info(f"🔁 Duplicado ignorado: {message_sid} ({safe_from})")
            return {"status": "duplicate", "message": "Already processed"}

    # Rate limit por número
    await rl_check_per_number(from_number, limit_per_minute=30)

    whatsapp_service = WhatsAppService()
    bot_service = NewEnhancedBotService(db)

    start = time.time()

    try:
        # Procesamiento del bot (IA / tradicional)
        response = await bot_service.process_message(from_number, message_body)
        logger.info(
            "Respuesta del bot | from=%s | type=%s",
            safe_from,
            type(response).__name__,
        )

        # Rama: solo imágenes
        if isinstance(response, dict) and response.get("type") == "images":
            images = response.get("images", [])
            caption = response.get("caption", "")
            for i, img in enumerate(images):
                url = img.get("url", "")
                icap = img.get("caption", "")
                final_caption = caption if i == 0 and caption else icap
                await send_with_retry(whatsapp_service, from_number, image_url=url, caption=final_caption)
                if i < len(images) - 1:
                    await asyncio.sleep(0.5)

        # Rama: combinado texto + imágenes
        elif isinstance(response, dict) and response.get("type") == "combined":
            text_message = response.get("text_message", "")
            if text_message:
                await send_with_retry(whatsapp_service, from_number, text=text_message)
                await asyncio.sleep(0.7)
            images_data = response.get("images", {})
            if isinstance(images_data, dict) and images_data.get("type") == "images":
                images = images_data.get("images", [])
                for i, img in enumerate(images):
                    url = img.get("url", "")
                    icap = img.get("caption", "")
                    await send_with_retry(whatsapp_service, from_number, image_url=url, caption=icap)
                    if i < len(images) - 1:
                        await asyncio.sleep(0.5)

        else:
            # Texto plano (asegura string)
            text = response if isinstance(response, str) else str(response)
            await send_with_retry(whatsapp_service, from_number, text=text)

        elapsed = time.time() - start
        logger.info("✅ Procesado OK | from=%s | %.2fs", safe_from, elapsed)

        # Marca de idempotencia al final
        if message_sid and cache_service and getattr(cache_service, "redis", None):
            await cache_service.redis.setex(f"dup:{message_sid}", 6 * 3600, "1")

        return {"status": "success", "message": "Procesado", "processing_time": elapsed}

    except TwilioRestException as e:
        logger.error("❌ Twilio error | from=%s | %s", safe_from, e)
        raise HTTPException(status_code=e.status or 400, detail=str(e))

    except Exception as e:
        logger.exception("❌ Error procesando mensaje | from=%s", safe_from)
        # Intenta notificar al usuario (best-effort)
        try:
            await whatsapp_service.send_message(from_number, "Lo siento, ocurrió un error. Intenta de nuevo.")
        except Exception:
            pass
        # Limpia la sesión si hubo operaciones de DB previas
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------------------------------------------------------
# Webhooks (Form y JSON) con validación de firma e idempotencia
# -----------------------------------------------------------------------------
@router.post("/whatsapp/form")
@limiter.limit("60/minute")
async def whatsapp_webhook_form(
    request: Request,
    background_tasks: BackgroundTasks,
    From: str = Form(...),
    Body: str = Form(...),
    MessageSid: Optional[str] = Form(None),
    SmsMessageSid: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    # Validación de firma (producción)
    if not settings.DEBUG:
        url = effective_url(request)
        signature = request.headers.get("X-Twilio-Signature", "")
        form_dict = dict(await request.form())
        if not WhatsAppService.validate_webhook(url, form_dict, signature):
            logger.warning("Webhook signature inválida (form)")
            raise HTTPException(status_code=403, detail="Invalid signature")

    from_number = (From or "").replace("whatsapp:", "")
    message_sid = MessageSid or SmsMessageSid

    # Procesa en background para responder ASAP a Twilio
    background_tasks.add_task(
        process_whatsapp_message,
        from_number,
        Body or "",
        db,
        {"MessageSid": MessageSid, "SmsMessageSid": SmsMessageSid, "Body": Body, "From": From},
        message_sid,
    )

    return JSONResponse({"status": "accepted"})


@router.post("/whatsapp")
@limiter.limit("60/minute")
async def whatsapp_webhook_json(
    request: Request,
    background_tasks: BackgroundTasks,
    data: WebhookJSONIn = Body(...),
    db: Session = Depends(get_db),
):
    # Validación de firma también para JSON (si lo usas con Twilio + proxy custom)
    if not settings.DEBUG and request.headers.get("X-Twilio-Signature"):
        url = effective_url(request)
        signature = request.headers.get("X-Twilio-Signature", "")
        # Para JSON, Twilio normalmente firma el body crudo; valida según tu implementación
        # Si tu WhatsAppService soporta validate_webhook_json, úsalo aquí.
        try:
            if not WhatsAppService.validate_webhook(url, data.model_dump(), signature):
                logger.warning("Webhook signature inválida (json)")
                raise HTTPException(status_code=403, detail="Invalid signature")
        except Exception:
            logger.warning("No se pudo validar firma JSON; continúa solo si confías en la fuente")

    from_number = (data.From or "").replace("whatsapp:", "")
    message_sid = data.MessageSid or data.SmsMessageSid

    background_tasks.add_task(
        process_whatsapp_message,
        from_number,
        data.Body,
        db,
        data.model_dump(),
        message_sid,
    )

    return JSONResponse({"status": "accepted"})


# -----------------------------------------------------------------------------
# Endpoints utilitarios
# -----------------------------------------------------------------------------
@router.post("/send-message")
@limiter.limit("60/minute")
async def send_message(
    data: SendMessageIn = Body(...),
):
    whatsapp_service = WhatsAppService()
    try:
        await send_with_retry(whatsapp_service, data.to_number, text=data.message)
        return JSONResponse({"status": "success"})
    except TwilioRestException as e:
        raise HTTPException(status_code=e.status or 400, detail=str(e))


@router.get("/test")
async def test_webhook():
    return {"status": "success", "message": "Webhook funcionando correctamente"}


@router.get("/performance")
async def performance_stats(db: Session = Depends(get_db)):
    try:
        cache_stats: Dict[str, Any] = {
            "redis_enabled": bool(cache_service and getattr(cache_service, "redis", None)),
        }
        if cache_service and getattr(cache_service, "redis", None):
            try:
                info = await cache_service.redis.info()
                cache_stats.update(
                    {
                        "redis_memory_used": info.get("used_memory_human", "unknown"),
                        "redis_connected_clients": info.get("connected_clients", 0),
                        "redis_total_commands": info.get("total_commands_processed", 0),
                    }
                )
            except Exception as e:
                cache_stats["redis_error"] = str(e)

        # Stats de DB (pool)
        db_stats: Dict[str, Any] = {}
        try:
            engine = db.get_bind()
            if hasattr(engine, "pool"):
                pool = engine.pool  # type: ignore
                db_stats = {
                    "pool_size": getattr(pool, "size", lambda: "unknown")(),
                    "checked_out": getattr(pool, "checkedout", lambda: "unknown")(),
                    "checked_in": getattr(pool, "checkedin", lambda: "unknown")(),
                    "overflow": getattr(pool, "overflow", lambda: "unknown")(),
                    "invalid": getattr(pool, "invalid", lambda: "unknown")(),
                }
            else:
                db_stats = {"pool_info": "not available"}
        except Exception as db_error:
            db_stats = {"error": f"DB stats unavailable: {db_error}"}

        return JSONResponse(
            {
                "status": "success",
                "cache_stats": cache_stats,
                "database_stats": db_stats,
                "timestamp": time.time(),
            }
        )
    except Exception as e:
        logger.error("Error en /performance: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

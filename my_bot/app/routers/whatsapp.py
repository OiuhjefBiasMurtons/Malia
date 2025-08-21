from fastapi import APIRouter, Request, HTTPException, Form, BackgroundTasks, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
import asyncio
import logging

from database.connection import SessionLocal  # sesión por task
from app.services.whatsapp_service import WhatsAppService
from app.services.bot_service import BotService
from app.services.throttle_service import (
    claim_message_idempotent,
    check_rate_limit,
)
from app.utils.retry import retry_async



router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)

class WebhookJSONIn(BaseModel):
    From: str = Field(..., min_length=5)
    Body: Optional[str] = Field(None, max_length=2000)
    MessageSid: Optional[str] = None
    SmsMessageSid: Optional[str] = None

    @field_validator('From')
    @classmethod
    def strip_from_whitespace(cls, v: str) -> str:
        """Valida y limpia espacios en blanco del campo From."""
        if isinstance(v, str):
            return v.strip()
        return v

def effective_url(request: Request) -> str:
    """Reconstruye la URL firmada por Twilio (respeta proxy y querystring)."""
    host = request.headers.get("x-forwarded-host") or request.url.hostname
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    path = request.url.path
    query = f"?{request.url.query}" if request.url.query else ""
    return f"{proto}://{host}{path}{query}"

def normalize_msisdn(n: str) -> str:
    """
    Normaliza un número de teléfono móvil en formato MSISDN.
    """
    n = (n or "").strip()
    if n.startswith("whatsapp:"):
        n = n[len("whatsapp:"):]
    n = n.replace(" ", "")
    if n and not n.startswith("+"):
        n = "+" + n
    return n

def _masked(num: str) -> str:
    """Enmascara todos los dígitos menos los últimos 4."""
    return ("•" * max(len(num) - 4, 0)) + num[-4:]


def _is_http_url(u: str) -> bool:
    """Valida que la URL sea HTTP/HTTPS válida."""
    return isinstance(u, str) and (u.startswith("http://") or u.startswith("https://"))


async def _send_images(whatsapp: WhatsAppService, from_number: str, images: list) -> None:
    """Envía una lista de imágenes con reintentos y delays."""
    if not isinstance(images, list):
        return
    
    # Cap suave: máximo 5 imágenes por respuesta
    images = images[:5]
        
    for i, img in enumerate(images):
        if isinstance(img, dict) and _is_http_url(img.get("url")):
            await retry_async(
                lambda img=img: whatsapp.send_image(from_number, img.get("url", ""), img.get("caption", "")),
                attempts=3, base_delay=0.4
            )
            # Pausa entre imágenes (excepto la última)
            if i < len(images) - 1:
                await asyncio.sleep(0.4)


async def _process_and_reply(from_number: str, body: str, message_sid: Optional[str]) -> None:
    """Flujo completo de procesamiento y respuesta."""
    safe = _masked(from_number)
    whatsapp = WhatsAppService()
    db: Session = SessionLocal()

    try:
        # 1) Idempotencia
        if message_sid and not claim_message_idempotent(db, message_sid, from_number, body):
            logger.info("🔁 Duplicado ignorado | sid=%s | from=%s", message_sid, safe)
            return

        # 2) Rate limit (ventana 1 min)
        if not check_rate_limit(db, from_number, limit_per_minute=30): # 30 mensajes por minuto
            fallback_msg = "Demasiados mensajes. Espera un momento."
            try:
                await retry_async(lambda: whatsapp.send_message(from_number, fallback_msg), attempts=3, base_delay=0.4)
            finally:
                return

        # 3) Proceso del bot con timeout
        bot = BotService(db)
        body_for_bot = body.strip() if body and body.strip() else "[non-text]"
        response = await asyncio.wait_for(
            bot.process_message(from_number, body_for_bot), timeout=20
        )

        # 4) Envío según tipo
        if isinstance(response, dict):
            response_type = response.get("type")
            
            if response_type == "combined":
                # Envío combinado: texto + imágenes
                txt = response.get("text_message", "")
                if txt:
                    await retry_async(lambda: whatsapp.send_message(from_number, txt), attempts=3, base_delay=0.4)
                    await asyncio.sleep(0.4)
                await _send_images(whatsapp, from_number, response.get("images", []))
                
            elif response_type == "images":
                # Solo imágenes
                await _send_images(whatsapp, from_number, response.get("images", []))
                
            else:
                # Texto simple o tipo desconocido
                text = response.get("text_message", str(response))
                await retry_async(lambda: whatsapp.send_message(from_number, text), attempts=3, base_delay=0.4)
        else:
            # Respuesta directa como string
            text = str(response)
            await retry_async(lambda: whatsapp.send_message(from_number, text), attempts=3, base_delay=0.4)

        logger.info("✅ Envío OK | from=%s | sid=%s", safe, message_sid or "N/A")

    except asyncio.TimeoutError:
        logger.warning("⏱️ Timeout procesando | from=%s | sid=%s", safe, message_sid or "N/A")
        timeout_msg = "Estamos experimentando demoras. Intenta de nuevo."
        try:
            await retry_async(lambda: whatsapp.send_message(from_number, timeout_msg), attempts=3, base_delay=0.4)
        except Exception:
            pass
    except Exception:
        logger.exception("❌ Error procesando/enviando | from=%s | sid=%s", safe, message_sid or "N/A")
        error_msg = "Ocurrió un error. Intenta de nuevo en unos momentos."
        try:
            await retry_async(lambda: whatsapp.send_message(from_number, error_msg), attempts=3, base_delay=0.4)
        except Exception:
            pass
    finally:
        db.close()

@router.post("/whatsapp")
@limiter.limit("200/minute") #SlowAPI
async def whatsapp_webhook_form(
    request: Request,
    background_tasks: BackgroundTasks,
    From: str = Form(...),
    Body: str = Form(""),
    MessageSid: Optional[str] = Form(None),
    SmsMessageSid: Optional[str] = Form(None),
):
    # ✅ Validación de firma (form) usando FormData crudo
    form_data = await request.form()
    signature = request.headers.get("X-Twilio-Signature", "")
    algo = request.headers.get("X-Twilio-Signature-Algorithm")
    url = effective_url(request)

    if not WhatsAppService.validate_webhook(url, form_data, signature, algo):
        logger.info("❌ Twilio signature invalid (form) url=%s sig_present=%s", url, bool(signature))
        raise HTTPException(status_code=403, detail="Invalid signature")

    from_number = normalize_msisdn(From)
    if not from_number:
        raise HTTPException(status_code=400, detail="Número inválido")

    background_tasks.add_task(
        _process_and_reply,
        from_number,
        (Body or "").strip(),
        MessageSid or SmsMessageSid,
    )
    return JSONResponse({"status": "accepted"})

@router.post("/whatsapp/json")
@limiter.limit("200/minute")
async def whatsapp_webhook_json(
    request: Request,
    background_tasks: BackgroundTasks,
    data: WebhookJSONIn = Body(...),
):
    # ✅ Validación de firma (JSON) con raw body exacto
    signature = request.headers.get("X-Twilio-Signature", "")
    algo = request.headers.get("X-Twilio-Signature-Algorithm")
    raw = await request.body()
    url = effective_url(request)

    if not WhatsAppService.validate_webhook_json(url, raw, signature, algo):
        logger.info("❌ Twilio signature invalid (json) url=%s sig_present=%s", url, bool(signature))
        raise HTTPException(status_code=403, detail="Invalid signature")

    from_number = normalize_msisdn(data.From)
    if not from_number:
        raise HTTPException(status_code=400, detail="Número inválido")

    background_tasks.add_task(
        _process_and_reply,
        from_number,
        (data.Body or "").strip(),
        data.MessageSid or data.SmsMessageSid,
    )
    return JSONResponse({"status": "accepted"})

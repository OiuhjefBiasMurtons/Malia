"""
📱 WHATSAPP SERVICE - PUENTE CON TWILIO
======================================

Este módulo maneja toda la comunicación con WhatsApp a través de la API de Twilio,
incluyendo envío de mensajes, imágenes y validación de webhooks de seguridad.

Autor: Sistema de Comunicación WhatsApp
Fecha: 2025-08-21
Versión: 1.5

🎯 PROPÓSITO PRINCIPAL:
- Enviar mensajes de texto a WhatsApp
- Enviar imágenes con captions
- Validar firmas de webhooks de Twilio (seguridad)
- Formatear números de teléfono para WhatsApp

🔐 SEGURIDAD:
- Validación de firmas HMAC para webhooks
- Soporte para SHA1 y SHA256
- Protección contra ataques de timing
- Validación tanto para form-data como JSON

📤 TIPOS DE MENSAJES SOPORTADOS:
- Texto simple
- Imágenes con caption opcional
- Formato automático de números WhatsApp

🔄 FLUJO DE COMUNICACIÓN:
1. Bot genera respuesta (BotService)
2. Router llama a WhatsAppService
3. Twilio API envía mensaje al usuario
4. Webhook recibe respuesta/confirmación
5. Validación de firma de seguridad

⚡ CARACTERÍSTICAS CLAVE:
- Cliente Twilio singleton para eficiencia
- Operaciones asíncronas con anyio
- Manejo automático de prefijo "whatsapp:"
- Logging detallado para debugging
- Validación robusta de webhooks

🛡️ VALIDACIÓN DE WEBHOOKS:
- validate_webhook(): Para form-data (application/x-www-form-urlencoded)
- validate_webhook_json(): Para JSON (application/json)
- Algoritmos: SHA1 (default) y SHA256
- Comparación segura con timing attack protection

📱 FORMATO DE NÚMEROS:
- Entrada: "+1234567890" o "1234567890"
- Salida: "whatsapp:+1234567890"
- Manejo automático de prefijos

🔧 CONFIGURACIÓN REQUERIDA:
- TWILIO_ACCOUNT_SID: ID de cuenta Twilio
- TWILIO_AUTH_TOKEN: Token de autenticación
- TWILIO_WHATSAPP_NUMBER: Número WhatsApp de la empresa

📝 EJEMPLO DE USO:
    service = WhatsAppService()
    await service.send_message("+1234567890", "¡Hola!")
    await service.send_image("+1234567890", "https://...", "Menú del día")
"""

from twilio.rest import Client
from twilio.request_validator import RequestValidator
from config.settings import settings
import anyio
import hmac
import hashlib
import base64
from typing import Optional, Union, Any, Mapping
from starlette.datastructures import FormData
import logging

logger = logging.getLogger(__name__)


_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

def _wa(n: str) -> str:
    return n if n.startswith("whatsapp:") else f"whatsapp:{n}"

class WhatsAppService:
    def __init__(self):
        self.client = _client
        self.from_number = settings.TWILIO_WHATSAPP_NUMBER

    async def send_message(self, to_number: str, body: str) -> str:
        def _send():
            msg = self.client.messages.create(
                from_=_wa(self.from_number),
                to=_wa(to_number),
                body=body,
            )
            return msg.sid
        return await anyio.to_thread.run_sync(_send)

    async def send_image(self, to_number: str, media_url: str, caption: str = "") -> str:
        def _send():
            msg = self.client.messages.create(
                from_=_wa(self.from_number),
                to=_wa(to_number),
                body=caption or None,
                media_url=[media_url],
            )
            return msg.sid
        return await anyio.to_thread.run_sync(_send)

    # ---------- Validación de firma ----------

    @staticmethod
    def _b64_hmac(data: bytes, key: str, algo: Optional[str]) -> str:
        alg = (algo or "SHA1").upper()
        if alg == "SHA256":
            digest = hmac.new(key.encode("utf-8"), data, hashlib.sha256).digest()
        else:
            digest = hmac.new(key.encode("utf-8"), data, hashlib.sha1).digest()
        return base64.b64encode(digest).decode("utf-8")

    @staticmethod
    def _safe_eq(a: str, b: str) -> bool:
        try:
            return hmac.compare_digest(a, b)
        except Exception:
            return False

    @staticmethod
    def validate_webhook(
        url: str,
        form: Union[FormData, Mapping[str, Any]],
        signature: str,
        signature_algo: Optional[str] = None,  # no usado por RequestValidator
    ) -> bool:
        """
        Valida firmas Twilio para application/x-www-form-urlencoded
        usando el validador oficial (maneja orden/encoding).
        """
        if not settings.TWILIO_AUTH_TOKEN or not signature or not url:
            logger.debug(
                "Missing validation data (form) url=%s sig=%s token=%s",
                url, bool(signature), bool(settings.TWILIO_AUTH_TOKEN)
            )
            return False

        try:
            validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
            # Twilio espera un mapping simple
            if isinstance(form, FormData):
                form_dict = dict(form)
            else:
                form_dict = dict(form)

            is_valid = validator.validate(url, form_dict, signature)
            logger.debug("Twilio form signature valid=%s url=%s", is_valid, url)
            return is_valid
        except Exception as e:
            logger.exception("Validation error (form): %s", e)
            return False

    @staticmethod
    def validate_webhook_json(
        url: str,
        raw_body: Union[bytes, bytearray, str],
        signature: str,
        signature_algo: Optional[str] = None,
    ) -> bool:
        """
        Valida firmas Twilio para application/json:
        string_to_sign = url + raw_body (bytes exactos).
        Permite SHA1 (default) y SHA256 si el header lo indica.
        """
        if not settings.TWILIO_AUTH_TOKEN or not signature or not url:
            logger.debug(
                "Missing validation data (json) url=%s sig=%s token=%s",
                url, bool(signature), bool(settings.TWILIO_AUTH_TOKEN)
            )
            return False

        if isinstance(raw_body, str):
            body_bytes = raw_body.encode("utf-8")
        else:
            body_bytes = bytes(raw_body or b"")

        try:
            string_to_sign = url.encode("utf-8") + body_bytes
            computed = WhatsAppService._b64_hmac(
                string_to_sign, settings.TWILIO_AUTH_TOKEN, signature_algo
            )
            ok = WhatsAppService._safe_eq(computed, signature)
            logger.debug("Twilio JSON signature valid=%s url=%s algo=%s", ok, url, signature_algo or "SHA1")
            return ok
        except Exception as e:
            logger.exception("Validation error (json): %s", e)
            return False
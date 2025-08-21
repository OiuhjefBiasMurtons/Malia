from sqlalchemy.orm import Session
import os
import json
import asyncio
from typing import Any, Dict, List, Optional, TypedDict, Literal

from config.settings import settings
from app.utils.retry import retry_async


from openai import OpenAI, APIConnectionError, APITimeoutError, RateLimitError

# ---------------------------
# Tipos de respuesta del bot
# ---------------------------

RespType = Literal["text", "images", "combined"]

class ImageItem(TypedDict, total=False):
    url: str
    caption: str

class BotReply(TypedDict, total=False):
    type: RespType
    text_message: Optional[str]
    images: Optional[List[ImageItem]]  # SIEMPRE lista

# --------------------------------
# BotService: interfaz muy simple
# --------------------------------

class BotService:
    """
    Orquesta una llamada al modelo de OpenAI para obtener una respuesta
    en formato JSON controlado (text / images / combined).
    """

    def __init__(self, db: Session):
        self.db = db
        api_key = os.getenv("OPENAI_API_KEY", settings.OPENAI_API_KEY)
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY no configurada")
        self.client = OpenAI(api_key=api_key)
        self.model = getattr(settings, "OPENAI_MODEL", None) or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    async def process_message(self, from_number: str, body: str) -> BotReply | str:
        """
        Retorna un dict con las llaves esperadas por el router:
        - {"type": "text", "text_message": "..."}
        - {"type": "images", "images": [{"url":"...", "caption":"..."}]}
        - {"type": "combined", "text_message":"...", "images": {...}}
        Si algo sale mal, retorna string de fallback (para que el router lo envíe tal cual).
        """

        system_prompt = self._system_prompt()  # reglas, ejemplos JSON válidos y qué NO hacer (no inventar URLs)
        user_prompt = self._user_prompt(from_number, body)  # Prompt del usuario

        async def _call():
            # Llamada con tiempo máximo total; también puedes usar timeout en SDK
            return await asyncio.wait_for(self._chat_json(system_prompt, user_prompt), timeout=5)

        try:
            # Reintenta 3 veces con backoff corto (0.4s → 0.8s → 1.6s)
            reply: BotReply = await retry_async(
                _call,
                attempts=3,
                base_delay=0.4,
                exc=(APIConnectionError, APITimeoutError, RateLimitError, TimeoutError, asyncio.TimeoutError),
            )

            # Validación mínima de estructura por seguridad
            if not isinstance(reply, dict) or "type" not in reply:
                return "Perdón, no entendí. ¿Puedes repetirlo?"
                
            # Normalizar tipo de respuesta
            response_type = reply.get("type")
            if response_type not in ("text", "images", "combined"):
                reply["type"] = "text"
                reply["text_message"] = reply.get("text_message") or "Perdón, no entendí. ¿Puedes repetirlo?"

            # Asegurar campos requeridos según el tipo
            self._validate_response_fields(reply)
            return reply

        except Exception:
            # Si todos los intentos fallan, devolvemos un texto plano de fallback
            return "Tuvimos un problema momentáneo. Intenta de nuevo."

    def _validate_response_fields(self, reply: BotReply) -> None:
        """Valida y corrige los campos de la respuesta según su tipo."""
        response_type = reply["type"]
        
        if response_type in ("text", "combined") and not reply.get("text_message"):
            reply["text_message"] = "¿En qué puedo ayudarte?"
            
        if response_type in ("images", "combined"):
            images = reply.get("images", [])
            if not isinstance(images, list) or not images:
                # Degrada a texto para no "responder nada"
                reply["type"] = "text"
                reply["text_message"] = reply.get("text_message") or "¿En qué puedo ayudarte?"
                reply.pop("images", None)

    def _is_http_url(self, u: str) -> bool:
        """Valida que la URL sea HTTP/HTTPS válida."""
        return isinstance(u, str) and (u.startswith("http://") or u.startswith("https://"))

    # -----------------
    # Prompts y llamada
    # -----------------

    def _system_prompt(self) -> str:
        """
        Instrucciones del asistente (tono, formato, reglas).
        """
        return (
            "Eres un asistente de pedidos por WhatsApp. Respondes en español, breve y amable.\n\n"
            "FORMATO DE RESPUESTA (devuelve SOLO un JSON válido, sin texto adicional fuera del JSON):\n"
            # Solo texto
            '{"type":"text","text_message":"¡Hola! ¿En qué puedo ayudarte?"}\n'
            # Solo imágenes (images SIEMPRE es una lista de {url, caption})
            '{"type":"images","images":[{"url":"https://ejemplo.com/menu.jpg","caption":"Menú del día"}]}\n'
            # Combinado
            '{"type":"combined","text_message":"Aquí tienes nuestro menú:","images":[{"url":"https://ejemplo.com/menu.jpg","caption":"Menú vigente"}]}\n\n'
            "REGLAS:\n"
            "- NUNCA inventes URLs de imágenes. Si no tienes imágenes reales, responde con type=\"text\".\n"
            "- Si el usuario saluda o es ambiguo, pide datos específicos del pedido (producto, tamaño/sabor, cantidad).\n"
            "- Una vez definido el pedido, confirma el resumen y luego solicita la dirección y método de pago.\n"
            "- Si falta información (p. ej., tamaño), pregunta SOLO por lo que falta.\n"
            "- Mantén las respuestas cortas (1–2 frases). No repitas información confirmada.\n\n"
            "NOTAS DE FORMATO:\n"
            "- Campos posibles: type ('text'|'images'|'combined'), text_message (string), images (lista de {url, caption}).\n"
            "- En 'images', 'caption' puede ser vacío si no aplica.\n"
            )

    def _user_prompt(self, from_number: str, body: str) -> str:
        """
        Contexto mínimo del usuario. Aquí podrías agregar señalizaciones
        (ej.: cliente frecuente, estado de un pedido) si las obtienes desde la DB.
        Mantente simple al inicio.
        """
        masked = "•••" + from_number[-4:]
        return f"Usuario {masked} dice: {body}"

    async def _chat_json(self, system_prompt: str, user_prompt: str) -> BotReply: 
        """
        Solicita una respuesta al modelo de chat en formato JSON. 
        """
        resp = await asyncio.to_thread(
            self.client.chat.completions.create,
            model=self.model,
            response_format={"type": "json_object"},
            temperature=0.4,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=400,
        )

        raw = resp.choices[0].message.content or "{}"
        try:
            data = json.loads(raw)
            # Validación de tipo
            if data.get("type") not in ("text", "images", "combined"):
                return {"type": "text", "text_message": "No entendí tu mensaje. ¿Qué producto te interesa?"}

            # text_message requerido en text/combined
            if data["type"] in ("text", "combined") and not data.get("text_message"):
                data["text_message"] = "¿En qué puedo ayudarte?"

            # images debe ser lista en images/combined
            if data["type"] in ("images", "combined"):
                images = data.get("images", [])
                if not isinstance(images, list):
                    # degradamos a texto si vino mal
                    return {"type": "text", "text_message": data.get("text_message", "¿En qué puedo ayudarte?")}
                # Filtrar items inválidos y validar URLs
                clean = []
                for it in images:
                    if isinstance(it, dict) and self._is_http_url(it.get("url")):
                        clean.append({"url": it["url"], "caption": it.get("caption", "")})
                # Cap suave: máximo 5 imágenes
                data["images"] = clean[:5]

            return data

        except json.JSONDecodeError:
            return {"type": "text", "text_message": "Hubo un error procesando tu pedido. ¿Puedes intentar de nuevo?"}
        except Exception:
            return {"type": "text", "text_message": "Algo salió mal. ¿En qué puedo ayudarte?"}

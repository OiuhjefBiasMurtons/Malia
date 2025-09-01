"""
🤖 BOT SERVICE - CEREBRO DEL ASISTENTE IA
========================================

Este módulo es el núcleo de inteligencia artificial que convierte mensajes 
de WhatsApp en respuestas útiles usando OpenAI GPT.

Autor: Sistema de Chat Bot WhatsApp
Fecha: 2025-08-21
Versión: 2.0

🎯 PROPÓSITO:
- Procesar mensajes de usuarios de WhatsApp
- Generar respuestas inteligentes usando OpenAI
- Manejar diferentes tipos de respuesta (texto, imágenes, combinado)
- Proporcionar fallbacks robustos ante errores

🔄 FLUJO PRINCIPAL:
1. Usuario envía mensaje por WhatsApp
2. Router llama a BotService.process_message()
3. BotService construye prompts para OpenAI
4. OpenAI devuelve respuesta en formato JSON estructurado
5. BotService valida y normaliza la respuesta
6. Router envía respuesta al usuario

📊 TIPOS DE RESPUESTA SOPORTADOS:
- TEXT: Solo mensaje de texto
- IMAGES: Solo imágenes con captions
- COMBINED: Texto + imágenes juntos

⚡ CARACTERÍSTICAS CLAVE:
- Reintentos automáticos con backoff exponencial
- Timeouts para evitar colgadas
- Validación estricta de URLs de imágenes
- Fallbacks elegantes ante errores
- Formato JSON estructurado para consistencia

🛡️ ROBUSTEZ:
- No inventa URLs de imágenes falsas
- Degrada graciosamente ante problemas de red
- Limita respuestas a formatos válidos
- Maneja errores de OpenAI (rate limits, timeouts)

📝 EJEMPLO DE USO:
    bot = BotService(db_session)
    reply = await bot.process_message("+1234567890", "Hola, quiero pizza")
    # reply = {"type": "text", "text_message": "¡Hola! ¿Qué pizza te interesa?"}
"""

from sqlalchemy.orm import Session
import os
import json
import asyncio
import logging
from contextvars import ContextVar
from typing import Any, Dict, List, Optional, TypedDict, Literal

from config.settings import settings
from app.utils.retry import retry_async

# 🔧 CONTEXT VAR: Thread-safe storage para phone_number
current_phone: ContextVar[Optional[str]] = ContextVar("current_phone", default=None)


from openai import AsyncOpenAI, APIConnectionError, APITimeoutError, RateLimitError

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
    
    🔧 PREPARADO PARA FUNCTION-CALLING:
    - _tool_defs(): Definirá schemas de herramientas
    - _dispatch_tool(): Ejecutará llamadas a OrderService
    - _chat_json(): Soportará 1 vuelta de tool máximo por turno
    """

    def __init__(self, db: Session):
        self.db = db
        api_key = os.getenv("OPENAI_API_KEY", settings.OPENAI_API_KEY)
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY no configurada")
        
        # 🔧 Cliente async nativo (mejor que asyncio.to_thread)
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = getattr(settings, "OPENAI_MODEL", None) or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        
        # 🔧 Inyección de OrderService para function-calling
        from app.services.order_service import OrderService
        self.order_service = OrderService(db)
        
        # 🧠 Inyección de Context Manager para gestión automática de contexto
        from app.services.context_manager import ConversationContextManager
        self.context_manager = ConversationContextManager(db)

    @staticmethod
    def _extract_sizes_from_text(text: str) -> List[int]:
        """
        Extrae tamaños (8, 16) del texto usando normalización Unicode.
        Útil para casos como 'uno de 8 y otro de 16'.
        """
        import re
        import unicodedata
        
        # Normalizar acentos
        normalized = ''.join(
            c for c in unicodedata.normalize('NFD', text.lower()) 
            if unicodedata.category(c) != 'Mn'
        )
        
        # Buscar tamaños 8 y 16
        sizes = re.findall(r'\b(8|16)\s*(?:oz|onzas)?\b', normalized)
        return [int(x) for x in sizes]

    async def process_message(self, from_number: str, body: str) -> BotReply | str:
        """
        Retorna un dict con las llaves esperadas por el router:
        - {"type": "text", "text_message": "..."}
        - {"type": "images", "images": [{"url":"...", "caption":"..."}]}
        - {"type": "combined", "text_message":"...", "images": {...}}
        Si algo sale mal, retorna string de fallback (para que el router lo envíe tal cual).
        """
        
        # 🧠 GESTIÓN AUTOMÁTICA DE CONTEXTO: Actualizar antes de procesar
        context = self.context_manager.update_context_automatically(from_number, body)
        
        # 🔍 INTERPRETACIÓN DE REFERENCIAS VAGAS: Intentar interpretar el mensaje
        interpretation = self.context_manager.interpret_vague_reference(body, context)
        if interpretation:
            # Si hay una interpretación clara, úsala en el user prompt
            enhanced_body = f"{body} ({interpretation})"
        else:
            enhanced_body = body
        
        # 🔧 PARSER OPCIONAL: Mejora adicional para casos de tamaños sin sabor
        if not interpretation:
            sizes = self._extract_sizes_from_text(body)
            last_products = context.get("last_discussed_products", [])
            if sizes and len(last_products) == 1:
                flavor = last_products[0]
                size_hints = [f"{flavor} {s}oz" for s in sizes]
                hint = f" (Interpreto que quieres: {', '.join(size_hints)})"
                enhanced_body = f"{body}{hint}"

        system_prompt = self._system_prompt()  # reglas, ejemplos JSON válidos y qué NO hacer (no inventar URLs)
        user_prompt = self._user_prompt(from_number, enhanced_body)  # Prompt del usuario con contexto
        
        # 🔧 CONTEXT VAR: Thread-safe storage para phone_number
        token = current_phone.set(from_number)

        async def _call():
            # 🔧 Timeout aumentado a 8s para horas pico de OpenAI (router mantiene 20s)
            # 🚀 ACTIVADO: Function-calling con herramientas de OrderService
            return await asyncio.wait_for(self._chat_json_with_tools(system_prompt, user_prompt), timeout=8)

        try:
            # Reintenta 3 veces con backoff corto (0.4s → 0.8s → 1.6s)
            reply: BotReply = await retry_async(
                _call,
                attempts=3,
                base_delay=0.4,
                exc=(APIConnectionError, APITimeoutError, RateLimitError, TimeoutError, asyncio.TimeoutError),
            )

            # 🔒 Validación estricta ya aplicada en _chat_json_with_tools
            # Solo verificación de seguridad adicional
            if not isinstance(reply, dict) or "type" not in reply:
                return "Perdón, no entendí. ¿Puedes repetirlo?"
                
            # El resto de validaciones ya están en _validate_and_fix_bot_reply
            return reply

        except Exception:
            # 🔧 Si todos los intentos fallan, devolvemos un texto plano de fallback
            # NOTA: Cuando se implemente function-calling, este fallback será procesado
            # por BotReply para generar una redacción final adecuada
            return "Tuvimos un problema momentáneo. Intenta de nuevo."
        finally:
            # 🔧 CLEANUP: Resetear context var
            current_phone.reset(token)

    def _validate_and_fix_bot_reply(self, data: Any) -> BotReply:
        """
        🔒 VALIDACIÓN ESTRICTA: Asegura que la respuesta cumpla BotReply exactamente
        
        Crítico para producción: evita que respuestas malformadas lleguen al router.
        Si OpenAI devuelve JSON válido pero con estructura incorrecta, esto lo arregla.
        
        Args:
            data: Respuesta raw de OpenAI (puede ser cualquier cosa)
            
        Returns:
            BotReply válido garantizado
        """
        # Validación de tipo base
        if not isinstance(data, dict):
            return {"type": "text", "text_message": "¿En qué puedo ayudarte?"}
        
        # Validación estricta del campo 'type'
        reply_type = data.get("type")
        if reply_type not in ("text", "images", "combined"):
            return {"type": "text", "text_message": "¿En qué puedo ayudarte?"}
        
        # Crear respuesta base válida
        result: BotReply = {"type": reply_type}
        
        # Validación específica por tipo
        if reply_type in ("text", "combined"):
            text_msg = data.get("text_message")
            if isinstance(text_msg, str) and text_msg.strip():
                result["text_message"] = text_msg.strip()
            else:
                result["text_message"] = "¿En qué puedo ayudarte?"
        
        if reply_type in ("images", "combined"):
            images = data.get("images", [])
            if isinstance(images, list) and images:
                # Validar cada imagen
                clean_images = []
                for img in images[:5]:  # Máximo 5 imágenes
                    if isinstance(img, dict) and self._is_http_url(img.get("url")):
                        clean_images.append({
                            "url": img["url"],
                            "caption": str(img.get("caption", "")).strip()
                        })
                
                if clean_images:
                    result["images"] = clean_images
                else:
                    # No hay imágenes válidas, degradar a texto
                    result["type"] = "text"
                    result["text_message"] = result.get("text_message", "¿En qué puedo ayudarte?")
            else:
                # Campo images inválido, degradar a texto
                result["type"] = "text"
                result["text_message"] = result.get("text_message", "¿En qué puedo ayudarte?")
        
        # 🔧 LIMPIEZA FINAL: Remover campos innecesarios
        if result["type"] == "text":
            result.pop("images", None)
        elif result["type"] == "images":
            result.pop("text_message", None)
        
        return result

    def _validate_response_fields(self, reply: BotReply) -> None:
        """
        🔧 MÉTODO LEGACY: Mantenido por compatibilidad
        La validación principal ahora está en _validate_and_fix_bot_reply()
        """
        # Este método ahora es redundante pero se mantiene por compatibilidad
        pass

    def _is_http_url(self, u: str) -> bool:
        """Valida que la URL sea HTTP/HTTPS válida."""
        return isinstance(u, str) and (u.startswith("http://") or u.startswith("https://"))

    # -----------------
    # Prompts y llamada
    # -----------------

    def _system_prompt(self) -> str:
        """
        Instrucciones del asistente con reglas estrictas para herramientas y contexto.
        🔧 REFORZADO: Controles estrictos para evitar respuestas inventadas.
        """
        base_url = os.getenv('NGROK_URL', 'http://localhost:8000')
        return (
            "Eres un asistente de pedidos por WhatsApp. Respondes en español, breve y amable.\n"
            "DEVUELVE SOLO un JSON válido con las claves: type ('text'|'images'|'combined'), text_message (string), images (lista de {url, caption}).\n"
            "\n"
            "USO DE HERRAMIENTAS (OBLIGATORIO):\n"
            "- Si el usuario menciona un sabor o pregunta por disponibilidad: usa primero search_products(user_query).\n"
            "- Si search_products no encuentra nada O si piden el menú: usa get_menu y OBLIGATORIAMENTE usa type='combined' con imagen.\n"
            "- Prohibido inventar listas o productos: NUNCA listes productos sin llamar a una herramienta primero.\n"
            "\n"
            "⚠️ REGLA CRÍTICA PARA get_menu():\n"
            "CUANDO USES get_menu(), DEBES:\n"
            "1. SIEMPRE usar type='combined'\n"
            "2. SIEMPRE incluir la imagen del menú\n"
            "3. NUNCA listar productos en el texto\n"
            "4. Texto breve: solo 'Aquí tienes nuestro menú completo'\n"
            "\n"
            "REGLA DE CONTEXTO (CRÍTICA):\n"
            "- Si el usuario da SOLO tamaños/cantidades (p.ej. 'uno de 8 y otro de 16') y hay un único 'last_discussed_product' en el CONTEXTO JSON, ASUME ese sabor por defecto.\n"
            "- Si en el user prompt aparece un bloque '(Interpreto que quieres: ...)', trátalo como intención vinculante.\n"
            "\n"
            "IMÁGENES:\n"
            f"- SIEMPRE que uses get_menu, responde SOLO con la imagen del menú (NO listes productos en texto).\n"
            f"- Usa type='combined' con texto breve + imagen del menú: {base_url}/static/images/menupaves.jpeg\n"
            "- NUNCA inventes URLs. Solo usa la URL oficial del menú cuando corresponda.\n"
            "\n"
            "FLUJO DE PEDIDO:\n"
            "- Valida sabores/tamaños con herramientas (search_products/get_menu) antes de confirmar.\n"
            "- Si falta un dato, pregunta SOLO por lo que falta.\n"
            "\n"
            "FORMATO DE RESPUESTA (devuelve SOLO un JSON válido):\n"
            "\n"
            "PARA CONVERSACIÓN NORMAL:\n"
            '{"type":"text","text_message":"¡Hola! ¿En qué puedo ayudarte?"}\n'
            "\n"
            "PARA MOSTRAR MENÚ (OBLIGATORIO DESPUÉS DE get_menu):\n"
            '{"type":"combined","text_message":"Aquí tienes nuestro menú completo","images":[{"url":"' + base_url + '/static/images/menupaves.jpeg","caption":"Menú de Pavés"}]}\n'
            "\n"
            "🔧 HERRAMIENTAS DISPONIBLES:\n"
            "- get_menu: Lista COMPLETA de productos (usar para 'qué tienen', 'menú', 'sabores')\n"
            "- search_products: Búsqueda específica (usar cuando mencionen sabor específico)\n"
            "- update_conversation_context: Actualizar contexto (usar cuando cambie el tema)\n"
            "- create_order: Crear pedido (SOLO con datos completos validados)\n"
            "- get_order_status: Estado de pedidos\n"
            "\n"
            "🧠 LECTURA DE CONTEXTO:\n"
            "- En el user prompt encontrarás 'CONTEXT_JSON: {...}' con información clave\n"
            "- last_discussed_products: productos mencionados recientemente\n"
            "- current_order_items: items en pedido actual\n"
            "- last_topic: último tema de conversación\n"
            "- USA esta información para resolver ambigüedades\n"
            "\n"
            "REGLAS CRÍTICAS:\n"
            "- NO inventes productos o precios\n"
            "- SIEMPRE consulta herramientas antes de confirmar disponibilidad\n"
            "- Si hay contexto de un producto y usuario da solo tamaños, ASUME ese producto\n"
            "- DESPUÉS DE USAR get_menu(): OBLIGATORIO usar type='combined' con imagen\n"
            "- Mantén respuestas cortas (1-2 frases)\n"
            )

    def _user_prompt(self, from_number: str, body: str) -> str:
        """
        Contexto del usuario con JSON embebido para mayor claridad del modelo.
        
        Args:
            from_number: Número de teléfono del usuario
            body: Mensaje actual del usuario (puede incluir interpretaciones)
            
        Returns:
            Prompt enriquecido con contexto JSON explícito
        """
        masked = "•••" + from_number[-4:]
        ctx_json = {"last_discussed_products": [], "current_order_items": [], "last_topic": None}

        try:
            from app.models.user_session import UserSession
            session = self.db.query(UserSession).filter(UserSession.phone_number == from_number).first()
            if session and session.context_data:
                c = session.context_data
                ctx_json["last_discussed_products"] = c.get("last_discussed_products", []) or []
                ctx_json["current_order_items"] = c.get("current_order_items", []) or []
                ctx_json["last_topic"] = c.get("last_topic")
        except Exception:
            pass

        # Nota: body ya puede venir con "(Interpreto que quieres: ...)" de interpret_vague_reference
        return (
            f"Usuario {masked} dice: {body}\n"
            "CONTEXT_JSON: " + json.dumps(ctx_json, ensure_ascii=False)
        )

    async def _chat_json(self, system_prompt: str, user_prompt: str) -> BotReply: 
        """
        🔧 MÉTODO LEGACY: Chat JSON sin herramientas (mantenido por compatibilidad)
        
        Ahora usa cliente async nativo y validación estricta.
        Para nuevas implementaciones, usar _chat_json_with_tools().
        """
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.1,  # 🔧 Más determinista (era 0.4)
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=400,
            )

            raw = resp.choices[0].message.content or "{}"
            
            try:
                data = json.loads(raw)
                # 🔒 Usar validación estricta nueva
                return self._validate_and_fix_bot_reply(data)
            except json.JSONDecodeError:
                return {"type": "text", "text_message": "Hubo un error procesando tu pedido. ¿Puedes intentar de nuevo?"}
                
        except Exception:
            return {"type": "text", "text_message": "Algo salió mal. ¿En qué puedo ayudarte?"}

    def _search_products(self, tool_args: Dict) -> Dict:
        """
        🔍 BÚSQUEDA INTELIGENTE DE PRODUCTOS con normalización robusta
        
        Implementa búsqueda tolerante a errores que puede encontrar productos
        incluso con variaciones de nombres, errores de tipeo y sinónimos.
        
        Args:
            tool_args: Argumentos de la herramienta {"user_query": str, "max_results": int}
            
        Returns:
            Resultados de búsqueda con productos coincidentes
        """
        try:
            from app.services.product_matcher import ProductMatcher
            # 🔧 IMPORT BLINDADO: Fallback robusto si falla normalización
            try:
                from app.utils.text_normalizer import normalize_search_query, is_safe_to_map_chocolate_to_milo
            except Exception:
                logging.exception("⚠️ Fallo import normalizador; usando fallback")
                def normalize_search_query(q: str) -> str: 
                    return q.lower().replace("maracuya", "maracuyá")  # Fallback básico
                def is_safe_to_map_chocolate_to_milo(products) -> bool: 
                    return True  # Por seguridad, permitir mapeo
            
            user_query = tool_args.get("user_query", "").strip()
            max_results = tool_args.get("max_results", 5)
            
            if not user_query:
                return {
                    "success": False,
                    "error": "Consulta de búsqueda vacía",
                    "code": "EMPTY_QUERY",
                    "suggestion": "Proporciona un término de búsqueda válido",
                    "next_step": "Prueba con 'get_menu' para ver todos los productos disponibles"
                }
            
            # Obtener productos de la base de datos
            from app.models.paves import Pave
            products = self.db.query(Pave).filter(Pave.available == True).all()
            
            # 🔧 NORMALIZACIÓN ROBUSTA: Usar nueva utilidad
            normalized_query = normalize_search_query(user_query)
            
            # 🔧 SEGURIDAD: Solo mapear chocolate→milo si no hay producto chocolate real
            if 'chocolate' in user_query.lower() and not is_safe_to_map_chocolate_to_milo(products):
                logging.warning("⚠️ No se mapea 'chocolate' → 'milo': existe producto chocolate real")
                normalized_query = user_query.lower()  # Usar query original
            
            # Crear matcher y buscar con query normalizada
            matcher = ProductMatcher(products)
            matches = matcher.find_products(normalized_query, min_score=0.6)
            
            # Limitar resultados
            matches = matches[:max_results]
            
            if not matches:
                return {
                    "success": True,
                    "query": user_query,
                    "normalized_query": normalized_query,
                    "matches": [],
                    "total_matches": 0,
                    "suggestion": "No se encontraron coincidencias. Usa get_menu para ver todos los productos disponibles."
                }
            
            # Formatear resultados (OPTIMIZADO: solo campos esenciales)
            formatted_matches = []
            for match in matches:
                product = match['product']
                formatted_matches.append({
                    "id": product.id,
                    "name": product.name,
                    "size": product.size.value,
                    "price": float(product.price),
                    "emoji": product.emoji,
                    "confidence": round(match['score'], 2),
                    # ingredients solo si es corto (evitar tokens excesivos)
                    "ingredients": product.ingredients[:100] + "..." if len(product.ingredients) > 100 else product.ingredients
                })
            
            result = {
                "success": True,
                "query": user_query,
                "normalized_query": normalized_query,
                "matches": formatted_matches,
                "total_matches": len(formatted_matches)
            }
            
            # 🔁 ACTUALIZACIÓN DETERMINISTA DE CONTEXTO: Si hay matches, actualizar automáticamente
            try:
                if formatted_matches:
                    # Extraer sabores únicos encontrados
                    flavors = list({match["name"] for match in formatted_matches})[:3]  # Máximo 3 para evitar spam
                    phone_number = tool_args.get("phone_number", "")  # Necesitaremos pasarlo desde el caller
                    
                    if phone_number:
                        context_update = {
                            "phone_number": phone_number,
                            "discussed_products": flavors,
                            "current_topic": "eligiendo_sabores"
                        }
                        self._update_conversation_context(context_update)
                        logging.info(f"🧠 Contexto actualizado automáticamente: {flavors}")
            except Exception as e:
                logging.warning(f"⚠️ No se pudo actualizar contexto tras search_products: {e}")
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error en búsqueda de productos: {str(e)}",
                "code": "SEARCH_ERROR",
                "suggestion": "Intenta con una búsqueda más simple",
                "next_step": "Prueba con 'get_menu' para ver todos los productos disponibles"
            }

    def _update_conversation_context(self, tool_args: Dict) -> Dict:
        """
        🧠 ACTUALIZACIÓN DE CONTEXTO CONVERSACIONAL
        
        Actualiza el contexto de la conversación para mantener memoria
        entre mensajes y mejorar la experiencia del usuario.
        
        Args:
            tool_args: Argumentos {"phone_number": str, "discussed_products": [...], etc.}
            
        Returns:
            Resultado de la actualización de contexto
        """
        try:
            phone_number = tool_args.get("phone_number", "").strip()
            if not phone_number:
                return {
                    "success": False,
                    "error": "Número de teléfono requerido",
                    "code": "MISSING_PHONE"
                }
            
            # Obtener o crear sesión
            from app.models.user_session import UserSession
            session = self.db.query(UserSession).filter(UserSession.phone_number == phone_number).first()
            
            if not session:
                # Crear nueva sesión si no existe
                session = UserSession(
                    phone_number=phone_number,
                    phase="ordering",
                    draft_order_json={},
                    context_data={}
                )
                self.db.add(session)
                self.db.flush()
            
            # Actualizar contexto
            context = session.context_data or {}
            
            # Productos discutidos
            discussed_products = tool_args.get("discussed_products", [])
            if discussed_products:
                context["last_discussed_products"] = discussed_products
            
            # Tema actual
            current_topic = tool_args.get("current_topic", "").strip()
            if current_topic:
                context["last_topic"] = current_topic
            
            # Items del pedido en progreso
            order_items = tool_args.get("order_items", [])
            if order_items:
                context["current_order_items"] = order_items
            
            # Timestamp de actualización
            from datetime import datetime
            context["last_updated"] = datetime.now().isoformat()
            
            # Guardar contexto actualizado
            session.context_data = context
            self.db.commit()
            
            return {
                "success": True,
                "message": "Contexto actualizado correctamente",
                "context_updated": {
                    "discussed_products": discussed_products,
                    "current_topic": current_topic,
                    "order_items": order_items
                }
            }
            
        except Exception as e:
            self.db.rollback()
            return {
                "success": False,
                "error": f"Error actualizando contexto: {str(e)}",
                "code": "CONTEXT_UPDATE_ERROR"
            }

    # ------------------------------------------------------------------
    # 🔧 PREPARACIÓN PARA FUNCTION-CALLING (implementar cuando se necesite)
    # ------------------------------------------------------------------
    
    def _tool_defs(self) -> List[Dict]:
        """
        �️ DEFINICIONES DE HERRAMIENTAS: Schemas estrictos para OpenAI function-calling
        
        Crítico: Sin schemas estrictos, el modelo "alucina" parámetros.
        Estos schemas le dicen a OpenAI exactamente qué herramientas tiene disponibles,
        cuándo usarlas y qué parámetros requieren.
        
        Returns:
            Lista de definiciones con schemas JSON estrictos
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_menu",
                    "description": "Obtiene el menú completo de productos (pavés) disponibles para pedidos",
                    "parameters": {
                        "type": "object",
                        "properties": {},  # No requiere parámetros
                        "required": [],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_products",
                    "description": "Busca productos de forma inteligente basado en texto del usuario. Maneja errores de tipeo, sinónimos y variaciones de nombres.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_query": {
                                "type": "string",
                                "description": "Texto del usuario describiendo el producto que busca (ej: 'milo 8 onzas', 'areqipe grande', 'chocolate')",
                                "minLength": 1,
                                "maxLength": 100
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Número máximo de resultados a devolver",
                                "minimum": 1,
                                "maximum": 10,
                                "default": 5
                            },
                            "phone_number": {
                                "type": "string",
                                "description": "Número de teléfono del usuario (opcional, para actualización de contexto)",
                                "pattern": r"^\+?[\d\s\-\(\)]+$"
                            }
                        },
                        "required": ["user_query"],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "update_conversation_context",
                    "description": "Actualiza el contexto de la conversación para recordar productos discutidos, temas de conversación, etc.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "phone_number": {
                                "type": "string",
                                "description": "Número de teléfono del usuario",
                                "pattern": r"^\+?[\d\s\-\(\)]+$"
                            },
                            "discussed_products": {
                                "type": "array",
                                "description": "Lista de productos que se están discutiendo actualmente",
                                "items": {"type": "string"},
                                "maxItems": 10
                            },
                            "current_topic": {
                                "type": "string",
                                "description": "Tema actual de la conversación (ej: 'eligiendo_sabores', 'confirmando_pedido', 'consultando_menu')",
                                "maxLength": 100
                            },
                            "order_items": {
                                "type": "array",
                                "description": "Items del pedido en progreso (opcional)",
                                "items": {"type": "string"},
                                "maxItems": 20
                            }
                        },
                        "required": ["phone_number"],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function", 
                "function": {
                    "name": "create_order",
                    "description": "Crea un nuevo pedido completo. SOLO usar cuando tengas TODOS los datos requeridos.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "phone_number": {
                                "type": "string",
                                "description": "Número de teléfono del cliente",
                                "pattern": r"^\+?[\d\s\-\(\)]+$"
                            },
                            "items": {
                                "type": "array",
                                "description": "Lista de productos a ordenar",
                                "minItems": 1,
                                "maxItems": 50,
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "product_id": {
                                            "type": "integer",
                                            "description": "ID del producto del menú",
                                            "minimum": 1
                                        },
                                        "quantity": {
                                            "type": "integer",
                                            "description": "Cantidad del producto",
                                            "minimum": 1,
                                            "maximum": 20
                                        },
                                        "notes": {
                                            "type": "string",
                                            "description": "Notas especiales para el producto (opcional)",
                                            "maxLength": 200
                                        }
                                    },
                                    "required": ["product_id", "quantity"],
                                    "additionalProperties": False
                                }
                            },
                            "delivery_address": {
                                "type": "string",
                                "description": "Dirección completa de entrega",
                                "minLength": 10,
                                "maxLength": 300
                            },
                            "payment_method": {
                                "type": "string",
                                "description": "Método de pago aceptado",
                                "enum": ["efectivo", "tarjeta", "transferencia"],
                                "pattern": "^(efectivo|tarjeta|transferencia)$"
                            },
                            "notes": {
                                "type": "string",
                                "description": "Notas adicionales para el pedido (opcional)",
                                "maxLength": 500
                            }
                        },
                        "required": ["phone_number", "items", "delivery_address", "payment_method"],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_order_status", 
                    "description": "Consulta el estado de pedidos del cliente. Muestra últimos pedidos o un pedido específico.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "phone_number": {
                                "type": "string",
                                "description": "Número de teléfono del cliente",
                                "pattern": r"^\+?[\d\s\-\(\)]+$"
                            },
                            "order_id": {
                                "type": "integer", 
                                "description": "ID específico del pedido a consultar (opcional)",
                                "minimum": 1
                            }
                        },
                        "required": ["phone_number"],
                        "additionalProperties": False
                    }
                }
            }
        ]
    
    @staticmethod
    def _mask_phone(phone: Optional[str]) -> str:
        """Enmascara teléfono para logs seguros"""
        if not phone or len(phone) < 4:
            return "unknown"
        return "•••" + phone[-4:]
    
    async def _dispatch_tool(self, tool_name: str, tool_args: Dict) -> Dict:
        """
        🎯 DISPATCHER DE HERRAMIENTAS: Ejecuta llamadas reales a OrderService
        
        Maneja errores semánticamente para que OpenAI pueda recuperarse en la 2ª llamada.
        Incluye timeouts específicos por herramienta y límites de tamaño de respuesta.
        
        Args:
            tool_name: Nombre de la herramienta a ejecutar
            tool_args: Argumentos validados por OpenAI schema
            
        Returns:
            Resultado del OrderService o error semántico para que OpenAI se recupere
        """
        # 🔧 Timeouts específicos por herramienta
        TOOL_TIMEOUTS = {
            "get_menu": 2.0,                    # Consulta rápida
            "search_products": 2.0,             # Búsqueda inteligente
            "update_conversation_context": 1.0, # Actualización de contexto
            "create_order": 5.0,                # Operación compleja
            "get_order_status": 3.0,            # Consulta moderada
        }
        
        # 🔧 Límites de tamaño de respuesta (caracteres)
        MAX_RESULT_SIZE = 2000
        
        # Validación de herramienta existente
        if tool_name not in TOOL_TIMEOUTS:
            return {
                "success": False,
                "error": f"Herramienta '{tool_name}' no disponible",
                "code": "UNKNOWN_TOOL",
                "available_tools": list(TOOL_TIMEOUTS.keys()),
                "suggestion": "Usa una herramienta válida",
                "next_step": "Prueba con 'get_menu' para ver productos disponibles"
            }
        
        timeout = TOOL_TIMEOUTS[tool_name]
        
        # 🔧 INYECCIÓN AUTOMÁTICA: phone_number desde context var para herramientas que lo necesitan
        if tool_name in ("search_products", "update_conversation_context", "get_order_status"):
            tool_args.setdefault("phone_number", current_phone.get())
        
        try:
            # Ejecutar herramienta con timeout específico
            if tool_name == "get_menu":
                result = await asyncio.wait_for(
                    asyncio.to_thread(self.order_service.get_menu),
                    timeout=timeout
                )
                
            elif tool_name == "search_products":
                result = await asyncio.wait_for(
                    asyncio.to_thread(self._search_products, tool_args),
                    timeout=timeout
                )
                
            elif tool_name == "update_conversation_context":
                result = await asyncio.wait_for(
                    asyncio.to_thread(self._update_conversation_context, tool_args),
                    timeout=timeout
                )
                
            elif tool_name == "create_order":
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.order_service.create_order,
                        phone_number=tool_args["phone_number"],
                        items=tool_args["items"],
                        delivery_address=tool_args["delivery_address"],
                        payment_method=tool_args["payment_method"],
                        notes=tool_args.get("notes")
                    ),
                    timeout=timeout
                )
                
            elif tool_name == "get_order_status":
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.order_service.get_order_status,
                        phone_number=tool_args["phone_number"],
                        order_id=tool_args.get("order_id")
                    ),
                    timeout=timeout
                )
            
            # 🔧 Límite de tamaño de respuesta (evita tokens excesivos)
            result_str = str(result)
            if len(result_str) > MAX_RESULT_SIZE:
                # Truncar preservando estructura JSON
                if isinstance(result, dict) and result.get("success") and "data" in result:
                    truncated_data = str(result["data"])[:MAX_RESULT_SIZE-200]  # Espacio para metadata
                    result = {
                        "success": True,
                        "data": f"{truncated_data}... (truncado por tamaño)",
                        "truncated": True,
                        "original_size": len(result_str)
                    }
            
            return result
            
        except asyncio.TimeoutError:
            # Error semántico para que OpenAI se recupere
            return {
                "success": False,
                "error": f"La operación {tool_name} tomó demasiado tiempo",
                "code": "TIMEOUT_ERROR",
                "timeout_seconds": timeout,
                "suggestion": "Intenta de nuevo o usa una consulta más simple",
                "next_step": "Prueba con 'menú' para ver opciones disponibles"
            }
            
        except Exception as e:
            # Error semántico con contexto para OpenAI
            return {
                "success": False,
                "error": f"Error ejecutando {tool_name}: {str(e)}",
                "code": "EXECUTION_ERROR",
                "suggestion": "Verifica los datos proporcionados e intenta nuevamente",
                "next_step": "Prueba con 'menú' para ver opciones disponibles"
            }
    
    async def _chat_json_with_tools(self, system_prompt: str, user_prompt: str) -> BotReply:
        """
        🔧 FUNCTION-CALLING CONTROLADO: Chat con herramientas disponibles
        
        Flujo controlado:
        1. Primera llamada: OpenAI decide si usar herramientas
        2. Si usa tool: ejecutar SOLO 1 herramienta (límite estricto por turno)
        3. Segunda llamada: OpenAI genera BotReply final con resultado
        
        Control estricto: máximo 1 tool call por turno para latencia/control predecible.
        
        Args:
            system_prompt: Instrucciones del sistema con guías de herramientas
            user_prompt: Mensaje del usuario
            
        Returns:
            BotReply validado estrictamente
        """
        tools = self._tool_defs()
        
        try:
            # 🎯 Primera llamada: OpenAI decide si usar herramientas
            response1 = await self.client.chat.completions.create(
                model=self.model,
                temperature=0.1,  # 🔧 Más determinista para tools (era 0.4)
                tools=tools,
                tool_choice="auto",  # OpenAI decide automáticamente
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=250,  # 🔧 OPTIMIZADO: Menos tokens para decisión de tools
            )
            
            message1 = response1.choices[0].message
            
            # 📝 LOGGING BÁSICO: Registrar uso de herramientas
            if message1.tool_calls:
                tool_names = [tc.function.name for tc in message1.tool_calls]
                logging.info(f"🔧 Bot usó herramientas: {', '.join(tool_names)}")
            
            # ¿OpenAI decidió usar herramientas?
            if message1.tool_calls:
                # 🔧 LÍMITE ESTRICTO: Solo 1 tool call por turno para latencia predecible
                tool_call = message1.tool_calls[0]  # Solo el primero
                tool_name = tool_call.function.name
                
                try:
                    tool_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}
                
                # 🔧 INYECTAR PHONE NUMBER para actualización automática de contexto
                # Ya se inyecta automáticamente via ContextVar en _dispatch_tool
                
                # 🎯 Ejecutar herramienta única
                tool_result = await self._dispatch_tool(tool_name, tool_args)
                
                # 📝 LOGGING: Registrar resultado de herramienta (SIN PII)
                success = tool_result.get("success", False)
                masked_phone = self._mask_phone(tool_args.get("phone_number"))
                logging.info(f"🔧 {tool_name} para {masked_phone}: {'✅' if success else '❌'}")
                
                # Preparar resultado para segunda llamada
                tool_results = [{
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result, ensure_ascii=False)
                }]
                
                # 🚀 Segunda llamada: OpenAI genera respuesta final con resultado
                messages_for_second_call = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                    message1,  # Mensaje original con tool_calls
                ] + tool_results  # Resultado de la herramienta única
                
                response2 = await self.client.chat.completions.create(
                    model=self.model,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    messages=messages_for_second_call,
                    max_tokens=700,  # 🔧 AUMENTADO: Más espacio para respuestas con tool results
                )
                
                final_content = response2.choices[0].message.content or "{}"
                
            else:
                # No necesita herramientas, respuesta directa con JSON format
                response_direct = await self.client.chat.completions.create(
                    model=self.model,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=400,
                )
                
                final_content = response_direct.choices[0].message.content or "{}"
            
            # 🔒 Validación estricta del resultado final
            try:
                raw_data = json.loads(final_content)
                return self._validate_and_fix_bot_reply(raw_data)
            except json.JSONDecodeError:
                return {"type": "text", "text_message": "Hubo un error procesando tu consulta. ¿Puedes intentar de nuevo?"}
                
        except Exception as e:
            # Fallback robusto
            return {"type": "text", "text_message": "Tuvimos un problema momentáneo. ¿En qué puedo ayudarte?"}

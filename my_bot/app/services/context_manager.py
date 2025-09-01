"""
🧠 CONTEXT MANAGER - GESTIÓN AUTOMÁTICA DE CONTEXTO
===================================================

Este módulo maneja automáticamente el contexto de conversación
sin requerir tool calls explícitos, mejorando la experiencia
del usuario de forma transparente.
"""

import re
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.user_session import UserSession

class ConversationContextManager:
    """
    Gestor automático de contexto conversacional que:
    - Detecta productos mencionados automáticamente
    - Mantiene contexto entre mensajes
    - Interpreta referencias vagas basado en contexto
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def extract_products_from_message(self, message: str) -> List[str]:
        """
        Extrae automáticamente productos mencionados en el mensaje (MEJORADO)
        
        Args:
            message: Mensaje del usuario
            
        Returns:
            Lista de productos detectados
        """
        message_lower = message.lower()
        detected_products = []
        
        # Productos conocidos y sus variaciones (AMPLIADO)
        product_patterns = {
            "maracuya": ["maracuya", "maracuyá", "passion", "parcha"],  # Con y sin acento
            "milo": ["milo", "chocolate", "choco", "cacao"],
            "arequipe": ["arequipe", "areqipe", "dulce de leche", "manjar"],  # Incluye error común
            "leche_klim": ["klim", "leche klim", "leche"]
        }
        
        for product, variations in product_patterns.items():
            for variation in variations:
                if variation in message_lower:
                    # Normalizar nombre del producto
                    product_name = {
                        "maracuya": "Maracuyá",  # Con acento para consistencia
                        "milo": "Pave de Milo", 
                        "arequipe": "Arequipe",
                        "leche_klim": "Leche Klim"
                    }[product]
                    
                    if product_name not in detected_products:
                        detected_products.append(product_name)
                    break
        
        return detected_products
    
    def extract_sizes_from_message(self, message: str) -> List[str]:
        """
        Extrae tamaños mencionados en el mensaje
        
        Args:
            message: Mensaje del usuario
            
        Returns:
            Lista de tamaños detectados
        """
        message_lower = message.lower()
        detected_sizes = []
        
        # Patrones de tamaños
        size_patterns = {
            "8 Onzas": ["8", "ocho", "chico", "pequeño", "small"],
            "16 Onzas": ["16", "dieciseis", "dieciséis", "grande", "large", "big"]
        }
        
        for size, variations in size_patterns.items():
            for variation in variations:
                if variation in message_lower:
                    if size not in detected_sizes:
                        detected_sizes.append(size)
                    break
        
        return detected_sizes
    
    def update_context_automatically(self, phone_number: str, user_message: str) -> Dict[str, Any]:
        """
        Actualiza automáticamente el contexto basado en el mensaje del usuario
        
        Args:
            phone_number: Número del usuario
            user_message: Mensaje del usuario
            
        Returns:
            Contexto actualizado
        """
        try:
            # Obtener o crear sesión
            session = self.db.query(UserSession).filter(
                UserSession.phone_number == phone_number
            ).first()
            
            if not session:
                session = UserSession(
                    phone_number=phone_number,
                    phase="ordering",
                    draft_order_json={},
                    context_data={}
                )
                self.db.add(session)
                self.db.flush()
            
            context = session.context_data or {}
            
            # Detectar productos mencionados
            detected_products = self.extract_products_from_message(user_message)
            if detected_products:
                context["last_discussed_products"] = detected_products
                context["last_topic"] = "eligiendo_productos"
            
            # Detectar tamaños mencionados
            detected_sizes = self.extract_sizes_from_message(user_message)
            if detected_sizes:
                context["mentioned_sizes"] = detected_sizes
                if detected_products:
                    context["last_topic"] = "especificando_tamaños"
            
            # Si menciona cantidades sin productos específicos, pero hay contexto de productos
            if re.search(r'\b(uno|una|dos|tres|\d+)\b', user_message.lower()) and not detected_products:
                if context.get("last_discussed_products"):
                    context["last_topic"] = "especificando_cantidades"
            
            # Timestamp
            context["last_updated"] = datetime.now().isoformat()
            
            # Guardar contexto
            session.context_data = context
            self.db.commit()
            
            return context
            
        except Exception as e:
            self.db.rollback()
            return {}
    
    def get_context(self, phone_number: str) -> Dict[str, Any]:
        """
        Obtiene el contexto actual del usuario
        
        Args:
            phone_number: Número del usuario
            
        Returns:
            Contexto actual
        """
        try:
            session = self.db.query(UserSession).filter(
                UserSession.phone_number == phone_number
            ).first()
            
            return session.context_data if session else {}
            
        except Exception:
            return {}
    
    def interpret_vague_reference(self, user_message: str, context: Dict[str, Any]) -> Optional[str]:
        """
        Interpreta referencias vagas basado en el contexto (MEJORADO)
        
        Args:
            user_message: Mensaje del usuario
            context: Contexto actual
            
        Returns:
            Interpretación clara o None
        """
        message_lower = user_message.lower()
        
        # Si ya hay una interpretación previa, no duplicar
        if "interpreto que quieres:" in message_lower:
            return None
        
        # Detectar tamaños/cantidades con regex mejorado
        sizes = re.findall(r'\b(8|16|ocho|dieciséis|dieciseis|uno.*?8|otro.*?16|una.*?8|otra.*?16)\b', message_lower)
        # Normalizar tamaños detectados
        normalized_sizes = []
        for size in sizes:
            if '8' in size or 'ocho' in size:
                normalized_sizes.append('8oz')
            elif '16' in size or 'dieciséis' in size or 'dieciseis' in size:
                normalized_sizes.append('16oz')
        
        discussed_products = context.get("last_discussed_products", [])
        
        # REGLA PRINCIPAL: Si detecta tamaños sin sabor y hay 1 producto en contexto
        if normalized_sizes and discussed_products and len(discussed_products) == 1:
            if not self.extract_products_from_message(user_message):
                flavor = discussed_products[0]
                pairs = [f"{flavor} {s}" for s in normalized_sizes]
                return f"Interpreto que quieres: {', '.join(pairs)}"
        
        # REGLA ALTERNATIVA: Cantidades genéricas con contexto de producto
        quantities = re.findall(r'\b(uno|una|dos|tres|cuatro|cinco|\d+)\b', message_lower)
        if quantities and discussed_products and len(discussed_products) == 1:
            if not self.extract_products_from_message(user_message) and not normalized_sizes:
                flavor = discussed_products[0]
                # Si solo mencionan cantidades sin especificar tamaño, sugerir clarificación
                qty_text = ", ".join(quantities)
                return f"Interpreto que quieres {qty_text} de {flavor}, pero ¿de qué tamaño?"
        
        # REGLA ESPECIAL: "el mismo" o referencias pronominales
        if any(word in message_lower for word in ["el mismo", "igual", "también", "otro igual"]):
            if discussed_products:
                return f"Interpreto que quieres otro {discussed_products[0]}"
        
        return None

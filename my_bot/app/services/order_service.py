"""
📦 ORDER SERVICE - GESTOR DE PEDIDOS Y SESIONES
===============================================

Este módulo es el corazón del sistema de pedidos, manejando todo el ciclo de vida
desde la consulta del menú hasta la confirmación de pedidos de pavé.

Autor: Sistema de Gestión de Pedidos WhatsApp
Fecha: 2025-08-21
Versión: 2.0

🎯 PROPÓSITO PRINCIPAL:
- Gestionar el menú de productos (pavés)
- Crear, actualizar, cancelar y consultar pedidos
- Manejar sesiones de usuario y fases de conversación
- Validar datos de entrada y mantener consistencia

🏗️ ARQUITECTURA MODERNA v2.0:
- Decoradores de transacciones (@db_transaction, @read_only)
- Eliminación de código duplicado try/except
- Manejo automático de commit/rollback
- Validación robusta de datos
- Respuestas estandarizadas

🔄 FLUJO TÍPICO DE PEDIDO:
1. Usuario consulta menú → get_menu()
2. Bot crea/actualiza sesión → update_session_phase()
3. Usuario especifica productos → create_order()
4. Sistema valida items y calcula total
5. Pedido se guarda en estado PENDIENTE
6. Usuario puede consultar estado → get_order_status()

📊 FUNCIONES PRINCIPALES:

🔍 CONSULTAS (decoradas con @read_only):
- get_menu(): Obtiene productos disponibles
- get_user_session(): Info de sesión actual
- get_order_status(): Estado de pedidos

✏️ MODIFICACIONES (decoradas con @db_transaction):
- create_user(): Nuevo cliente y sesión
- create_order(): Pedido completo con validaciones
- update_order(): Modificar pedido pendiente
- cancel_order(): Cancelar pedido

🛡️ VALIDACIONES AUTOMÁTICAS:
- Items válidos vs productos disponibles
- Cantidades positivas
- Métodos de pago reconocidos
- Estados de pedido permitidos
- Límites de items por pedido (max 50)

💰 CÁLCULOS MONETARIOS:
- Redondeo preciso a 2 decimales
- Subtotales por item
- Total general del pedido
- Manejo de tipos Decimal para precisión

📱 INTEGRACIÓN CON WHATSAPP:
- Identificación por número de teléfono
- Sesiones persistentes entre conversaciones
- Fases de conversación (greeting, ordering, etc.)
- Borradores de pedido temporal

⚡ OPTIMIZACIONES:
- Queries batch para evitar N+1
- Validación antes de procesamiento
- Manejo eficiente de transacciones
- Cacheo de productos en memoria durante validación

CHANGELOG v2.0 (2025-08-20):
✅ Agregados decoradores de transacciones para código más limpio
✅ Corregidos problemas de transacciones anidadas  
✅ Mejorado manejo de errores consistente
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session
from sqlalchemy import and_, delete
from sqlalchemy.sql import func

# 🎯 Decoradores para manejo automático de transacciones
from app.utils.decorators import db_transaction, read_only

from app.models.cliente import Cliente
from app.models.paves import Pave
from app.models.pedido import Pedido, DetallePedido, EstadoPedido, MedioPago
from app.models.user_session import UserSession, ConversationPhase

logger = logging.getLogger(__name__)

# Mapeo tolerante para métodos de pago
PAYMENT_METHOD_MAP = {
    "efectivo": MedioPago.EFECTIVO,
    "cash": MedioPago.EFECTIVO,
    "dinero": MedioPago.EFECTIVO,
    "tarjeta": MedioPago.TARJETA,
    "card": MedioPago.TARJETA,
    "credito": MedioPago.TARJETA,
    "debito": MedioPago.TARJETA,
    "transferencia": MedioPago.TRANSFERENCIA_BANCARIA,
    "transfer": MedioPago.TRANSFERENCIA_BANCARIA,
    "banco": MedioPago.TRANSFERENCIA_BANCARIA,
    "transferencia_bancaria": MedioPago.TRANSFERENCIA_BANCARIA,
    "nequi": MedioPago.TRANSFERENCIA_BANCARIA,
}

class OrderService:
    """Servicio para manejar pedidos, menú y sesiones de usuario"""

    def __init__(self, db: Session):
        self.db = db

    def _money(self, amount: Decimal) -> Decimal:
        """
        Redondea cantidades monetarias a 2 decimales
        
        Args:
            amount: Cantidad a redondear
            
        Returns:
            Decimal redondeado a 2 decimales
        """
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _normalize_payment_method(self, payment_method: str) -> Optional[MedioPago]:
        """
        Normaliza método de pago de forma tolerante
        
        Args:
            payment_method: Método de pago en cualquier formato
            
        Returns:
            MedioPago enum o None si no se reconoce
        """
        if not payment_method:
            return None
            
        # Normalizar: lowercase, sin espacios extra
        normalized = payment_method.lower().strip().replace(" ", "_")
        return PAYMENT_METHOD_MAP.get(normalized)

    def _validate_order_items(self, items: List[Dict]) -> Dict[str, Any]:
        """
        Valida lista de items para pedido
        
        Args:
            items: Lista de items a validar
            
        Returns:
            Dict con items válidos, inválidos y errores
        """
        if not items or not isinstance(items, list):
            return {
                "valid_items": [],
                "invalid_items": [],
                "errors": ["La lista de items está vacía o es inválida"]
            }

        # Cap suave para evitar abuso
        if len(items) > 50:
            return {
                "valid_items": [],
                "invalid_items": [],
                "errors": ["Demasiados items"]
            }

        valid_items = []
        invalid_items = []
        errors = []

        # Prefetch todos los productos en una sola query (fix N+1)
        product_ids = [
            item.get("product_id") for item in items 
            if isinstance(item, dict) and isinstance(item.get("product_id"), int)
        ]
        
        if not product_ids:
            return {
                "valid_items": [],
                "invalid_items": [],
                "errors": ["No valid product_id values"]
            }

        # Una sola query para todos los productos
        paves_dict = {
            pave.id: pave 
            for pave in self.db.query(Pave).filter(Pave.id.in_(product_ids)).all()
        }

        for i, item in enumerate(items):
            if not isinstance(item, dict):
                invalid_items.append({"index": i, "item": item, "error": "Item must be a dictionary"})
                continue
                
            # Validar product_id
            product_id = item.get("product_id")
            if not isinstance(product_id, int) or product_id <= 0:
                invalid_items.append({"index": i, "item": item, "error": "Invalid product_id"})
                continue
                
            # Validar quantity
            quantity = item.get("quantity", 1)
            if not isinstance(quantity, int) or quantity <= 0:
                invalid_items.append({"index": i, "item": item, "error": "Invalid quantity"})
                continue
                
            # Verificar que el producto existe y está disponible (desde dict cacheado)
            pave = paves_dict.get(product_id)
            if not pave:
                invalid_items.append({"index": i, "item": item, "error": f"Product {product_id} not found"})
                continue
                
            if not pave.available:
                invalid_items.append({"index": i, "item": item, "error": f"Product {product_id} not available"})
                continue
                
            valid_items.append({
                "product_id": product_id,
                "quantity": quantity,
                "notes": item.get("notes", ""),
                "pave": pave
            })
        
        if invalid_items:
            errors.append(f"Found {len(invalid_items)} invalid items")
            
        return {
            "valid_items": valid_items,
            "invalid_items": invalid_items,
            "errors": errors
        }

    # ==========================================
    # FUNCIONES PARA FUNCTION CALLING
    # ==========================================

    @read_only  # 🎯 Decorador: manejo automático de errores para consultas
    def get_menu(self) -> Dict[str, Any]:
        """
        Obtiene el menú disponible
        
        Returns:
            Dict con productos disponibles
            
        🎯 DECORADOR: @read_only
        - Manejo automático de errores
        - No requiere try/except manual
        - Rollback automático en caso de error
        """
        paves = (self.db.query(Pave)
                .filter(Pave.available.is_(True))
                .order_by(Pave.name.asc())
                .all())
        
        menu_items = []
        for pave in paves:
            menu_items.append({
                "id": pave.id,
                "name": pave.name,
                "ingredients": pave.ingredients,
                "size": pave.size.value,
                "price": float(pave.price),  # Solo para JSON response
                "emoji": pave.emoji,
                "available": pave.available
            })
        
        return {
            "success": True,
            "menu_items": menu_items,
            "total_items": len(menu_items)
        }

    @read_only  # 🎯 Decorador: consulta de solo lectura con manejo automático de errores
    def get_user_session(self, phone_number: str) -> Dict[str, Any]:
        """
        Obtiene la sesión actual del usuario
        
        Args:
            phone_number: Número de teléfono del usuario
            
        Returns:
            Dict con información de la sesión
            
        🎯 DECORADOR: @read_only
        - Consulta de solo lectura
        - Manejo automático de errores
        - Sin try/except manual necesario
        """
        # Buscar sesión por teléfono (identificador principal)
        session = self.db.query(UserSession).filter(UserSession.phone_number == phone_number).first()
        
        if not session:
            return {
                "success": True,
                "session": None,
                "client": None,
                "is_new_user": True
            }
        
        # Obtener cliente si existe
        client_data = None
        if session.cliente_id and session.cliente:
            client_data = {
                "id": session.cliente.id,
                "name": session.cliente.nombre,
                "phone": session.cliente.numero_whatsapp,
                "address": session.cliente.direccion,
                "last_order": session.cliente.ultimo_pedido.isoformat() if session.cliente.ultimo_pedido else None
            }
        
        session_data = {
            "phase": session.phase,
            "draft_order": session.draft_order_json,     # Siempre dict válido (nullable=False)
            "context_data": session.context_data,        # Siempre dict válido (nullable=False)
            "last_interaction": session.last_interaction_at.isoformat() if session.last_interaction_at else None
        }
        
        return {
            "success": True,
            "session": session_data,
            "client": client_data,
            "is_new_user": session.cliente_id is None
        }

    @db_transaction
    def create_user(self, phone_number: str, name: Optional[str] = None, address: Optional[str] = None) -> Dict[str, Any]:
        """
        Crea un nuevo usuario y su sesión
        
        🔧 DECORATOR: @db_transaction
        - Maneja automáticamente commit/rollback de transacciones
        - Elimina necesidad de try/except manual para transacciones
        
        Args:
            phone_number: Número de teléfono
            name: Nombre del cliente (opcional)
            address: Dirección del cliente (opcional)
            
        Returns:
            Dict con información del usuario creado
        """
        # Verificar si ya existe sesión - hacer idempotente
        existing_session = self.db.query(UserSession).filter(UserSession.phone_number == phone_number).first()
        if existing_session:
            # Devolver sesión existente en lugar de error
            client_data = None
            if existing_session.cliente_id and existing_session.cliente:
                client_data = {
                    "id": existing_session.cliente.id,
                    "name": existing_session.cliente.nombre,
                    "phone": existing_session.cliente.numero_whatsapp,
                    "address": existing_session.cliente.direccion
                }
            
            return {
                "success": True,
                "client": client_data,
                "session": {
                    "phase": existing_session.phase,
                    "draft_order": existing_session.draft_order_json or {},
                    "context_data": existing_session.context_data or {}
                },
                "existed": True  # Indicar que ya existía
            }
        
        # Crear cliente si se proporcionan datos
        cliente = None
        if name or address:
            cliente = Cliente(
                numero_whatsapp=phone_number,
                nombre=name,
                direccion=address
            )
            self.db.add(cliente)
            self.db.flush()  # Para obtener el ID
        
        # Crear sesión
        session = UserSession(
            cliente_id=cliente.id if cliente else None,
            phone_number=phone_number,
            phase=ConversationPhase.GREETING.value,
            draft_order_json={},  # Valor por defecto para NOT NULL JSONB
            context_data={}       # Valor por defecto para NOT NULL JSONB
        )
        self.db.add(session)
        
        client_data = None
        if cliente:
            client_data = {
                "id": cliente.id,
                "name": cliente.nombre,
                "phone": cliente.numero_whatsapp,
                "address": cliente.direccion
            }
        
        return {
            "success": True,
            "client": client_data,
            "session": {
                "phase": session.phase,
                "draft_order": {},
                "context_data": {}
            }
        }

    @db_transaction
    def update_user(self, phone_number: str, name: Optional[str] = None, address: Optional[str] = None) -> Dict[str, Any]:
        """
        Actualiza información del usuario
        
        🔧 DECORATOR: @db_transaction
        - Maneja automáticamente commit/rollback de transacciones
        - Elimina necesidad de try/except manual para transacciones
        
        Args:
            phone_number: Número de teléfono
            name: Nuevo nombre (opcional)
            address: Nueva dirección (opcional)
            
        Returns:
            Dict con resultado de la actualización
        """
        cliente = self.db.query(Cliente).filter(Cliente.numero_whatsapp == phone_number).first()
        if not cliente:
            return {"success": False, "error": "Cliente no encontrado"}
        
        if name:
            cliente.nombre = name
        if address:
            cliente.direccion = address
            
        return {
            "success": True,
            "client": {
                "id": cliente.id,
                "name": cliente.nombre,
                "phone": cliente.numero_whatsapp,
                "address": cliente.direccion
            }
        }

    @db_transaction  # 🎯 Decorador: commit/rollback automático + manejo de errores
    def create_order(self, phone_number: str, items: List[Dict], delivery_address: str, 
                    payment_method: str, notes: Optional[str] = None) -> Dict[str, Any]:
        """
        Crea un nuevo pedido
        
        Args:
            phone_number: Número de teléfono del cliente
            items: Lista de items [{"product_id": int, "quantity": int, "notes": str}]
            delivery_address: Dirección de entrega
            payment_method: Método de pago ("efectivo", "tarjeta", "transferencia_bancaria")
            notes: Notas adicionales del pedido
            
        Returns:
            Dict con información del pedido creado
            
        🎯 DECORADOR: @db_transaction
        - Commit automático al final
        - Rollback automático en errores
        - Manejo de errores estandarizado
        - ¡Sin try/except manual!
        """
        # Validar items antes de comenzar
        validation = self._validate_order_items(items)
        if not validation["valid_items"]:
            return {
                "success": False, 
                "error": "No se encontraron items válidos",
                "details": validation["errors"],
                "invalid_items": validation["invalid_items"]
            }
        
        # Buscar sesión (que puede tener o no cliente)
        session = self.db.query(UserSession).filter(UserSession.phone_number == phone_number).first()
        if not session:
            return {"success": False, "error": "Sesión no encontrada"}
        
        # Si no hay cliente asociado, crear uno básico
        if not session.cliente_id:
            cliente = Cliente(numero_whatsapp=phone_number)
            self.db.add(cliente)
            self.db.flush()  # Para obtener el ID
            session.cliente_id = cliente.id
        else:
            cliente = session.cliente
            
        if not cliente:
            return {"success": False, "error": "Cliente no encontrado"}
        
        # Validar método de pago
        medio_pago = self._normalize_payment_method(payment_method)
        if not medio_pago:
            return {"success": False, "error": f"Método de pago inválido: {payment_method}"}
        
        # 🚀 Crear pedido (sin try/except - el decorador lo maneja)
        pedido = Pedido(
            cliente_id=cliente.id,
            estado=EstadoPedido.PENDIENTE,
            medio_pago=medio_pago,
            direccion_entrega=delivery_address,
            notas=notes,
            total=Decimal('0')  # Se calculará después
        )
        self.db.add(pedido)
        self.db.flush()
        
        # Agregar detalles y calcular total
        total = Decimal('0')
        items_added = []
        
        for item in validation["valid_items"]:
            pave = item["pave"]
            cantidad = item["quantity"]
            precio_unitario = Decimal(str(pave.price))  # Convertir a Decimal
            subtotal = self._money(precio_unitario * cantidad)  # Redondeo explícito
            
            detalle = DetallePedido(
                pedido_id=pedido.id,
                pave_id=pave.id,
                cantidad=cantidad,
                precio_unitario=precio_unitario,
                nombre_pave=pave.name,
                tamano_pave=pave.size.value,
                subtotal=subtotal
            )
            self.db.add(detalle)
            total += subtotal
            
            items_added.append({
                "product_id": pave.id,
                "name": pave.name,
                "quantity": cantidad,
                "price": float(precio_unitario),  # Para JSON
                "subtotal": float(subtotal)       # Para JSON
            })
        
        # � Refresh para obtener campos con server_default (fecha_pedido) ANTES de calcular total
        self.db.refresh(pedido)
        
        # 💾 Ahora calcular y asignar total (después del refresh)
        total_calculado = self._money(total)
        pedido.total = total_calculado  # Redondeo final del total
        
        # Actualizar cliente y sesión
        cliente.ultimo_pedido = func.now()  # Timestamp del servidor DB
        session.phase = ConversationPhase.COMPLETED.value
        session.draft_order_json = {}  # Limpiar borrador (no None)
        # last_interaction_at se actualiza automáticamente con onupdate
        
        # ✅ Return exitoso - el decorador hará commit automático
        return {
            "success": True,
            "data": {
                "order_id": pedido.id,
                "total": float(total_calculado),  # 🔧 Usar total calculado
                "status": pedido.estado.value,
                "payment_method": pedido.medio_pago.value,
                "delivery_address": pedido.direccion_entrega,
                "items": items_added,
                "created_at": pedido.fecha_pedido.isoformat()
            },
            "skipped_items": validation["invalid_items"] or []
        }

    def get_order_status(self, phone_number: str, order_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Obtiene el estado de un pedido o los últimos pedidos del usuario
        
        Args:
            phone_number: Número de teléfono del cliente
            order_id: ID específico del pedido (opcional, si no se proporciona devuelve los últimos)
            
        Returns:
            Dict con información del/los pedido(s)
        """
        try:
            # Buscar sesión y cliente (consistente con otras funciones)
            session = self.db.query(UserSession).filter(UserSession.phone_number == phone_number).first()
            if not session or not session.cliente_id:
                return {"success": False, "error": "Cliente no encontrado"}
            
            cliente_id = session.cliente_id
            
            if order_id:
                # Buscar pedido específico
                pedido = self.db.query(Pedido).filter(
                    and_(Pedido.id == order_id, Pedido.cliente_id == cliente_id)
                ).first()
                
                if not pedido:
                    return {"success": False, "error": "Pedido no encontrado"}
                
                return {
                    "success": True,
                    "order": {
                        "id": pedido.id,
                        "status": pedido.estado.value,
                        "total": float(pedido.total),
                        "payment_method": pedido.medio_pago.value,
                        "delivery_address": pedido.direccion_entrega,
                        "notes": pedido.notas,
                        "created_at": pedido.fecha_pedido.isoformat(),
                        "estimated_delivery": pedido.fecha_entrega.isoformat() if pedido.fecha_entrega else None
                    }
                }
            else:
                # Últimos pedidos
                pedidos = self.db.query(Pedido).filter(
                    Pedido.cliente_id == cliente_id
                ).order_by(Pedido.fecha_pedido.desc()).limit(5).all()
                
                orders = []
                for pedido in pedidos:
                    orders.append({
                        "id": pedido.id,
                        "status": pedido.estado.value,
                        "total": float(pedido.total),
                        "created_at": pedido.fecha_pedido.isoformat()
                    })
                
                return {
                    "success": True,
                    "orders": orders,
                    "total_orders": len(orders)
                }
                
        except Exception as e:
            logger.exception(f"Error obteniendo el estado del pedido: {e}")
            return {"success": False, "error": str(e)}

    @db_transaction
    def update_order(self, phone_number: str, order_id: int, 
                    items: Optional[List[Dict]] = None,
                    delivery_address: Optional[str] = None,
                    payment_method: Optional[str] = None,
                    notes: Optional[str] = None) -> Dict[str, Any]:
        """
        Actualiza un pedido (solo si está en estado PENDIENTE)
        
        🔧 DECORATOR: @db_transaction
        - Maneja automáticamente commit/rollback de transacciones
        - Elimina necesidad de try/except manual para transacciones
        
        Args:
            phone_number: Número de teléfono del cliente
            order_id: ID del pedido a actualizar
            items: Nueva lista de items (opcional)
            delivery_address: Nueva dirección (opcional)
            payment_method: Nuevo método de pago (opcional)
            notes: Nuevas notas (opcional)
            
        Returns:
            Dict con resultado de la actualización
        """
        # Buscar sesión y cliente
        session = self.db.query(UserSession).filter(UserSession.phone_number == phone_number).first()
        if not session or not session.cliente_id:
            return {"success": False, "error": "Cliente no encontrado"}
        
        pedido = self.db.query(Pedido).filter(
            and_(Pedido.id == order_id, Pedido.cliente_id == session.cliente_id)
        ).first()
        
        if not pedido:
            return {"success": False, "error": "Pedido no encontrado"}
        
        if pedido.estado != EstadoPedido.PENDIENTE:
            return {"success": False, "error": "El pedido no se puede modificar en el estado actual"}

        # 🔥 VALIDAR TODO ANTES del procesamiento
        validated_payment_method = None
        if payment_method:
            validated_payment_method = self._normalize_payment_method(payment_method)
            if not validated_payment_method:
                return {"success": False, "error": f"Método de pago inválido: {payment_method}"}

        validated_items = None
        if items:
            validation = self._validate_order_items(items)
            if not validation["valid_items"]:
                return {
                    "success": False, 
                    "error": "No se encontraron items válidos",
                    "details": validation["errors"],
                    "invalid_items": validation["invalid_items"]
                }
            validated_items = validation["valid_items"]
        
        # Actualizar campos básicos
        if delivery_address:
            pedido.direccion_entrega = delivery_address
        if notes:
            pedido.notas = notes
        if validated_payment_method:
            pedido.medio_pago = validated_payment_method
        
        # Actualizar items si se proporcionan
        if validated_items:
            # Eliminar detalles existentes (SQLAlchemy 2.x style)
            self.db.execute(delete(DetallePedido).where(DetallePedido.pedido_id == pedido.id))
            
            # Agregar nuevos detalles
            total = Decimal('0')
            for item in validated_items:
                pave = item["pave"]
                cantidad = item["quantity"]
                precio_unitario = Decimal(str(pave.price))
                subtotal = self._money(precio_unitario * cantidad)
                
                detalle = DetallePedido(
                    pedido_id=pedido.id,
                    pave_id=pave.id,
                    cantidad=cantidad,
                    precio_unitario=precio_unitario,
                    nombre_pave=pave.name,
                    tamano_pave=pave.size.value,
                    subtotal=subtotal
                )
                self.db.add(detalle)
                total += subtotal
            
            pedido.total = self._money(total)
        
        return {
            "success": True,
            "data": {  
                "order_id": pedido.id,
                "total": float(pedido.total),
                "status": pedido.estado.value,
                "updated": True
            }
        }

    @db_transaction
    def cancel_order(self, phone_number: str, order_id: int) -> Dict[str, Any]:
        """
        Cancela un pedido (cambia estado a CANCELADO)
        
        🔧 DECORATOR: @db_transaction
        - Maneja automáticamente commit/rollback de transacciones
        - Elimina necesidad de try/except manual para transacciones
        
        Args:
            phone_number: Número de teléfono del cliente
            order_id: ID del pedido a cancelar
            
        Returns:
            Dict con resultado de la cancelación
        """
        # Buscar sesión y cliente
        session = self.db.query(UserSession).filter(UserSession.phone_number == phone_number).first()
        if not session or not session.cliente_id:
            return {"success": False, "error": "Cliente no encontrado"}

        pedido = self.db.query(Pedido).filter(
            and_(Pedido.id == order_id, Pedido.cliente_id == session.cliente_id)
        ).first()
        
        if not pedido:
            return {"success": False, "error": "Pedido no encontrado"}
        
        if pedido.estado in [EstadoPedido.ENTREGADO, EstadoPedido.CANCELADO]:
            return {"success": False, "error": f"No se puede cancelar el pedido en estado: {pedido.estado.value}"}
        
        pedido.estado = EstadoPedido.CANCELADO
        
        return {
            "success": True,
            "order": {
                "id": pedido.id,
                "status": pedido.estado.value,
                "cancelled": True
            }
        }

    @db_transaction
    def delete_order(self, phone_number: str, order_id: int) -> Dict[str, Any]:
        """
        Elimina un pedido completamente (solo para borradores/admin)
        
        🔧 DECORATOR: @db_transaction
        - Maneja automáticamente commit/rollback de transacciones
        - Elimina necesidad de try/except manual para transacciones
        
        Args:
            phone_number: Número de teléfono del cliente
            order_id: ID del pedido a eliminar
            
        Returns:
            Dict con resultado de la eliminación
        """
        # Buscar sesión y cliente
        session = self.db.query(UserSession).filter(UserSession.phone_number == phone_number).first()
        if not session or not session.cliente_id:
            return {"success": False, "error": "Cliente no encontrado"}
        
        pedido = self.db.query(Pedido).filter(
            and_(Pedido.id == order_id, Pedido.cliente_id == session.cliente_id)
        ).first()
        
        if not pedido:
            return {"success": False, "error": "Pedido no encontrado"}
        
        # Solo permitir eliminar pedidos pendientes
        if pedido.estado != EstadoPedido.PENDIENTE:
            return {"success": False, "error": "Solo se pueden eliminar pedidos pendientes"}
        
        self.db.delete(pedido)
        
        return {
            "success": True,
            "message": f"Pedido {order_id} eliminado con éxito"
        }

    # ==========================================
    # FUNCIONES AUXILIARES PARA SESIONES
    # ==========================================

    @db_transaction
    def update_session_phase(self, phone_number: str, phase: str, draft_order: Optional[Dict] = None) -> bool:
        """
        Actualiza la fase de conversación del usuario
        
        🔧 DECORATOR: @db_transaction
        - Maneja automáticamente commit/rollback de transacciones
        - Elimina necesidad de try/except manual para transacciones
        
        Args:
            phone_number: Número de teléfono
            phase: Nueva fase
            draft_order: Borrador del pedido (opcional)
            
        Returns:
            bool: True si se actualizó correctamente
        """
        session = self.db.query(UserSession).filter(UserSession.phone_number == phone_number).first()
        
        if not session:
            # Crear nueva sesión si no existe
            session = UserSession(
                cliente_id=None,  # Se enlazará después
                phone_number=phone_number,
                phase=phase,
                draft_order_json=draft_order if draft_order is not None else {},  # Valor por defecto
                context_data={}  # Valor por defecto para NOT NULL JSONB
            )
            self.db.add(session)
        else:
            session.phase = phase
            # last_interaction_at se actualiza automáticamente con onupdate
        
        if draft_order is not None:
            session.draft_order_json = draft_order  # JSONB directo, siempre dict válido
        
        return True

# app/services/order_service.py
from __future__ import annotations
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from datetime import datetime
from app.models.cliente import Cliente
from app.models.pedido import Pedido, DetallePedido
from app.models.paves import Pave

# Ejemplo mínimo de dataclass-like dicts esperados de salida
# (No son modelos, solo te sirven de guía del shape)
# MenuItem: id, name, price, category, photo_url
# Order: id, customer_phone, status, total, created_at

class OrderService:
    def __init__(self, db: Session):
        self.db = db

    # ---------- MENÚ ----------
    def list_menu(self, category: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Devuelve una lista de items del menú. Campos clave: id, name, price, category, photo_url (opcional).
        """
        # ⚠️ REEMPLAZA por tus modelos y campos reales
        q = self.db.execute(
            select(MenuItem.id, MenuItem.name, MenuItem.price, MenuItem.category, MenuItem.photo_url)
            .where(MenuItem.is_active == True)
            .order_by(MenuItem.name)
            .limit(limit)
        )
        # rows = q.all()

        # MOCK si aún no tienes modelos listos:
        rows = [
            (1, "Pizza Hawaiana", 35000, "pizza", "https://tu-cdn.com/menu/hawaiana.jpg"),
            (2, "Pizza Pepperoni", 36000, "pizza", "https://tu-cdn.com/menu/pepperoni.jpg"),
            (3, "Limonada", 8000, "bebida", None),
        ]
        if category:
            rows = [r for r in rows if r[3] == category]

        items = []
        for r in rows:
            items.append({
                "id": r[0],
                "name": r[1],
                "price": int(r[2]),
                "category": r[3],
                "photo_url": r[4],
            })
        return items

    # ---------- CREAR PEDIDO ----------
    def create_order(
        self,
        customer_phone: str,
        items: List[Dict[str, int]],
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Crea un pedido sencillo:
        items: [{"product_id": 1, "quantity": 2}, ...]
        Devuelve {"order_id": int, "status": str, "total": int}
        """
        if not items:
            return {"error": "items_empty"}

        # ⚠️ EJEMPLO SIMPLE sin consultar precios reales (reemplaza por tu lógica)
        # Debes: 1) Validar que los product_id existen
        #        2) Obtener precio por ítem
        #        3) Calcular total
        #        4) Insertar Order + OrderItems
        total = 0
        for it in items:
            qty = max(1, int(it.get("quantity", 1)))
            # price = self._get_price_from_db(it["product_id"])
            price = 35000  # placeholder
            total += price * qty

        # Aquí insertarías Order + OrderItems y commit
        # order = Order(customer_phone=customer_phone, status="pending", total=total, notes=notes)
        # self.db.add(order)
        # self.db.flush()
        # for it in items:
        #     self.db.add(OrderItem(order_id=order.id, product_id=it["product_id"], quantity=it["quantity"], price=...))
        # self.db.commit()

        # MOCK: retorna un ID simulado
        order_id = 1234
        return {"order_id": order_id, "status": "pending", "total": total}

    # ---------- ESTADO PEDIDO ----------
    def get_order_status(self, order_id: int) -> Dict[str, Any]:
        """
        Devuelve {"order_id": int, "status": str, "total": int, "eta_minutes": int opcional}
        """
        # ⚠️ Cambia por tu consulta real
        # order = self.db.get(Order, order_id)
        # if not order: return {"error": "not_found"}
        # return {"order_id": order.id, "status": order.status, "total": int(order.total), "eta_minutes": order.eta_minutes}

        # MOCK:
        if order_id == 1234:
            return {"order_id": 1234, "status": "preparing", "total": 70000, "eta_minutes": 20}
        return {"error": "not_found"}

    # ---------- ÚLTIMO PEDIDO POR TELÉFONO ----------
    def get_last_order_by_phone(self, phone: str) -> Dict[str, Any]:
        """
        Devuelve el último pedido del cliente por teléfono, o {"error":"not_found"}.
        """
        # ⚠️ Reemplaza por consulta real (order by created_at desc limit 1)
        # row = self.db.execute(
        #     select(Order.id, Order.status, Order.total, Order.created_at)
        #     .where(Order.customer_phone == phone)
        #     .order_by(Order.created_at.desc())
        #     .limit(1)
        # ).first()
        # if not row: return {"error": "not_found"}
        # return {"order_id": row.id, "status": row.status, "total": int(row.total), "created_at": row.created_at.isoformat()}

        # MOCK:
        return {"order_id": 1234, "status": "preparing", "total": 70000, "created_at": datetime.utcnow().isoformat()}

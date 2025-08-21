from re import sub
from sqlalchemy import create_engine, select
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) #Agregar ruta del proyecto
from database.connection import Base, engine
from app.models.paves import Pave
from app.models.pedido import Pedido, DetallePedido, MedioPago
from database.connection import SessionLocal
from decimal import Decimal
from app.models.cliente import Cliente
from typing import List, Dict


def init_database():
    """Crear todas las tablas en la base de datos"""
    Base.metadata.create_all(bind=engine)
    print("✅ Base de datos inicializada correctamente")

def elpedido(
        client_id: int, medio_pago: MedioPago, items: List[Dict[str, int]],
        direccion: str | None = None,
        notas: str | None = None
):
    db = SessionLocal()

    cliente = db.get(Cliente, client_id) # Obtener cliente
    if not cliente:
        raise ValueError("Cliente no encontrado.")
    print(f"{cliente.nombre} vive en {cliente.direccion} y su numero es {cliente.numero_whatsapp}")
    all_detalles = [] # Lista para almacenar todos los detalles del pedido
    total = Decimal("0.00")
    for it in items:
        pave = db.get(Pave, it["pave_id"]) #Aqui se obtiene el pave
        print(f"El pavé {pave.name} cuesta {pave.price} y tiene {pave.ingredients}")
        total += pave.price * it["cantidad"] # Calcular el subtotal
        detalle = DetallePedido(pave=pave, cantidad=it["cantidad"], precio_unitario=pave.price,
                                nombre_pave=pave.name, tamano_pave=pave.size.value, subtotal=total) # Crear detalle de pedido
        all_detalles.append(detalle) # Agregar detalle a la lista
    db.add_all(all_detalles) # Agregar todos los detalles a la sesión

    pedido = Pedido(cliente=cliente, medio_pago=medio_pago, total=total, direccion_entrega=cliente.direccion, notas=notas, detalles=all_detalles)
    db.add(pedido)
    db.commit()

init_database()
#elpedido(client_id=1, medio_pago=MedioPago.TARJETA, items=[
#    {"pave_id": 2, "cantidad": 1}, {"pave_id": 7, "cantidad": 1}
#])

"""
📦 MODELO DE PEDIDOS - ESTRUCTURA DE ÓRDENES
============================================

Este módulo define la estructura de datos para pedidos de pavé, incluyendo
estados, métodos de pago, detalles de productos y relaciones con clientes.

Autor: Sistema de Modelo de Datos
Fecha: 2025-08-21
Versión: 1.0

🎯 PROPÓSITO:
- Definir estructura de pedidos en base de datos
- Gestionar estados del ciclo de vida del pedido
- Manejar métodos de pago soportados
- Relacionar pedidos con clientes y productos
- Mantener histórico de precios y productos

📊 ESTRUCTURA PRINCIPAL:

🛒 TABLA PEDIDOS:
- ID único del pedido
- Referencia a cliente
- Estado actual (pendiente → entregado)
- Método de pago elegido
- Total calculado con precisión decimal
- Dirección de entrega
- Notas adicionales
- Timestamps de pedido y entrega

🔍 TABLA DETALLE_PEDIDOS:
- Items individuales del pedido
- Cantidad de cada producto
- Precio unitario (snapshot histórico)
- Nombre y tamaño (snapshot para auditoría)
- Subtotal calculado

🏷️ ENUMS DEFINIDOS:

💳 MÉTODOS DE PAGO:
- TARJETA: Pagos con tarjeta
- TRANSFERENCIA_BANCARIA: Transferencias/Nequi/etc
- EFECTIVO: Pago contra entrega

📋 ESTADOS DE PEDIDO:
- PENDIENTE: Recién creado, esperando confirmación
- CONFIRMADO: Aceptado por el negocio
- PREPARANDO: En cocina
- ENVIADO: En camino al cliente
- ENTREGADO: Completado exitosamente
- CANCELADO: Cancelado por cualquier motivo

🔗 RELACIONES:
- Pedido → Cliente (many-to-one)
- Pedido → DetallePedido (one-to-many, cascade delete)
- DetallePedido → Pave (many-to-one, snapshot data)

⚡ OPTIMIZACIONES:
- Índices compuestos para consultas frecuentes
- Lazy loading selectivo según uso
- Constraints de integridad a nivel DB

🛡️ VALIDACIONES:
- Total y precios no negativos
- Cantidades positivas
- Integridad referencial con restricciones
- Timestamps automáticos

💾 SNAPSHOTS HISTÓRICOS:
- Precios al momento de compra
- Nombres y tamaños de productos
- Preserva datos aunque productos cambien

📝 EJEMPLO DE USO:
    pedido = Pedido(
        cliente_id=1,
        estado=EstadoPedido.PENDIENTE,
        medio_pago=MedioPago.EFECTIVO,
        total=Decimal('15000.00'),
        direccion_entrega="Calle 123 #45-67"
    )
"""

from os import name
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text, Numeric
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import CheckConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.connection import Base
from enum import Enum

class MedioPago(Enum):
    TARJETA = "tarjeta"
    TRANSFERENCIA_BANCARIA = "transferencia_bancaria"
    EFECTIVO = "efectivo"

class EstadoPedido(Enum):
    PENDIENTE = "pendiente"
    CONFIRMADO = "confirmado"
    PREPARANDO = "preparando"
    ENVIADO = "enviado"
    ENTREGADO = "entregado"
    CANCELADO = "cancelado"

# Modelo de pedido
class Pedido(Base):
    __tablename__ = "pedidos"
    
    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=False)
    estado = Column(SQLEnum(EstadoPedido), default=EstadoPedido.PENDIENTE, nullable=False)
    medio_pago = Column(SQLEnum(MedioPago), nullable=False)
    total = Column(Numeric(10, 2), nullable=False)
    direccion_entrega = Column(String(200), nullable=False)
    notas = Column(Text, nullable=True)
    fecha_pedido = Column(DateTime(timezone=True), server_default=func.now())
    fecha_entrega = Column(DateTime(timezone=True))
    
    # Relación con cliente
    cliente = relationship("Cliente", lazy="joined")
    
    # Relación con detalles de pedido
    detalles = relationship("DetallePedido", back_populates="pedido", cascade="all, delete-orphan", lazy="selectin")


    __table_args__ = (
        CheckConstraint("total >= 0", name="ck_pedido_total_nonneg"),
        Index("ix_pedidos_estado_fecha", "estado", "fecha_pedido"),
        Index("ix_pedidos_cliente_fecha", "cliente_id", "fecha_pedido"),
    )


    def __repr__(self):
        return f"<Pedido(id={self.id}, cliente_id={self.cliente_id}, total={self.total})>"

# Modelo de detalle de pedido
class DetallePedido(Base):
    __tablename__ = "detalle_pedidos"
    
    id = Column(Integer, primary_key=True, index=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id", ondelete="CASCADE"), nullable=False)
    pave_id = Column(Integer, ForeignKey("paves.id", ondelete="RESTRICT"), nullable=False)
    
    cantidad = Column(Integer, nullable=False, default=1)  # cantidad de pavés
    precio_unitario = Column(Numeric(10, 2), nullable=False)  #Precio al momento de la compra
    nombre_pave = Column(String(100), nullable=False)  # Snapshot nombre del pavé
    tamano_pave = Column(String(20), nullable=False)  # Snapshot del tamaño
    subtotal = Column(Numeric(10, 2), nullable=False) # cantidad × precio_unitario

    # Relaciones
    pedido = relationship("Pedido", back_populates="detalles", lazy="selectin")
    pave = relationship("Pave", lazy="joined")
    
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_detalle_cantidad_positive"),
        CheckConstraint("precio_unitario >= 0 AND subtotal >= 0", name="ck_detalle_precios_nonneg"),
    )

    def __repr__(self):
        return f"<DetallePedido(pedido_id={self.pedido_id}, pave_id={self.pave_id}, cantidad={self.cantidad})>"
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
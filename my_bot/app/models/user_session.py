from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.connection import Base
from enum import Enum

class ConversationPhase(Enum):
    GREETING   = "greeting"
    BROWSING   = "browsing"
    ORDERING   = "ordering"
    CONFIRMING = "confirming"
    DELIVERY   = "delivery"
    PAYMENT    = "payment"
    COMPLETED  = "completed"

class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)

    # Ancla por teléfono (1 sesión por número)
    phone_number = Column(String(20), nullable=False, unique=True)  # unique ya crea índice
    cliente_id   = Column(Integer, ForeignKey("clientes.id", ondelete="CASCADE"), nullable=True)

    phase = Column(String(20), default=ConversationPhase.GREETING.value, nullable=False)
    draft_order_json = Column(JSONB, nullable=False, server_default='{}')
    context_data     = Column(JSONB, nullable=False, server_default='{}')

    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_interaction_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    cliente = relationship("Cliente", lazy="selectin")

    # Asegurar que siempre se guarde un dict válido
    __table_args__ = (
        CheckConstraint("phone_number ~ '^\\+[1-9][0-9]{6,15}$'", name="ck_valid_phone_format"),
        CheckConstraint("phase IN ('greeting','browsing','ordering','confirming','delivery','payment','completed')", name="ck_valid_phase"),
        Index("ix_user_sessions_last_interaction", "last_interaction_at"),
    )

    def __repr__(self):
        return f"<UserSession(phone={self.phone_number}, cliente_id={self.cliente_id}, phase='{self.phase}')>"

from sqlalchemy import Column, Integer, Text, DateTime, UniqueConstraint, BigInteger, func
from database.connection import Base


class InboundMessage(Base):
    __tablename__ = "inbound_messages"
    message_sid = Column(Text, primary_key=True)
    from_number = Column(Text, nullable=False)
    body = Column(Text, nullable=True)
    received_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class RateLimit(Base):
    __tablename__ = "rate_limits"
    id = Column(BigInteger, primary_key=True)
    from_number = Column(Text, nullable=False)
    window_start = Column(DateTime(timezone=True), nullable=False)
    count = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (UniqueConstraint("from_number", "window_start", name="rate_limits_unique"),)
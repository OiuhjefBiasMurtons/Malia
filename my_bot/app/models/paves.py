from re import S
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Numeric
from sqlalchemy import Enum as SQLEnum
from database.connection import Base
from enum import Enum

class TamanoPave(Enum):
    ocho_oz = "8 Onzas"
    dieciseis_oz = "16 Onzas"


# Paves models
class Pave(Base):
    __tablename__ = "paves"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    ingredients = Column(String(1500), nullable=False)
    size = Column(SQLEnum(TamanoPave), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    available = Column(Boolean, default=True)
    emoji = Column(String(10), default="🍰")
    
    def __repr__(self):
        return f"<Pave(name='{self.name}', size='{self.size}', price={self.price})>"
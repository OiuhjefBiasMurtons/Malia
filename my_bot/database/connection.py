from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

# Crear motor de base de datos con pooling optimizado
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,                    # Número de conexiones permanentes en el pool
    max_overflow=20,                 # Conexiones adicionales cuando el pool está lleno
    pool_pre_ping=True,             # Verificar conexiones antes de usar
    pool_recycle=3600,              # Reciclar conexiones cada hora
    echo=False,                     # No mostrar SQL queries (cambiar a True para debug)
    connect_args={
        "connect_timeout": 10,       # Timeout de conexión en segundos
    } if "postgresql" in settings.DATABASE_URL else {
        "timeout": 30,               # Para SQLite
    }
)

# Crear sesión local
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para modelos usando el nuevo estilo de declaración
Base = declarative_base()

# Dependencia para obtener sesión de BD
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 
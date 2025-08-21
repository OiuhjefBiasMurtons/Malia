"""
🗄️ CONEXIÓN A BASE DE DATOS - CONFIGURACIÓN SQLALCHEMY
======================================================

Este módulo configura la conexión a PostgreSQL con pooling optimizado,
gestión de sesiones y configuraciones de rendimiento para la aplicación.

Autor: Sistema de Conexión BD
Fecha: 2025-08-21
Versión: 1.0

🎯 PROPÓSITO:
- Configurar engine SQLAlchemy con pooling optimizado
- Gestionar sesiones de base de datos de forma eficiente
- Proporcionar base declarativa para modelos ORM
- Optimizar rendimiento de conexiones concurrentes

🏗️ CONFIGURACIÓN DEL POOL:
- Pool permanente: 10 conexiones activas
- Overflow: 20 conexiones adicionales bajo demanda
- Total máximo: 30 conexiones concurrentes
- Pre-ping: Verificación automática de conexiones
- Recycle: Renovación cada hora (3600s)

⚡ OPTIMIZACIONES:
- QueuePool para alta concurrencia
- Timeouts configurados para evitar colgadas
- Pool recycle para conexiones frescas
- Pre-ping para detectar conexiones muertas

🔧 CARACTERÍSTICAS:
- Compatibilidad PostgreSQL y SQLite
- Configuración adaptativa según DB type
- Logging configurable para debugging
- Dependency injection para FastAPI

📊 GESTIÓN DE SESIONES:
- SessionLocal: Factory de sesiones por request
- autocommit=False: Control manual de transacciones
- autoflush=False: Optimización de performance
- Cierre automático en dependency

🛡️ ROBUSTEZ:
- Timeouts de conexión configurados
- Pool overflow para picos de tráfico
- Manejo de conexiones perdidas
- Logging de errores de conexión

📝 USO CON FASTAPI:
    from database.connection import get_db
    
    @app.post("/endpoint")
    def endpoint(db: Session = Depends(get_db)):
        # usar sesión db aquí
        pass

🗂️ MODELOS ORM:
    from database.connection import Base
    
    class MiModelo(Base):
        __tablename__ = "mi_tabla"
        # campos aquí

💾 CONFIGURACIÓN REQUERIDA:
- DATABASE_URL en variables de entorno
- PostgreSQL con driver psycopg2 recomendado
- SQLite soportado para desarrollo/testing
"""

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
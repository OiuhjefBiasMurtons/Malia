from sqlalchemy import create_engine
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) #Agregar ruta del proyecto

from database.connection import Base, engine
from app.models.paves import Pave
from app.models.cliente import Cliente



def init_database():
    """Crear todas las tablas en la base de datos"""
    Base.metadata.create_all(bind=engine)
    print("✅ Base de datos inicializada correctamente")

def populate_clientes():
    """Poblar la tabla de clientes con datos de ejemplo"""
    from database.connection import SessionLocal

    db = SessionLocal()
    try:
        first_cliente = db.query(Cliente).first()
        if not first_cliente:
            # Si no hay clientes, crear uno de ejemplo
            new_cliente = Cliente(nombre="Andres Cortes", numero_whatsapp="3137479005",
                                  direccion="Calle 123 #45-67")
            db.add(new_cliente)
            db.commit()
            print("✅ Cliente de ejemplo creado")
        else:
            print("ℹ️ Ya existe un cliente en la base de datos")
    except Exception as e:
        print(f"❌ Error al poblar la tabla de clientes: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    init_database()
    populate_clientes()

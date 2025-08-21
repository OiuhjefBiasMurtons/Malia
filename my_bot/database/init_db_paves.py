from sqlalchemy import create_engine
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) #Agregar ruta del proyecto

from database.connection import Base, engine
from app.models.paves import Pave, TamanoPave



def init_database():
    """Crear todas las tablas en la base de datos"""
    Base.metadata.create_all(bind=engine)
    print("✅ Base de datos inicializada correctamente")

def populate_paves():
    """Poblar la base de datos con 29 sabores de pizza - precios en pesos colombianos"""
    from database.connection import SessionLocal
    
    db = SessionLocal()
    
    # Verificar si ya hay paves
    if db.query(Pave).count() > 0:
        print("⚠️  Ya hay paves en la base de datos")
        db.close()
        return

    paves_data = [
        {
            "name": "Pave de Milo",
            "ingredients": "Milo, Leche Condensada, Galletas",
            "size": TamanoPave.ocho_oz,
            "price": 8000,
            "available": True,
            "emoji": "🍫"
        },
        {
            "name": "Pave de Milo",
            "ingredients": "Milo, Leche Condensada, Galletas",
            "size": TamanoPave.dieciseis_oz,
            "price": 16000,
            "available": True,
            "emoji": "🍫"
        },
        {
            "name": "Maracuya",
            "ingredients": "Maracuya, Leche Condensada, Galletas",
            "size": TamanoPave.ocho_oz,
            "price": 8000,
            "available": True,
            "emoji": "🍑"
        },
        {
            "name": "Maracuya",
            "ingredients": "Maracuya, Leche Condensada, Galletas",
            "size": TamanoPave.dieciseis_oz,
            "price": 16000,
            "available": True,
            "emoji": "🍑"
        },
        {
            "name": "Arequipe",
            "ingredients": "Arequipe, Leche Condensada, Galletas",
            "size": TamanoPave.ocho_oz,
            "price": 8000,
            "available": True,
            "emoji": "🍯"
        },
        {
            "name": "Arequipe",
            "ingredients": "Arequipe, Leche Condensada, Galletas",
            "size": TamanoPave.dieciseis_oz,
            "price": 16000,
            "available": True,
            "emoji": "🍯"
        },
        {
            "name": "Leche Klim",
            "ingredients": "Leche Klim, Leche Condensada, Galletas",
            "size": TamanoPave.ocho_oz,
            "price": 8000,
            "available": True,
            "emoji": "🥛"
        },
        {
            "name": "Leche Klim",
            "ingredients": "Leche Klim, Leche Condensada, Galletas",
            "size": TamanoPave.dieciseis_oz,
            "price": 16000,
            "available": True,
            "emoji": "🥛"
        }
    ]
    for pave_data in paves_data:
        pave = Pave(**pave_data)
        db.add(pave)

    db.commit()
    db.close()
    print("✅ 5 sabores de paves agregados a la base de datos con precios en pesos colombianos")


if __name__ == "__main__":
    init_database()
    populate_paves()

#!/usr/bin/env python3

from database.connection import SessionLocal
from app.models.paves import Pave

def check_products():
    db = SessionLocal()
    try:
        paves = db.query(Pave).filter(Pave.available == True).order_by(Pave.name, Pave.size).all()
        
        print('=== PRODUCTOS DISPONIBLES EN LA BASE DE DATOS ===')
        for pave in paves:
            print(f'ID: {pave.id} | Nombre: {pave.name} | Tamaño: {pave.size.value} | Precio: ${pave.price} | Disponible: {pave.available}')
        
        print(f'\nTotal productos disponibles: {len(paves)}')
        
        # Verificar específicamente Milo
        print('\n=== PRODUCTOS DE MILO ===')
        milo_paves = db.query(Pave).filter(Pave.name.ilike('%milo%')).all()
        for pave in milo_paves:
            print(f'ID: {pave.id} | Nombre: {pave.name} | Tamaño: {pave.size.value} | Precio: ${pave.price} | Disponible: {pave.available}')
    finally:
        db.close()

if __name__ == "__main__":
    check_products()

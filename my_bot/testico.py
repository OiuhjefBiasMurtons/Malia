#!/usr/bin/env python3
"""
TESTICO.PY - Script de Prueba Educativo para Order Service
=====================================================

Este script te ayuda a entender cómo funciona tu aplicativo de pedidos
y te permite probar todas las funciones principales de OrderService.

Funcionalidades que vas a probar:
1. Conexión a la base de datos
2. Obtener el menú de pavés
3. Crear y gestionar usuarios
4. Crear pedidos completos
5. Actualizar pedidos
6. Consultar estados de pedidos
7. Cancelar y eliminar pedidos
8. Gestionar sesiones de usuario

IMPORTANTE: Este script usará tu base de datos REAL (PostgreSQL).
Los datos que crees aquí serán reales y persistentes.
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, List
from decimal import Decimal
import logging
from datetime import datetime

# Configurar el path para importar módulos
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def print_section(title: str):
    """Imprime una sección de manera visual"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def print_subsection(title: str):
    """Imprime una subsección"""
    print(f"\n--- {title} ---")

def print_result(result: Dict[str, Any], description: str = ""):
    """Imprime un resultado de manera formateada"""
    if description:
        print(f"\n✅ {description}")
    print(f"   Resultado: {result.get('message', 'Sin mensaje')}")
    if result.get('success'):
        print("   ✓ Operación exitosa")
    else:
        print("   ❌ Operación falló")
    
    # Mostrar datos adicionales si existen
    if 'data' in result and result['data']:
        print("   📊 Datos:")
        for key, value in result['data'].items():
            print(f"      {key}: {value}")

def print_error(error: str):
    """Imprime un error de manera formateada"""
    print(f"❌ ERROR: {error}")

class TesticoRunner:
    """Clase principal que ejecuta todas las pruebas educativas"""
    
    def __init__(self):
        self.db = None
        self.order_service = None
        self.test_phone = "+573001234567"  # Número de teléfono de prueba
        self.test_user_name = "Juan Pérez Test"
        self.test_address = "Calle 123 #45-67, Bogotá"
        
    def setup_database(self):
        """Configura la conexión a la base de datos"""
        print_section("🔧 CONFIGURACIÓN DE BASE DE DATOS")
        
        try:
            from database.connection import SessionLocal, engine
            from app.services.order_service import OrderService
            
            # Crear sesión de base de datos
            self.db = SessionLocal()
            print("✅ Conexión a PostgreSQL establecida")
            
            # Crear instancia del servicio
            self.order_service = OrderService(self.db)
            print("✅ OrderService inicializado")
            
            # Verificar que las tablas existen
            from sqlalchemy import inspect
            inspector = inspect(engine) #Inspector se usa para obtener metadatos de la base de datos como nombres de tablas
            tables = inspector.get_table_names()
            print(f"📊 Tablas encontradas: {', '.join(tables)}")
            
            return True
            
        except Exception as e:
            print_error(f"No se pudo conectar a la base de datos: {e}")
            print("\n💡 CONSEJOS:")
            print("   1. Verifica que PostgreSQL esté ejecutándose")
            print("   2. Confirma la variable DATABASE_URL en tu .env")
            print("   3. Ejecuta las migraciones: python -m alembic upgrade head")
            return False
    
    def test_menu(self):
        """Prueba obtener el menú"""
        print_section("🍰 PRUEBA 1: OBTENER MENÚ")
        
        try:
            result = self.order_service.get_menu()
            print_result(result, "Obtener menú completo")
            
            if result.get('success'):
                # El OrderService devuelve menu_items directamente
                paves = result.get('menu_items', [])
                total_items = result.get('total_items', 0)
                
                print(f"\n📋 MENÚ COMPLETO:")
                print(f"   Total de pavés: {total_items}")
                
                # Mostrar algunos pavés de ejemplo
                if paves:
                    print(f"\n🍰 EJEMPLOS DE PAVÉS:")
                    for i, pave in enumerate(paves[:3]):  # Mostrar solo los primeros 3. Enumerate me da el indice y el elemento
                        print(f"   {i+1}. {pave['name']} ({pave['size']})")
                        print(f"      💰 Precio: ${pave['price']}")
                        print(f"      🥧 Ingredientes: {pave['ingredients']}")
                        print(f"      {pave['emoji']} Disponible: {'Sí' if pave['available'] else 'No'}")
                else:
                    print("\n⚠️ No se encontraron pavés en el menú")
                        
        except Exception as e:
            print_error(f"Error al obtener menú: {e}")
    
    def test_user_creation(self):
        """Prueba crear y gestionar usuarios"""
        print_section("👤 PRUEBA 2: GESTIÓN DE USUARIOS")
        
        try:
            # Obtener sesión actual (puede no existir)
            print_subsection("Verificar sesión existente")
            session_result = self.order_service.get_user_session(self.test_phone)
            print_result(session_result, "Obtener sesión de usuario")
            
            # Crear o actualizar usuario
            print_subsection("Crear usuario de prueba")
            user_result = self.order_service.create_user(
                phone_number=self.test_phone,
                name=self.test_user_name,
                address=self.test_address
            )
            print_result(user_result, "Crear usuario de prueba")
            
            # Actualizar información del usuario
            print_subsection("Actualizar información del usuario")
            update_result = self.order_service.update_user(
                phone_number=self.test_phone,
                name=f"{self.test_user_name} (Actualizado)",
                address=f"{self.test_address} - Apartamento 501"
            )
            print_result(update_result, "Actualizar datos del usuario")
            
            # Verificar sesión después de crear usuario
            print_subsection("Verificar sesión después de crear usuario")
            final_session = self.order_service.get_user_session(self.test_phone)
            print_result(final_session, "Sesión final del usuario")
            
        except Exception as e:
            print_error(f"Error en gestión de usuarios: {e}")
    
    def test_order_creation(self):
        """Prueba crear pedidos"""
        print_section("📦 PRUEBA 3: CREACIÓN DE PEDIDOS")
        
        # Crear nueva sesión para esta prueba
        from database.connection import SessionLocal
        from app.services.order_service import OrderService
        
        try:
            db_session = SessionLocal()
            order_service = OrderService(db_session)
            
            # Primero obtener el menú para tener IDs válidos
            menu_result = order_service.get_menu()
            if not menu_result.get('success'):
                print_error("No se pudo obtener el menú para crear pedidos")
                print("📊 Contenido de la respuesta del menú:")
                for key, value in menu_result.items():
                    print(f"   {key}: {value}")
                return
                
            # El OrderService devuelve los pavés en 'menu_items'
            paves = menu_result.get('menu_items', [])
                
            if not paves:
                print_error("No hay pavés disponibles en el menú")
                print("📊 Estructura de respuesta del menú:")
                print(f"   Claves disponibles: {list(menu_result.keys())}")
                return
            
            # Preparar items del pedido usando pavés reales
            print_subsection("Preparar items del pedido")
            test_items = []
            
            for i, pave in enumerate(paves[:2]):  # Usar los primeros 2 pavés
                item = {
                    "product_id": pave['id'],  # Usar product_id como espera OrderService
                    "quantity": i + 1,  # 1 del primero, 2 del segundo
                    "notes": f"Sin {['nueces', 'almendras'][i]}" if i < 2 else ""
                }
                test_items.append(item)
                print(f"   📋 Item {i+1}: {pave['name']} ({pave['size']}) x{item['quantity']}")
                print(f"      💰 Precio unitario: ${pave['price']}")
                if item['notes']:
                    print(f"      📝 Notas: {item['notes']}")
            
            # Crear el pedido
            print_subsection("Crear pedido completo")
            order_result = order_service.create_order(
                phone_number=self.test_phone,
                items=test_items,
                delivery_address=self.test_address,
                payment_method="efectivo",
                notes="Entregar en el apartamento 501, tocar el timbre"
            )
            print_result(order_result, "Crear pedido completo")
            
            # Guardar ID del pedido para pruebas posteriores
            if order_result.get('success') and order_result.get('data'):
                self.test_order_id = order_result['data'].get('order_id')
                print(f"💾 Pedido creado con ID: {self.test_order_id}")
            
        except Exception as e:
            print_error(f"Error al crear pedido: {e}")
        finally:
            if 'db_session' in locals():
                db_session.close()
    
    def test_order_status(self):
        """Prueba consultar estado de pedidos"""
        print_section("📊 PRUEBA 4: CONSULTA DE PEDIDOS")
        
        try:
            # Consultar último pedido del usuario
            print_subsection("Consultar último pedido")
            status_result = self.order_service.get_order_status(self.test_phone)
            print_result(status_result, "Consultar último pedido")
            
            # Si tenemos un pedido específico, consultarlo
            if hasattr(self, 'test_order_id') and self.test_order_id:
                print_subsection(f"Consultar pedido específico ID: {self.test_order_id}")
                specific_result = self.order_service.get_order_status(
                    self.test_phone, 
                    self.test_order_id
                )
                print_result(specific_result, f"Consultar pedido #{self.test_order_id}")
                
        except Exception as e:
            print_error(f"Error al consultar pedidos: {e}")
    
    def test_order_update(self):
        """Prueba actualizar pedidos"""
        print_section("✏️ PRUEBA 5: ACTUALIZACIÓN DE PEDIDOS")
        
        if not hasattr(self, 'test_order_id') or not self.test_order_id:
            print("⚠️ No hay pedido para actualizar. Saltando esta prueba.")
            return
            
        try:
            # Actualizar dirección de entrega
            print_subsection("Actualizar dirección de entrega")
            update_result = self.order_service.update_order(
                phone_number=self.test_phone,
                order_id=self.test_order_id,
                delivery_address="Nueva dirección: Calle 456 #78-90, Medellín",
                notes="Nueva instrucción: Llamar al llegar"
            )
            print_result(update_result, "Actualizar dirección y notas")
            
            # Cambiar método de pago
            print_subsection("Cambiar método de pago")
            payment_result = self.order_service.update_order(
                phone_number=self.test_phone,
                order_id=self.test_order_id,
                payment_method="tarjeta"
            )
            print_result(payment_result, "Cambiar método de pago a tarjeta")
            
        except Exception as e:
            print_error(f"Error al actualizar pedido: {e}")
    
    def test_order_cancellation(self):
        """Prueba cancelar pedidos"""
        print_section("❌ PRUEBA 6: CANCELACIÓN DE PEDIDOS")
        
        if not hasattr(self, 'test_order_id') or not self.test_order_id:
            print("⚠️ No hay pedido para cancelar. Saltando esta prueba.")
            return
            
        try:
            # Consultar estado antes de cancelar
            print_subsection("Estado antes de cancelar")
            before_result = self.order_service.get_order_status(
                self.test_phone, 
                self.test_order_id
            )
            print_result(before_result, "Estado antes de cancelación")
            
            # Cancelar el pedido
            print_subsection("Cancelar pedido")
            cancel_result = self.order_service.cancel_order(
                self.test_phone,
                self.test_order_id
            )
            print_result(cancel_result, "Cancelar pedido")
            
            # Verificar estado después de cancelar
            print_subsection("Estado después de cancelar")
            after_result = self.order_service.get_order_status(
                self.test_phone, 
                self.test_order_id
            )
            print_result(after_result, "Estado después de cancelación")
            
        except Exception as e:
            print_error(f"Error al cancelar pedido: {e}")
    
    def test_session_management(self):
        """Prueba gestión de sesiones"""
        print_section("🔄 PRUEBA 7: GESTIÓN DE SESIONES")
        
        try:
            # Actualizar fase de conversación
            print_subsection("Actualizar fase de conversación")
            phase_result = self.order_service.update_session_phase(
                self.test_phone,
                "ordering",  # Usar fase válida en minúsculas
                {"temp_items": [{"pave_id": 1, "quantity": 1}]}
            )
            print(f"✅ Fase actualizada: {phase_result}")
            
            # Verificar sesión actualizada
            print_subsection("Verificar sesión actualizada")
            session_result = self.order_service.get_user_session(self.test_phone)
            print_result(session_result, "Sesión con nueva fase")
            
            # Volver a fase inicial
            print_subsection("Resetear a fase inicial")
            reset_result = self.order_service.update_session_phase(
                self.test_phone,
                "greeting"  # Usar fase válida en minúsculas
            )
            print(f"✅ Fase reseteada: {reset_result}")
            
        except Exception as e:
            print_error(f"Error en gestión de sesiones: {e}")
    
    def test_edge_cases(self):
        """Prueba casos límite y errores"""
        print_section("🧪 PRUEBA 8: CASOS LÍMITE")
        
        # Crear nueva sesión para esta prueba
        from database.connection import SessionLocal
        from app.services.order_service import OrderService
        
        try:
            db_session = SessionLocal()
            order_service = OrderService(db_session)
            
            # Intentar crear pedido sin items
            print_subsection("Pedido sin items (debe fallar)")
            empty_order = order_service.create_order(
                phone_number=self.test_phone,
                items=[],  # Lista vacía
                delivery_address=self.test_address,
                payment_method="efectivo"
            )
            print_result(empty_order, "Pedido sin items")
            
            # Intentar actualizar pedido inexistente
            print_subsection("Actualizar pedido inexistente (debe fallar)")
            fake_update = order_service.update_order(
                phone_number=self.test_phone,
                order_id=99999,  # ID que no existe
                delivery_address="Nueva dirección"
            )
            print_result(fake_update, "Actualizar pedido inexistente")
            
            # Intentar crear orden con método de pago inválido
            print_subsection("Método de pago inválido")
            menu_result = order_service.get_menu()
            if menu_result.get('success') and menu_result.get('menu_items'):
                paves = menu_result['menu_items']
                if paves:
                    invalid_payment = order_service.create_order(
                        phone_number=self.test_phone,
                        items=[{"product_id": paves[0]['id'], "quantity": 1, "notes": ""}],
                        delivery_address=self.test_address,
                        payment_method="bitcoins"  # Método inválido
                    )
                    print_result(invalid_payment, "Método de pago inválido")
            
        except Exception as e:
            print_error(f"Error en casos límite: {e}")
        finally:
            if 'db_session' in locals():
                db_session.close()
    
    def cleanup(self):
        """Limpia recursos después de las pruebas"""
        print_section("🧹 LIMPIEZA")
        
        try:
            if hasattr(self, 'test_order_id') and self.test_order_id:
                print_subsection("Eliminar pedido de prueba")
                delete_result = self.order_service.delete_order(
                    self.test_phone,
                    self.test_order_id
                )
                print_result(delete_result, "Eliminar pedido de prueba")
            
            if self.db:
                self.db.close()
                print("✅ Conexión a base de datos cerrada")
                
        except Exception as e:
            print_error(f"Error en limpieza: {e}")
    
    def run_all_tests(self):
        """Ejecuta todas las pruebas en secuencia"""
        print("🚀 INICIANDO TESTICO - SCRIPT DE PRUEBA EDUCATIVO")
        print("=" * 60)
        print("Este script te ayudará a entender cómo funciona tu aplicativo")
        print("de pedidos de pavés mediante pruebas reales.")
        print("=" * 60)
        
        # Setup
        if not self.setup_database():
            print("\n❌ No se pudo configurar la base de datos. Abortando.")
            return
        
        try:
            # Ejecutar todas las pruebas
            self.test_menu()
            self.test_user_creation()
            self.test_order_creation()
            self.test_order_status()
            self.test_order_update()
            self.test_order_cancellation()
            self.test_session_management()
            self.test_edge_cases()
            
        finally:
            # Limpiar siempre
            self.cleanup()
        
        print_section("🎉 PRUEBAS COMPLETADAS")
        print("¡Has visto cómo funciona tu aplicativo de pedidos!")
        print("\n📚 LO QUE APRENDISTE:")
        print("   ✓ Cómo se conecta a PostgreSQL")
        print("   ✓ Cómo funciona el menú de pavés")
        print("   ✓ Gestión completa de usuarios y sesiones")
        print("   ✓ Ciclo completo de pedidos (crear, consultar, actualizar, cancelar)")
        print("   ✓ Manejo de errores y validaciones")
        print("   ✓ Persistencia de datos en tiempo real")
        
        print("\n💡 PRÓXIMOS PASOS:")
        print("   • Revisa el código de OrderService para entender la lógica")
        print("   • Explora los modelos en app/models/ para ver la estructura de datos")
        print("   • Prueba la API REST con las rutas de app/routers/")
        print("   • Conecta con WhatsApp usando las configuraciones de Twilio")

def main():
    """Función principal"""
    testico = TesticoRunner()
    testico.run_all_tests()

if __name__ == "__main__":
    main()

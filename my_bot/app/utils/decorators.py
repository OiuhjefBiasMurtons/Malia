"""
🔧 DECORADOR DE TRANSACCIONES PARA ORDER SERVICE
================================================

Este módulo proporciona decoradores simples para manejar transacciones
de manera consistente y reducir código duplicado.

Autor: Sistema de mejoras OrderService
Fecha: 2025-08-20
Versión: 1.0

ANTES (código repetitivo):
    def mi_metodo(self, ...):
        try:
            # lógica de negocio
            self.db.commit()
            return resultado
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error: {e}")
            return {"success": False, "error": str(e)}

DESPUÉS (con decorador):
    @db_transaction
    def mi_metodo(self, ...):
        # solo lógica de negocio
        return resultado  # commit automático
"""

import logging
from functools import wraps
from typing import Callable, Any, Dict

logger = logging.getLogger(__name__)

def db_transaction(func: Callable) -> Callable:
    """
    🎯 Decorador principal para manejo automático de transacciones
    
    ✅ QUÉ HACE:
    - Ejecuta la función original
    - Hace commit automáticamente si no hay errores
    - Hace rollback automáticamente si hay errores
    - Convierte excepciones en respuestas JSON estándar
    
    ✅ CUÁNDO USAR:
    - Métodos que modifican la base de datos
    - Operaciones que necesitan consistencia transaccional
    - Cuando quieres respuestas de error estandarizadas
    
    ⚠️ CUÁNDO NO USAR:
    - Métodos de solo lectura (get_*, consultas)
    - Operaciones que ya manejan sus transacciones manualmente
    
    📝 EJEMPLO:
        @db_transaction
        def create_order(self, phone_number, items, ...):
            # validaciones...
            pedido = Pedido(...)
            self.db.add(pedido)
            # NO necesitas commit/rollback manual
            return {"success": True, "data": {...}}
    
    🔄 FLUJO:
        1. Ejecuta función original
        2. Si NO hay error → commit automático
        3. Si hay error → rollback automático + respuesta de error
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs) -> Dict[str, Any]:
        try:
            # 🚀 Ejecutar la función original
            result = func(self, *args, **kwargs)
            
            # ✅ Si llegamos aquí, no hubo errores
            self.db.commit()
            logger.debug(f"✅ Transacción exitosa en {func.__name__}")
            
            return result
            
        except Exception as e:
            # ❌ Hubo un error, hacer rollback
            self.db.rollback()
            error_msg = str(e)
            
            # 📊 Log del error con contexto
            logger.error(f"❌ Error en {func.__name__}: {error_msg}")
            logger.debug(f"   Args: {args}")
            logger.debug(f"   Kwargs: {kwargs}")
            
            # 🔄 Respuesta de error estandarizada
            return {
                "success": False,
                "error": error_msg,
                "method": func.__name__,
                "details": "Error durante operación de base de datos"
            }
    
    # 📋 Preservar metadatos de la función original
    wrapper.__doc__ = func.__doc__
    wrapper.__name__ = func.__name__
    
    return wrapper


def read_only(func: Callable) -> Callable:
    """
    📖 Decorador para operaciones de solo lectura
    
    ✅ QUÉ HACE:
    - NO hace commit (no modifica datos)
    - SÍ hace rollback si hay error (limpia transacción)
    - Proporciona manejo de errores consistente
    
    ✅ CUÁNDO USAR:
    - Métodos get_*, find_*, search_*
    - Consultas que no modifican datos
    - Operaciones de lectura complejas
    
    📝 EJEMPLO:
        @read_only
        def get_order_status(self, phone_number, order_id):
            # consultas...
            return {"success": True, "data": order_info}
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs) -> Dict[str, Any]:
        try:
            # 🔍 Ejecutar consulta
            result = func(self, *args, **kwargs)
            logger.debug(f"📖 Consulta exitosa en {func.__name__}")
            
            return result
            
        except Exception as e:
            # 🧹 Limpiar transacción en caso de error
            self.db.rollback()
            error_msg = str(e)
            
            logger.error(f"❌ Error en consulta {func.__name__}: {error_msg}")
            
            return {
                "success": False,
                "error": error_msg,
                "method": func.__name__,
                "details": "Error durante consulta de base de datos"
            }
    
    return wrapper


# 🏷️ Alias más cortos para uso frecuente
transaction = db_transaction  # Alias corto
query = read_only            # Alias descriptivo

# 📚 Documentación de uso rápido
"""
🚀 GUÍA RÁPIDA DE USO:

1. IMPORTAR:
   from app.utils.decorators import db_transaction, read_only

2. DECORAR MÉTODOS DE ESCRITURA:
   @db_transaction
   def create_order(self, ...): ...
   
   @db_transaction  
   def update_order(self, ...): ...
   
   @db_transaction
   def delete_order(self, ...): ...

3. DECORAR MÉTODOS DE LECTURA:
   @read_only
   def get_menu(self): ...
   
   @read_only
   def get_order_status(self, ...): ...

4. ¡LISTO! 
   - Sin try/except manual
   - Sin commit/rollback manual  
   - Manejo de errores automático
   - Logging consistente
"""

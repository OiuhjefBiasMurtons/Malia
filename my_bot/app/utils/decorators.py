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
import re
from functools import wraps
from typing import Callable, Any, Dict

logger = logging.getLogger(__name__)

def _mask_sensitive_data(data: Any) -> str:
    """
    🔒 Enmascara datos sensibles en logs para proteger PII
    
    Args:
        data: Datos a enmascarar (args, kwargs, etc.)
        
    Returns:
        String seguro para logging sin datos sensibles
    """
    data_str = str(data)
    
    # Enmascarar números de teléfono (varios formatos)
    phone_patterns = [
        r'\b(\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4})\b',  # US/Internacional
        r'\b(\+?[0-9]{1,4}[-.\s]?[0-9]{6,14})\b',  # Internacional general
        r"'phone_number':\s*'([^']+)'",  # En kwargs como string
        r'"phone_number":\s*"([^"]+)"',  # En kwargs como JSON
    ]
    
    for pattern in phone_patterns:
        data_str = re.sub(pattern, lambda m: m.group(0).replace(m.group(1), "***MASKED***"), data_str)
    
    # Enmascarar otros campos sensibles comunes
    sensitive_fields = ['password', 'token', 'api_key', 'secret']
    for field in sensitive_fields:
        pattern = rf"('{field}'|'{field}'):\s*'([^']+)'"
        data_str = re.sub(pattern, rf"\1: '***MASKED***'", data_str, flags=re.IGNORECASE)
    
    return data_str

def db_transaction(func: Callable) -> Callable:
    """
    🎯 Decorador principal para manejo automático de transacciones
    
    ✅ QUÉ HACE:
    - Ejecuta la función original
    - Hace commit SOLO si el resultado indica éxito (success=True)
    - Hace rollback automáticamente si hay errores o si success=False
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
            if not valid:
                return {"success": False, "error": "Invalid data"}  # NO hace commit
            pedido = Pedido(...)
            self.db.add(pedido)
            return {"success": True, "data": {...}}  # SÍ hace commit
    
    🔄 FLUJO:
        1. Ejecuta función original
        2. Si hay error → rollback automático + respuesta de error
        3. Si NO hay error y success=True → commit automático
        4. Si NO hay error y success=False → rollback (validación falló)
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs) -> Dict[str, Any]:
        try:
            # 🚀 Ejecutar la función original
            result = func(self, *args, **kwargs)
            
            # 🔍 Verificar si el resultado indica éxito
            if isinstance(result, dict) and result.get("success") is False:
                # ❌ Validación falló - hacer rollback para evitar commits accidentales
                self.db.rollback()
                logger.debug(f"🔄 Rollback por validación fallida en {func.__name__}: {result.get('error', 'Sin detalle')}")
                return result
            
            # ✅ Si llegamos aquí, operación exitosa - hacer commit
            self.db.commit()
            logger.debug(f"✅ Transacción exitosa en {func.__name__}")
            
            return result
            
        except Exception as e:
            # ❌ Hubo un error, hacer rollback
            self.db.rollback()
            error_msg = str(e)
            
            # 📊 Log del error con contexto (enmascarando datos sensibles)
            logger.error(f"❌ Error en {func.__name__}: {error_msg}")
            logger.debug(f"   Args: {_mask_sensitive_data(args)}")
            logger.debug(f"   Kwargs: {_mask_sensitive_data(kwargs)}")
            
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
            
            # 📊 Log del error (enmascarando datos sensibles)
            logger.error(f"❌ Error en consulta {func.__name__}: {error_msg}")
            logger.debug(f"   Args: {_mask_sensitive_data(args)}")
            logger.debug(f"   Kwargs: {_mask_sensitive_data(kwargs)}")
            
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
   - Commit solo cuando success=True
   - Datos sensibles enmascarados en logs

🔒 MEJORAS DE SEGURIDAD (v1.1):
   ✅ Commit inteligente: Solo cuando success=True
   ✅ Protección PII: Números de teléfono enmascarados en logs
   ✅ Consistencia: @read_only aplicado a get_order_status
"""

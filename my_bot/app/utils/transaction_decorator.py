"""
Decorador para manejo automático de transacciones
Simplifica el código evitando repetir try/commit/rollback
"""
import logging
from functools import wraps
from typing import Callable, Any

logger = logging.getLogger(__name__)

def transactional(auto_commit: bool = True):
    """
    Decorador para manejo automático de transacciones en métodos de servicio
    
    Args:
        auto_commit: Si True, hace commit automáticamente. Si False, solo rollback en error.
    
    Usage:
        @transactional()
        def create_order(self, ...):
            # código sin try/except
            # commit automático al final
            return {"success": True, ...}
            
        @transactional(auto_commit=False)
        def complex_operation(self, ...):
            # código sin try/except
            # commit manual con self.db.commit()
            return result
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs) -> Any:
            try:
                # Ejecutar la función original
                result = func(self, *args, **kwargs)
                
                # Auto-commit si está habilitado
                if auto_commit:
                    self.db.commit()
                    
                return result
                
            except Exception as e:
                # Rollback automático en caso de error
                self.db.rollback()
                logger.error(f"Error en {func.__name__}: {e}")
                
                # Re-lanzar la excepción para que el método pueda manejarla
                raise e
                
        return wrapper
    return decorator

# Versión simplificada para casos comunes
def auto_commit(func: Callable) -> Callable:
    """
    Decorador simplificado que siempre hace auto-commit
    
    Usage:
        @auto_commit
        def simple_operation(self, ...):
            # código sin try/except
            return result
    """
    return transactional(auto_commit=True)(func)

def safe_transaction(func: Callable) -> Callable:
    """
    Decorador que solo hace rollback en error, commit manual
    
    Usage:
        @safe_transaction
        def complex_operation(self, ...):
            # código...
            self.db.commit()  # commit manual
            return result
    """
    return transactional(auto_commit=False)(func)

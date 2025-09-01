"""
🔧 NORMALIZADOR DE TEXTO MEJORADO
================================

Utilidad para normalización robusta de texto con:
- Accent folding (elimina acentos)
- Sinónimos configurables por regex
- Future-proof para nuevos productos
"""

import unicodedata
import re
from typing import Dict

def _fold_accents(s: str) -> str:
    """
    Elimina acentos usando Unicode normalization.
    'maracuyá' → 'maracuya'
    """
    return ''.join(
        c for c in unicodedata.normalize('NFD', s.lower()) 
        if unicodedata.category(c) != 'Mn'
    )

# 🔧 SINÓNIMOS CONFIGURABLES: Usar regex con límites de palabra
PRODUCT_SYNONYMS = {
    r'\bchoco\b': 'chocolate',
    r'\bchocolate\b': 'milo',  # Solo si no hay producto "chocolate" real
    r'\bareqipe\b': 'arequipe',
    r'\bmaracuya\b': 'maracuyá',  # Sin acento → con acento
}

def normalize_search_query(query: str) -> str:
    """
    Normaliza query de búsqueda de forma robusta.
    
    Args:
        query: Query original del usuario
        
    Returns:
        Query normalizada
    """
    # 1. Fold accents
    normalized = _fold_accents(query)
    
    # 2. Aplicar sinónimos con regex de límites de palabra
    for pattern, replacement in PRODUCT_SYNONYMS.items():
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    
    return normalized

def is_safe_to_map_chocolate_to_milo(db_products) -> bool:
    """
    Verifica si es seguro mapear 'chocolate' → 'milo'.
    
    Returns False si existe un producto con 'chocolate' en el nombre.
    """
    try:
        for product in db_products:
            if 'chocolate' in product.name.lower():
                return False
        return True
    except Exception:
        return False  # Por seguridad, no mapear si hay error

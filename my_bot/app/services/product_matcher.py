"""
🔍 PRODUCT MATCHER - BÚSQUEDA INTELIGENTE DE PRODUCTOS
==================================================

Este módulo maneja la búsqueda y matching inteligente de productos
basado en texto de usuarios, permitiendo variaciones, errores de tipeo
y sinónimos.

Autor: Sistema de Matching de Productos
Fecha: 2025-08-25
Versión: 1.0
"""

from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher
import re
from app.models.paves import Pave

class ProductMatcher:
    """
    Matcher inteligente que puede encontrar productos incluso con:
    - Errores de tipeo
    - Variaciones de nombres
    - Sinónimos
    - Nombres parciales
    """
    
    # Sinónimos y variaciones conocidas (MEJORADO)
    SYNONYMS = {
        "milo": ["chocolate", "cacao", "choco"],
        "arequipe": ["dulce de leche", "manjar", "cajeta", "areqipe"],  # Incluye error común
        "maracuya": ["maracuyá", "passion fruit", "parcha", "maracuya"],  # Sin y con acento
        "maracuyá": ["maracuya", "passion fruit", "parcha"],  # Inverso también
        "klim": ["leche", "milk", "leche en polvo"]
    }
    
    # Palabras que se pueden ignorar en la búsqueda
    IGNORE_WORDS = {"de", "del", "la", "el", "un", "una", "pave", "pavé", "onza", "onzas", "oz"}
    
    def __init__(self, products: List[Pave]):
        """
        Inicializa el matcher con la lista de productos disponibles
        
        Args:
            products: Lista de productos Pave de la base de datos
        """
        self.products = products
        self._build_search_index()
    
    def _build_search_index(self):
        """Construye un índice de búsqueda optimizado"""
        self.search_index = []
        
        for product in self.products:
            # Crear variaciones del nombre para búsqueda
            base_name = product.name.lower()
            search_terms = [base_name]
            
            # Añadir variaciones sin "pave de"
            clean_name = re.sub(r'\b(pave|pavé)\s+(de\s+)?', '', base_name).strip()
            if clean_name != base_name:
                search_terms.append(clean_name)
            
            # Añadir sinónimos
            for word in clean_name.split():
                if word in self.SYNONYMS:
                    for synonym in self.SYNONYMS[word]:
                        search_terms.append(synonym)
            
            self.search_index.append({
                'product': product,
                'search_terms': search_terms,
                'size_8oz': product.size.value == "8 Onzas",
                'size_16oz': product.size.value == "16 Onzas"
            })
    
    def _normalize_user_input(self, user_text: str) -> List[str]:
        """
        Normaliza el input del usuario para búsqueda (MEJORADO con accent folding)
        
        Args:
            user_text: Texto del usuario
            
        Returns:
            Lista de términos de búsqueda normalizados
        """
        # Usar nueva utilidad de normalización
        try:
            from app.utils.text_normalizer import normalize_search_query
            normalized_text = normalize_search_query(user_text)
        except ImportError:
            # Fallback si no está disponible la utilidad
            normalized_text = user_text.lower().replace("maracuya", "maracuyá")
        
        # Remover puntuación común
        text = re.sub(r'[,.!?¿¡]', ' ', normalized_text)
        
        # Extraer palabras, ignorando las que no aportan
        words = [w for w in text.split() if w not in self.IGNORE_WORDS and len(w) > 1]
        
        return words
    
    def _calculate_similarity(self, user_terms: List[str], search_terms: List[str]) -> float:
        """
        Calcula la similitud entre términos del usuario y términos de producto
        
        Args:
            user_terms: Términos normalizados del usuario
            search_terms: Términos de búsqueda del producto
            
        Returns:
            Score de similitud (0.0 - 1.0)
        """
        max_score = 0.0
        
        for user_term in user_terms:
            for search_term in search_terms:
                # Coincidencia exacta
                if user_term == search_term:
                    max_score = max(max_score, 1.0)
                # Contiene el término
                elif user_term in search_term or search_term in user_term:
                    max_score = max(max_score, 0.8)
                # Similitud por caracteres (errores de tipeo)
                else:
                    similarity = SequenceMatcher(None, user_term, search_term).ratio()
                    if similarity > 0.7:  # Umbral para errores de tipeo
                        max_score = max(max_score, similarity * 0.9)
        
        return max_score
    
    def find_products(self, user_input: str, min_score: float = 0.6) -> List[Dict]:
        """
        Encuentra productos que coincidan con el input del usuario
        
        Args:
            user_input: Texto del usuario (ej: "milo de 8 onzas", "areqipe 16oz")
            min_score: Score mínimo para considerar una coincidencia
            
        Returns:
            Lista de coincidencias ordenadas por relevancia
        """
        user_terms = self._normalize_user_input(user_input)
        if not user_terms:
            return []
        
        matches = []
        
        # Detectar tamaño específico en el input
        size_preference = None
        if any(term in user_input.lower() for term in ["8", "ocho"]):
            size_preference = "8oz"
        elif any(term in user_input.lower() for term in ["16", "dieciseis", "dieciséis"]):
            size_preference = "16oz"
        
        for item in self.search_index:
            score = self._calculate_similarity(user_terms, item['search_terms'])
            
            if score >= min_score:
                # Bonus por coincidencia de tamaño
                if size_preference:
                    if (size_preference == "8oz" and item['size_8oz']) or \
                       (size_preference == "16oz" and item['size_16oz']):
                        score += 0.1
                
                matches.append({
                    'product': item['product'],
                    'score': score,
                    'matched_terms': user_terms
                })
        
        # Ordenar por score (mejor coincidencia primero)
        matches.sort(key=lambda x: x['score'], reverse=True)
        
        return matches
    
    def find_best_match(self, user_input: str) -> Optional[Pave]:
        """
        Encuentra la mejor coincidencia individual
        
        Args:
            user_input: Texto del usuario
            
        Returns:
            Producto con mejor coincidencia o None si no hay coincidencias buenas
        """
        matches = self.find_products(user_input, min_score=0.7)
        return matches[0]['product'] if matches else None


def create_smart_search_tool(products: List[Pave]) -> Dict:
    """
    Crea una herramienta de búsqueda inteligente para function calling
    
    Args:
        products: Lista de productos disponibles
        
    Returns:
        Definición de herramienta para OpenAI
    """
    return {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Busca productos de forma inteligente basado en texto del usuario. Maneja errores de tipeo, sinónimos y variaciones de nombres.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_query": {
                        "type": "string",
                        "description": "Texto del usuario describiendo el producto que busca (ej: 'milo 8 onzas', 'areqipe grande', 'chocolate')",
                        "minLength": 1,
                        "maxLength": 100
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Número máximo de resultados a devolver",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 5
                    }
                },
                "required": ["user_query"],
                "additionalProperties": False
            }
        }
    }

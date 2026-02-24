"""
Mapeo de Departamentos a Códigos SAT

Mapea los 23 departamentos a códigos SAT producto/servicio y unidades.
"""

from typing import Tuple, Optional, List
import logging

logger = logging.getLogger(__name__)

# Mapeo directo de departamentos a códigos SAT base
DEPARTMENT_TO_SAT_BASE = {
    # BELLEZA
    "Maquillaje": "53131600",      # Productos de maquillaje
    "Labiales": "53131607",        # Labiales
    "Pestañas": "53131606",        # Rímel / Máscara de pestañas
    "Delineadores": "53131605",    # Delineador de ojos
    "Cosméticos": "53131600",      # Productos de maquillaje (genérico)
    "Skin Care": "53131500",       # Productos para el cuidado de la piel
    "Uñas": "53131900",            # Productos para uñas
    "Peinados": "53131800",        # Productos para el cabello
    "Perfumería": "53131700",      # Perfumes y fragancias
    
    # ACCESORIOS
    "Bisutería": "53131500",       # Accesorios de belleza
    "Lentes": "53131500",          # Accesorios de belleza
    "Bolsos y Carteras": "53131500", # Accesorios de belleza
    "Llaveros": "53131500",        # Accesorios de belleza
    "Espejos": "53131500",         # Accesorios de belleza
    "Accesorios": "53131500",      # Accesorios de belleza (genérico)
    
    # OTROS
    "Papelería": "44111500",       # Bolígrafos (genérico papelería)
    "Juguetería": "42211500",      # Juguetes
    "Electrónica": "43211500",     # Computadoras (genérico electrónica)
    "Hogar": "47131800",           # Productos de limpieza (genérico hogar)
    "Fiestas": "42211500",         # Decoraciones
    "Regalos": "42211500",         # Artículos para regalo
    "Novedad": "01010101",         # No existe en el catálogo
    "Sin Clasificar": "01010101",  # No existe en el catálogo
}

# Mapeo de palabras clave específicas a códigos SAT más precisos
KEYWORD_TO_SAT_SPECIFIC = {
    # Maquillaje específico
    "BASE": "53131601",           # Base de maquillaje
    "BASE LIQUIDA": "53131601",
    "BASE CREMA": "53131601",
    "CORRECTOR": "53131602",      # Corrector
    "POLVO": "53131603",          # Polvo compacto/suelto
    "SOMBRA": "53131604",         # Sombras de ojos
    "PALETA": "53131604",         # Paleta de sombras
    "RUBOR": "53131608",          # Rubor/Blush
    "BRONZER": "53131608",
    "ILUMINADOR": "53131609",     # Iluminador/Highlighter
    
    # Skin Care específico
    "CREMA": "53131501",          # Crema facial
    "SERUM": "53131502",          # Sérum
    "TONER": "53131503",          # Tónico
    "MASCARILLA": "53131504",     # Mascarilla facial
    "PROTECTOR SOLAR": "53131505", # Protector solar
}

# Mapeo de departamentos a unidades SAT
DEPARTMENT_TO_UNIT = {
    # La mayoría son "H87" (Pieza)
    "Maquillaje": "H87",
    "Labiales": "H87",
    "Pestañas": "H87",
    "Delineadores": "H87",
    "Cosméticos": "H87",
    "Skin Care": "H87",
    "Uñas": "H87",
    "Peinados": "H87",
    "Perfumería": "H87",
    "Bisutería": "H87",
    "Lentes": "H87",
    "Bolsos y Carteras": "H87",
    "Llaveros": "H87",
    "Espejos": "H87",
    "Accesorios": "H87",
    "Papelería": "H87",
    "Juguetería": "H87",
    "Electrónica": "H87",
    "Hogar": "H87",
    "Fiestas": "H87",
    "Regalos": "H87",
    "Novedad": "H87",
    "Sin Clasificar": "H87",
}

class SATDepartmentMapper:
    """
    Mapea departamentos a códigos SAT y busca códigos específicos.
    """
    
    def __init__(self, sat_catalog_manager=None):
        """
        Args:
            sat_catalog_manager: Instancia de SATCatalogManager (opcional)
        """
        self.sat_catalog_manager = sat_catalog_manager
    
    def get_sat_code(self, department: str, product_name: str = "") -> Tuple[str, str]:
        """
        Obtiene código SAT producto/servicio y unidad.
        
        Args:
            department: Departamento del producto
            product_name: Nombre del producto (para búsqueda específica)
            
        Returns:
            (sat_clave_prod_serv, sat_clave_unidad)
        """
        # Obtener código base del departamento
        base_code = DEPARTMENT_TO_SAT_BASE.get(department, "01010101")
        
        # Intentar búsqueda específica si hay nombre de producto
        if product_name:
            specific_code = self.search_specific_code(department, product_name)
            if specific_code:
                sat_code = specific_code
            else:
                sat_code = base_code
        else:
            sat_code = base_code
        
        # Obtener unidad
        sat_unit = DEPARTMENT_TO_UNIT.get(department, "H87")
        
        return (sat_code, sat_unit)
    
    def search_specific_code(self, department: str, product_name: str) -> Optional[str]:
        """
        Busca código SAT más específico basado en palabras clave.
        
        Args:
            department: Departamento del producto
            product_name: Nombre del producto
            
        Returns:
            Código SAT específico o None si no se encuentra
        """
        product_upper = product_name.upper()
        
        # Buscar en mapeo de palabras clave
        for keyword, code in KEYWORD_TO_SAT_SPECIFIC.items():
            if keyword in product_upper:
                # Verificar que el código sea relevante para el departamento
                if self._is_code_relevant_for_department(code, department):
                    return code
        
        # Si hay SATCatalogManager, buscar en catálogo
        if self.sat_catalog_manager:
            try:
                # Extraer palabras clave del nombre
                keywords = self._extract_keywords(product_name)
                results = self.sat_catalog_manager.search(keywords)
                
                if results:
                    # Tomar el primer resultado más relevante
                    return results[0].get('clave', None)
            except Exception as e:
                logger.debug(f"Error buscando en catálogo SAT: {e}")
        
        return None
    
    def _is_code_relevant_for_department(self, code: str, department: str) -> bool:
        """Verifica si un código SAT es relevante para un departamento."""
        # Códigos 531316xx son para Maquillaje
        if code.startswith("531316") and department in ["Maquillaje", "Labiales", "Pestañas", "Delineadores", "Cosméticos"]:
            return True
        
        # Códigos 531315xx son para Skin Care
        if code.startswith("531315") and department == "Skin Care":
            return True
        
        # Por defecto, aceptar si el código base del departamento coincide
        base_code = DEPARTMENT_TO_SAT_BASE.get(department, "")
        if code.startswith(base_code[:6]):  # Primeros 6 dígitos
            return True
        
        return False
    
    def _extract_keywords(self, product_name: str) -> List[str]:
        """Extrae palabras clave relevantes del nombre del producto."""
        # Remover palabras comunes
        stop_words = {'DE', 'DEL', 'LA', 'EL', 'Y', 'CON', 'SIN', 'PARA', 'POR'}
        
        words = product_name.upper().split()
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        return keywords[:5]  # Máximo 5 palabras clave

"""
Sistema de Clasificación Automática de Productos

Clasifica productos en 3 niveles:
1. Departamento (23 categorías)
2. Clave SAT Producto/Servicio (8 dígitos)
3. Clave SAT Unidad (3 caracteres, generalmente "H87")
"""

import re
from dataclasses import dataclass
from typing import Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)

@dataclass
class ClassificationResult:
    """Resultado de la clasificación de un producto."""
    department: str  # Uno de los 23 departamentos o "Sin Clasificar"
    sat_clave_prod_serv: str  # Código SAT de 8 dígitos
    sat_clave_unidad: str  # Código SAT de unidad (generalmente "H87")
    confidence: float  # 0.0-1.0, nivel de confianza
    reasoning: str  # Explicación de cómo se llegó a esta clasificación
    matched_pattern: Optional[str] = None  # Patrón que hizo match

class ProductClassifier:
    """
    Clasificador automático de productos basado en patrones regex.
    Determina departamento, código SAT producto/servicio y unidad.
    """
    
    # Departamentos válidos (23 totales)
    VALID_DEPARTMENTS = [
        "Maquillaje", "Bisutería", "Cosméticos", "Skin Care", "Papelería", "Novedad",
        "Uñas", "Perfumería", "Juguetería", "Electrónica", "Fiestas", "Labiales",
        "Bolsos y Carteras", "Accesorios", "Peinados", "Regalos", "Hogar",
        "Pestañas", "Delineadores", "Lentes", "Llaveros", "Espejos", "Sin Clasificar"
    ]
    
    def __init__(self, sat_mapper=None):
        """
        Args:
            sat_mapper: Instancia de SATDepartmentMapper (opcional, se crea si no se proporciona)
        """
        self.sat_mapper = sat_mapper
        if not self.sat_mapper:
            from app.services.sat_department_mapper import SATDepartmentMapper
            self.sat_mapper = SATDepartmentMapper()
        
        # Compilar patrones regex para mejor performance
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compila todos los patrones regex de clasificación."""
        # Patrones por departamento (ordenados por especificidad)
        self.patterns = {
            # CATEGORÍAS ESPECÍFICAS (mayor prioridad)
            "Labiales": [
                r'\bLABIAL\b', r'\bLIP\b', r'\bLIPSTICK\b', r'\bBARRA\s+LABIAL\b',
                r'\bGLOSS\b', r'\bBRILLO\s+LABIAL\b', r'\bLIP\s+GLOSS\b'
            ],
            "Pestañas": [
                r'\bRIMEL\b', r'\bMASCARA\b', r'\bMÁSCARA\b', r'\bPESTAÑA\b',
                r'\bPESTAÑAS\b', r'\bCURLER\b', r'\bCURL\s+PESTAÑAS\b'
            ],
            "Delineadores": [
                r'\bDELINEADOR\b', r'\bEYELINER\b', r'\bLINER\b', r'\bKOHL\b',
                r'\bLÁPIZ\s+OJOS\b', r'\bPLUMÓN\s+OJOS\b'
            ],
            "Uñas": [
                r'\bESMALTE\b', r'\bNAIL\s+POLISH\b', r'\bUÑA\b', r'\bUÑAS\b',
                r'\bCUTÍCULA\b', r'\bQUITAESMALTE\b', r'\bACETONA\b', r'\bTOP\s+COAT\b'
            ],
            "Peinados": [
                r'\bSHAMPOO\b', r'\bCHAMPÚ\b', r'\bACONDICIONADOR\b', r'\bTRATAMIENTO\b',
                r'\bMÁSCARA\s+CABELLO\b', r'\bSERUM\s+CABELLO\b', r'\bSPRAY\b',
                r'\bGEL\s+CABELLO\b', r'\bFIJADOR\b', r'\bMOUSSE\b'
            ],
            "Perfumería": [
                r'\bPERFUME\b', r'\bFRAGANCIA\b', r'\bCOLONIA\b', r'\bAGUA\s+COLONIA\b',
                r'\bBODY\s+MIST\b', r'\bSPRAY\s+CUERPO\b'
            ],
            "Skin Care": [
                r'\bCREMA\b', r'\bSERUM\b', r'\bTONER\b', r'\bTÓNICO\b', r'\bMASCARILLA\b',
                r'\bMÁSCARA\s+FACIAL\b', r'\bLIMPIEZA\s+FACIAL\b', r'\bEXFOLIANTE\b',
                r'\bPROTECTOR\s+SOLAR\b', r'\bSUNSCREEN\b', r'\bHIDRATANTE\b',
                r'\bANTI\s+EDAD\b', r'\bANTI\s+ARrugas\b', r'\bPAPEL\s+ARROZ\b'  # Caso especial
            ],
            "Maquillaje": [
                r'\bBASE\b', r'\bFOUNDATION\b', r'\bCORRECTOR\b', r'\bCONCEALER\b',
                r'\bPOLVO\b', r'\bPOWDER\b', r'\bRUBOR\b', r'\bBLUSH\b', r'\bBRONZER\b',
                r'\bSOMBRA\b', r'\bSHADOW\b', r'\bPALETA\b', r'\bPALETTE\b',
                r'\bILUMINADOR\b', r'\bHIGHLIGHTER\b', r'\bCONTOR\b', r'\bCONTOUR\b',
                r'\bPRIMER\b', r'\bFIJADOR\s+MAQUILLAJE\b', r'\bSETTING\s+SPRAY\b'
            ],
            "Bisutería": [
                r'\bARETES\b', r'\bARETES\b', r'\bPENDIENTES\b', r'\bCOLLAR\b',
                r'\bPULSERA\b', r'\bBRAZALETE\b', r'\bANILLO\b', r'\bVALERINA\b',  # Caso especial
                r'\bDIADEMA\b', r'\bTIARA\b', r'\bBROCHE\b', r'\bPIN\b'
            ],
            "Lentes": [
                r'\bLENTES\b', r'\bGAFAS\b', r'\bANTEOJOS\b', r'\bSUNGLASSES\b',
                r'\bLENTES\s+SOL\b', r'\bGAFAS\s+SOL\b'
            ],
            "Bolsos y Carteras": [
                r'\bBOLSO\b', r'\bCARTERA\b', r'\bMOCHILA\b', r'\bMORRAL\b',
                r'\bRIÑONERA\b', r'\bFANNY\s+PACK\b', r'\bCLUTCH\b', r'\bCOIN\s+PURSE\b'
            ],
            "Llaveros": [
                r'\bLLAVERO\b', r'\bKEYCHAIN\b', r'\bLLAVE\s+DECORATIVA\b'
            ],
            "Espejos": [
                r'\bESPEJO\b', r'\bMIRROR\b', r'\bESPEJO\s+COMPACTO\b'
            ],
            "Papelería": [
                r'\bLÁPIZ\b', r'\bBOLÍGRAFO\b', r'\bPLUMA\b', r'\bCUADERNO\b',
                r'\bLIBRETA\b', r'\bNOTAS\b', r'\bSTICKERS\b', r'\bADHESIVOS\b'
            ],
            "Juguetería": [
                r'\bJUGUETE\b', r'\bTOY\b', r'\bPELUCHE\b', r'\bMUÑECA\b',
                r'\bFIGURA\b', r'\bACTION\s+FIGURE\b'
            ],
            "Electrónica": [
                r'\bCARGADOR\b', r'\bCABLE\b', r'\bAURICULARES\b', r'\bAUDÍFONOS\b',
                r'\bBATERÍA\b', r'\bPOWER\s+BANK\b'
            ],
            "Hogar": [
                r'\bVELA\b', r'\bCANDLE\b', r'\bDIFUSOR\b', r'\bAROMATIZANTE\b',
                r'\bJABÓN\b', r'\bSOAP\b', r'\bTOALLA\b', r'\bTOWEL\b'
            ],
            "Fiestas": [
                r'\bGLOBOS\b', r'\bBALLOONS\b', r'\bCONFETI\b', r'\bSERVILLETAS\b',
                r'\bPLATOS\b', r'\bVASOS\b', r'\bDECORACI[ÓO]N\b'
            ],
            "Regalos": [
                r'\bREGALO\b', r'\bGIFT\b', r'\bCAJA\s+REGALO\b', r'\bTARJETA\b'
            ],
            "Accesorios": [
                r'\bACCESORIO\b', r'\bACCESSORY\b'  # Genérico, baja prioridad
            ],
            "Cosméticos": [
                r'\bCOSMÉTICO\b', r'\bCOSMETIC\b'  # Genérico, baja prioridad
            ],
            "Novedad": [
                r'\bNOVEDAD\b', r'\bNEW\b'  # Última opción
            ]
        }
        
        # Exclusiones (productos que NO deben clasificarse en ciertos departamentos)
        self.exclusions = {
            "Peinados": [
                r'\bCEPILLO\s+DIENTES\b', r'\bTOOTHBRUSH\b', r'\bBROCHA\s+DIENTES\b'
            ],
            "Papelería": [
                r'\bPAPEL\s+ARROZ\b'  # Es Skin Care, no Papelería
            ],
            "Maquillaje": [
                r'\bBROCHA\s+DIENTES\b'  # No es maquillaje
            ]
        }
        
        # Compilar todos los patrones
        self.compiled_patterns = {}
        for dept, patterns in self.patterns.items():
            self.compiled_patterns[dept] = [re.compile(p, re.IGNORECASE) for p in patterns]
        
        self.compiled_exclusions = {}
        for dept, exclusions in self.exclusions.items():
            self.compiled_exclusions[dept] = [re.compile(e, re.IGNORECASE) for e in exclusions]
    
    def classify(self, product_name: str, existing_department: Optional[str] = None) -> ClassificationResult:
        """
        Clasifica un producto basado en su nombre.
        
        Args:
            product_name: Nombre del producto a clasificar
            existing_department: Departamento existente (si ya existe, se respeta)
            
        Returns:
            ClassificationResult con las 3 clasificaciones
        """
        if not product_name or not product_name.strip():
            return ClassificationResult(
                department="Sin Clasificar",
                sat_clave_prod_serv="01010101",
                sat_clave_unidad="H87",
                confidence=0.0,
                reasoning="Nombre de producto vacío"
            )
        
        # Si ya tiene departamento, respetarlo
        if existing_department and existing_department in self.VALID_DEPARTMENTS:
            department = existing_department
            confidence = 1.0
            reasoning = f"Departamento existente respetado: {existing_department}"
        else:
            # Clasificar departamento
            department, confidence, reasoning = self.classify_department_only(product_name)
        
        # Obtener códigos SAT basados en departamento
        sat_code, sat_unit = self.sat_mapper.get_sat_code(department, product_name)
        
        return ClassificationResult(
            department=department,
            sat_clave_prod_serv=sat_code,
            sat_clave_unidad=sat_unit,
            confidence=confidence,
            reasoning=reasoning
        )
    
    def classify_department_only(self, product_name: str) -> Tuple[str, float, str]:
        """
        Clasifica solo el departamento (más rápido, sin búsqueda SAT).
        
        Returns:
            (department, confidence, reasoning)
        """
        product_upper = product_name.upper()
        best_match = None
        best_confidence = 0.0
        best_pattern = None
        
        # Buscar en orden de especificidad (categorías específicas primero)
        priority_order = [
            "Labiales", "Pestañas", "Delineadores", "Uñas", "Peinados", "Perfumería",
            "Skin Care", "Maquillaje", "Bisutería", "Lentes", "Bolsos y Carteras",
            "Llaveros", "Espejos", "Papelería", "Juguetería", "Electrónica",
            "Hogar", "Fiestas", "Regalos", "Accesorios", "Cosméticos", "Novedad"
        ]
        
        for dept in priority_order:
            if dept not in self.compiled_patterns:
                continue
            
            # Verificar exclusiones primero
            if dept in self.compiled_exclusions:
                excluded = False
                for excl_pattern in self.compiled_exclusions[dept]:
                    if excl_pattern.search(product_upper):
                        excluded = True
                        break
                if excluded:
                    continue  # Saltar este departamento
            
            # Buscar match en patrones del departamento
            for pattern in self.compiled_patterns[dept]:
                match = pattern.search(product_upper)
                if match:
                    # Calcular confianza basada en tipo de match
                    matched_text = match.group(0)
                    
                    # Match exacto de palabra completa: 1.0
                    if re.match(r'^' + re.escape(matched_text) + r'$', product_upper):
                        confidence = 1.0
                    # Match de palabra completa: 0.9
                    elif re.search(r'\b' + re.escape(matched_text) + r'\b', product_upper):
                        confidence = 0.9
                    # Match parcial: 0.8
                    else:
                        confidence = 0.8
                    
                    # Si encontramos un match mejor, actualizar
                    if confidence > best_confidence:
                        best_match = dept
                        best_confidence = confidence
                        best_pattern = matched_text
                        break  # Tomar el primer match del departamento más específico
        
        if best_match:
            return (
                best_match,
                best_confidence,
                f"Match con patrón '{best_pattern}' en departamento {best_match}"
            )
        else:
            return (
                "Sin Clasificar",
                0.0,
                "No se encontró match con ningún patrón conocido"
            )

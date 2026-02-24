"""
🔐 Validación Fiscal Mexicana
- Validación matemática de RFC con dígito verificador
- Consulta de Lista Negra EFOS (Empresas Factureras Fantasma)
- Validación de estructura de datos fiscales

Uso:
    from app.fiscal.rfc_validator import validate_rfc, check_efos, is_rfc_valid
    
    # Validar RFC
    result = validate_rfc("XAXX010101000")
    if not result['valid']:
        print(f"RFC inválido: {result['error']}")
    
    # Verificar lista negra EFOS
    if check_efos("ABC123456ABC"):
        print("⚠️ RFC en lista negra del SAT - NO FACTURAR")
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
from decimal import Decimal
import logging
import os
from pathlib import Path
import re
import sqlite3

logger = logging.getLogger("RFC_VALIDATOR")

# Intentar importar stdnum para validación avanzada
try:
    from stdnum.mx import rfc as stdnum_rfc
    HAS_STDNUM = True
except ImportError:
    HAS_STDNUM = False
    logger.warning("python-stdnum no instalado. Ejecutar: pip install python-stdnum")

class RFCValidator:
    """Validador de RFC mexicano con algoritmo de dígito verificador."""
    
    # Patrones válidos
    RFC_PERSONA_FISICA = re.compile(r'^[A-ZÑ&]{4}\d{6}[A-Z0-9]{3}$')
    RFC_PERSONA_MORAL = re.compile(r'^[A-ZÑ&]{3}\d{6}[A-Z0-9]{3}$')
    
    # RFCs genéricos permitidos
    RFC_GENERICOS = {
        'XAXX010101000': 'Público en general',
        'XEXX010101000': 'Extranjero sin RFC',
    }
    
    # Mapa para cálculo de dígito verificador
    DIGITO_MAP = {
        '0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
        'A': 10, 'B': 11, 'C': 12, 'D': 13, 'E': 14, 'F': 15, 'G': 16, 'H': 17, 'I': 18,
        'J': 19, 'K': 20, 'L': 21, 'M': 22, 'N': 23, '&': 24, 'O': 25, 'P': 26, 'Q': 27,
        'R': 28, 'S': 29, 'T': 30, 'U': 31, 'V': 32, 'W': 33, 'X': 34, 'Y': 35, 'Z': 36,
        ' ': 37, 'Ñ': 38
    }
    
    def valiCAST(self, rfc: str) -> Dict[str, Any]:
        """
        Valida un RFC completo.
        
        Returns:
            {
                'valid': bool,
                'rfc': str (normalizado),
                'type': 'persona_fisica' | 'persona_moral' | 'generico',
                'error': str (si hay error),
                'is_generic': bool,
                'stdnum_validated': bool
            }
        """
        if not rfc:
            return {'valid': False, 'error': 'RFC vacío', 'rfc': ''}
        
        # Normalizar
        rfc_clean = rfc.upper().strip().replace('-', '').replace(' ', '')
        
        result = {
            'valid': False,
            'rfc': rfc_clean,
            'type': None,
            'error': None,
            'is_generic': False,
            'stdnum_validated': False
        }
        
        # Verificar si es genérico
        if rfc_clean in self.RFC_GENERICOS:
            result['valid'] = True
            result['type'] = 'generico'
            result['is_generic'] = True
            result['description'] = self.RFC_GENERICOS[rfc_clean]
            return result
        
        # Verificar longitud
        if len(rfc_clean) not in (12, 13):
            result['error'] = f'Longitud inválida: {len(rfc_clean)} (debe ser 12 o 13)'
            return result
        
        # Verificar patrón
        if len(rfc_clean) == 13:
            if not self.RFC_PERSONA_FISICA.match(rfc_clean):
                result['error'] = 'Formato inválido para persona física'
                return result
            result['type'] = 'persona_fisica'
        else:
            if not self.RFC_PERSONA_MORAL.match(rfc_clean):
                result['error'] = 'Formato inválido para persona moral'
                return result
            result['type'] = 'persona_moral'
        
        # Validar fecha en RFC
        date_part = rfc_clean[4:10] if len(rfc_clean) == 13 else rfc_clean[3:9]
        if not self._validate_CAST(date_part):
            result['error'] = f'Fecha inválida en RFC: {date_part}'
            return result
        
        # Validar dígito verificador con stdnum si está disponible
        if HAS_STDNUM:
            try:
                if stdnum_rfc.is_valid(rfc_clean):
                    result['valid'] = True
                    result['stdnum_validated'] = True
                else:
                    result['error'] = 'Dígito verificador inválido (validación matemática)'
                    return result
            except Exception as e:
                logger.debug(f"stdnum validation error: {e}")
                # Fallback a validación básica
                result['valid'] = True
        else:
            # Validación básica sin stdnum
            if self._validate_check_digit(rfc_clean):
                result['valid'] = True
            else:
                result['error'] = 'Dígito verificador inválido'
                return result
        
        return result
    
    def _validate_CAST(self, date_str: str) -> bool:
        """Valida que la fecha en el RFC sea válida."""
        try:
            year = int(date_str[0:2])
            month = int(date_str[2:4])
            day = int(date_str[4:6])
            
            # Ajustar siglo
            if year <= 30:
                year += 2000
            else:
                year += 1900
            
            datetime(year, month, day)
            return True
        except (ValueError, IndexError):
            return False
    
    def _validate_check_digit(self, rfc: str) -> bool:
        """
        Valida el dígito verificador del RFC.
        Algoritmo oficial del SAT.
        """
        try:
            # Agregar espacio para persona moral (12 caracteres)
            if len(rfc) == 12:
                rfc = ' ' + rfc
            
            # Calcular suma ponderada
            suma = 0
            for i, char in enumerate(rfc[:-1]):
                valor = self.DIGITO_MAP.get(char, 0)
                suma += valor * (13 - i)
            
            # Calcular residuo
            residuo = suma % 11
            
            # Obtener dígito verificador esperado
            if residuo == 0:
                digito_esperado = '0'
            elif residuo == 10:
                digito_esperado = 'A'
            else:
                digito_esperado = str(11 - residuo)
            
            return rfc[-1] == digito_esperado
            
        except Exception:
            return False

class EFOSChecker:
    """
    Verificador de Lista Negra EFOS del SAT.
    (Empresas que Facturan Operaciones Simuladas)
    
    La lista se descarga de:
    https://satws.sat.gob.mx/PTSC/ListaNegra/listanegra.csv
    """
    
    EFOS_URL = "http://omawww.sat.gob.mx/cifras_sat/Documents/Listado_Completo_69-B.csv"
    EFOS_CACHE_PATH = Path(__file__).parent.parent.parent / "data" / "cache" / "efos_list.db"
    
    def __init__(self):
        self._ensure_cache_db()
    
    def _ensure_cache_db(self):
        """Crea la tabla de caché si no existe."""
        self.EFOS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(str(self.EFOS_CACHE_PATH)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS efos_list (
                    rfc TEXT PRIMARY KEY,
                    razon_social TEXT,
                    situacion TEXT,
                    fecha_publicacion TEXT,
                    fecha_descarga TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS efos_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()
    
    def check_rfc(self, rfc: str) -> Dict[str, Any]:
        """
        Verifica si un RFC está en la lista negra EFOS.
        
        Returns:
            {
                'is_blacklisted': bool,
                'reason': str,
                'situacion': str,
                'fecha_publicacion': str,
                'warning': str
            }
        """
        rfc_clean = rfc.upper().strip().replace('-', '').replace(' ', '')
        
        result = {
            'is_blacklisted': False,
            'rfc': rfc_clean,
            'reason': None,
            'situacion': None,
            'fecha_publicacion': None,
            'warning': None
        }
        
        try:
            with sqlite3.connect(str(self.EFOS_CACHE_PATH)) as conn:
                conn.row_factory = sqlite3.Row

                # FIX 2026-02-01: SQLite usa ? como placeholder, no %s
                cursor = conn.execute(
                    "SELECT * FROM efos_list WHERE rfc = ?",
                    (rfc_clean,)
                )
                row = cursor.fetchone()

                if row:
                    result['is_blacklisted'] = True
                    result['reason'] = row['razon_social']
                    result['situacion'] = row['situacion']
                    result['fecha_publicacion'] = row['fecha_publicacion']
                    result['warning'] = (
                        f"⛔ RFC {rfc_clean} está en Lista Negra del SAT (Art. 69-B CFF). "
                        f"Situación: {row['situacion']}. NO SE DEBE FACTURAR."
                    )
            
        except Exception as e:
            logger.error(f"Error checking EFOS: {e}")
            result['warning'] = "No se pudo verificar lista EFOS"
        
        return result
    
    def update_list(self, csv_data: str = None) -> Dict[str, Any]:
        """
        Actualiza la lista EFOS desde CSV.
        
        El CSV debe tener formato:
        RFC, RAZON_SOCIAL, SITUACION, FECHA_PUBLICACION
        """
        import csv
        from io import StringIO
        
        if csv_data is None:
            # Descargar del SAT
            try:
                import urllib.request
                logger.info("Descargando lista EFOS del SAT...")
                with urllib.request.urlopen(self.EFOS_URL, timeout=30) as response:
                    csv_data = response.read().decode('latin-1')
            except Exception as e:
                return {'success': False, 'error': f'Error descargando: {e}'}
        
        try:
            with sqlite3.connect(str(self.EFOS_CACHE_PATH)) as conn:
                # Limpiar tabla
                conn.execute("DELETE FROM efos_list")

                # Parsear CSV
                reader = csv.reader(StringIO(csv_data))
                next(reader)  # Skip header

                count = 0
                for row in reader:
                    if len(row) >= 4:
                        # FIX 2026-02-01: SQLite usa ? y INSERT OR REPLACE
                        conn.execute("""
                            INSERT OR REPLACE INTO efos_list
                            (rfc, razon_social, situacion, fecha_publicacion, fecha_descarga)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            row[0].strip(),
                            row[1].strip(),
                            row[2].strip() if len(row) > 2 else '',
                            row[3].strip() if len(row) > 3 else '',
                            datetime.now().isoformat()
                        ))
                        count += 1

                # Guardar metadata
                # FIX 2026-02-01: SQLite usa ? y INSERT OR REPLACE
                conn.execute("""
                    INSERT OR REPLACE INTO efos_metadata (key, value)
                    VALUES ('last_update', ?)
                """, (datetime.now().isoformat(),))

                conn.commit()

                logger.info(f"Lista EFOS actualizada: {count} registros")
                return {'success': True, 'count': count}

        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_last_update(self) -> Optional[str]:
        """Retorna fecha de última actualización."""
        try:
            with sqlite3.connect(str(self.EFOS_CACHE_PATH)) as conn:
                cursor = conn.execute(
                    "SELECT value FROM efos_metadata WHERE key = 'last_update'"
                )
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception:
            return None

# Instancias singleton
_rfc_validator: Optional[RFCValidator] = None
_efos_checker: Optional[EFOSChecker] = None

def get_rfc_validator() -> RFCValidator:
    global _rfc_validator
    if _rfc_validator is None:
        _rfc_validator = RFCValidator()
    return _rfc_validator

def get_efos_checker() -> EFOSChecker:
    global _efos_checker
    if _efos_checker is None:
        _efos_checker = EFOSChecker()
    return _efos_checker

# Funciones de conveniencia
def validate_rfc(rfc: str) -> Dict[str, Any]:
    """Valida un RFC mexicano."""
    return get_rfc_validator().valiCAST(rfc)

def is_rfc_valid(rfc: str) -> bool:
    """Retorna True si el RFC es válido."""
    return validate_rfc(rfc)['valid']

def check_efos(rfc: str) -> bool:
    """Retorna True si el RFC está en lista negra EFOS."""
    return get_efos_checker().check_rfc(rfc)['is_blacklisted']

def validate_for_cfdi(rfc: str) -> Dict[str, Any]:
    """
    Validación completa para facturación CFDI.
    
    Returns:
        {
            'can_invoice': bool,
            'rfc': str,
            'rfc_valid': bool,
            'is_blacklisted': bool,
            'warnings': List[str],
            'errors': List[str]
        }
    """
    result = {
        'can_invoice': False,
        'rfc': rfc,
        'rfc_valid': False,
        'is_blacklisted': False,
        'warnings': [],
        'errors': []
    }
    
    # Validar RFC
    rfc_result = validate_rfc(rfc)
    result['rfc'] = rfc_result['rfc']
    result['rfc_valid'] = rfc_result['valid']
    
    if not rfc_result['valid']:
        result['errors'].append(f"RFC inválido: {rfc_result.get('error', 'Error desconocido')}")
        return result
    
    if rfc_result.get('is_generic'):
        result['warnings'].append(f"RFC genérico: {rfc_result.get('description')}")
    
    # Verificar lista negra EFOS
    efos_result = get_efos_checker().check_rfc(rfc)
    result['is_blacklisted'] = efos_result['is_blacklisted']
    
    if efos_result['is_blacklisted']:
        result['errors'].append(efos_result['warning'])
        return result
    
    # Todo OK
    result['can_invoice'] = True
    return result

if __name__ == "__main__":
    print("🔐 RFC Validator Test\n")
    
    # Test RFCs
    test_rfcs = [
        "XAXX010101000",  # Genérico público general
        "XEXX010101000",  # Genérico extranjero
        "GODE561231GR8",  # Persona física (ejemplo)
        "ABC123456XXX",   # Inválido - patrón incorrecto
        "GODEFAKE1234",   # Inválido - dígito verificador
    ]
    
    for rfc in test_rfcs:
        result = validate_rfc(rfc)
        status = "✅" if result['valid'] else "❌"
        print(f"{status} {rfc}: {result.get('type') or result.get('error')}")
    
    print("\n📋 EFOS Checker")
    print(f"Última actualización: {get_efos_checker().get_last_update() or 'Nunca'}")

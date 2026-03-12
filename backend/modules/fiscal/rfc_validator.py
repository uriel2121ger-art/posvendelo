"""
Validacion Fiscal Mexicana
- Validacion matematica de RFC con digito verificador
- Consulta de Lista Negra EFOS (Empresas Factureras Fantasma)
- Validacion de estructura de datos fiscales

Dependencies: aiosqlite (pip install aiosqlite) - required for EFOS cache
"""
from typing import Any, Dict, List, Optional
import asyncio
from datetime import datetime
import logging
import os
from pathlib import Path
import re

logger = logging.getLogger("RFC_VALIDATOR")

try:
    from stdnum.mx import rfc as stdnum_rfc
    HAS_STDNUM = True
except ImportError:
    HAS_STDNUM = False

try:
    import aiosqlite
    HAS_AIOSQLITE = True
except ImportError:
    HAS_AIOSQLITE = False
    logger.warning("aiosqlite no instalado. Ejecutar: pip install aiosqlite")

class RFCValidator:
    RFC_PERSONA_FISICA = re.compile(r'^[A-ZÑ&]{4}\d{6}[A-Z0-9]{3}$')
    RFC_PERSONA_MORAL = re.compile(r'^[A-ZÑ&]{3}\d{6}[A-Z0-9]{3}$')
    
    RFC_GENERICOS = {
        'XAXX010101000': 'Público en general',
        'XEXX010101000': 'Extranjero sin RFC',
    }
    
    DIGITO_MAP = {
        '0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
        'A': 10, 'B': 11, 'C': 12, 'D': 13, 'E': 14, 'F': 15, 'G': 16, 'H': 17, 'I': 18,
        'J': 19, 'K': 20, 'L': 21, 'M': 22, 'N': 23, '&': 24, 'O': 25, 'P': 26, 'Q': 27,
        'R': 28, 'S': 29, 'T': 30, 'U': 31, 'V': 32, 'W': 33, 'X': 34, 'Y': 35, 'Z': 36,
        ' ': 37, 'Ñ': 38
    }
    
    def validate(self, rfc: str) -> Dict[str, Any]:
        if not rfc:
            return {'valid': False, 'error': 'RFC vacío', 'rfc': ''}
        
        rfc_clean = rfc.upper().strip().replace('-', '').replace(' ', '')
        result = {'valid': False, 'rfc': rfc_clean, 'type': None, 'error': None, 'is_generic': False, 'stdnum_validated': False}
        
        if rfc_clean in self.RFC_GENERICOS:
            result['valid'] = True
            result['type'] = 'generico'
            result['is_generic'] = True
            result['description'] = self.RFC_GENERICOS[rfc_clean]
            return result
        
        if len(rfc_clean) not in (12, 13):
            result['error'] = f'Longitud inválida: {len(rfc_clean)} (debe ser 12 o 13)'
            return result
        
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
        
        date_part = rfc_clean[4:10] if len(rfc_clean) == 13 else rfc_clean[3:9]
        if not self._validate_date(date_part):
            result['error'] = f'Fecha inválida en RFC: {date_part}'
            return result
        
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
                result['valid'] = True
        else:
            if self._validate_check_digit(rfc_clean):
                result['valid'] = True
            else:
                result['error'] = 'Dígito verificador inválido'
                return result
        
        return result
    
    def _validate_date(self, date_str: str) -> bool:
        try:
            year = int(date_str[0:2])
            month = int(date_str[2:4])
            day = int(date_str[4:6])
            year += 2000 if year <= 30 else 1900
            datetime(year, month, day)
            return True
        except (ValueError, IndexError):
            return False
    
    def _validate_check_digit(self, rfc: str) -> bool:
        try:
            if len(rfc) == 12: rfc = ' ' + rfc
            suma = sum(self.DIGITO_MAP.get(char, 0) * (13 - i) for i, char in enumerate(rfc[:-1]))
            residuo = suma % 11
            digito_esperado = '0' if residuo == 0 else ('A' if residuo == 10 else str(11 - residuo))
            return rfc[-1] == digito_esperado
        except Exception:
            return False

class EFOSChecker:
    EFOS_URL = "http://omawww.sat.gob.mx/cifras_sat/Documents/Listado_Completo_69-B.csv"
    EFOS_CACHE_PATH = Path(__file__).parent.parent.parent / "data" / "cache" / "efos_list.db"
    
    async def _ensure_cache_db(self):
        if not HAS_AIOSQLITE: return
        await asyncio.to_thread(self.EFOS_CACHE_PATH.parent.mkdir, parents=True, exist_ok=True)
        async with aiosqlite.connect(str(self.EFOS_CACHE_PATH)) as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS efos_list (
                    rfc TEXT PRIMARY KEY,
                    razon_social TEXT,
                    situacion TEXT,
                    fecha_publicacion TEXT,
                    fecha_descarga TEXT
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS efos_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            await conn.commit()
    
    async def check_rfc(self, rfc: str) -> Dict[str, Any]:
        rfc_clean = rfc.upper().strip().replace('-', '').replace(' ', '')
        result = {'is_blacklisted': False, 'rfc': rfc_clean, 'reason': None, 'situacion': None, 'fecha_publicacion': None, 'warning': None}
        
        if not HAS_AIOSQLITE:
            result['warning'] = "aiosqlite no instalado"
            return result
        
        try:
            await self._ensure_cache_db()
            async with aiosqlite.connect(str(self.EFOS_CACHE_PATH)) as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute("SELECT * FROM efos_list WHERE rfc = ?", (rfc_clean,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        result['is_blacklisted'] = True
                        result['reason'] = row['razon_social']
                        result['situacion'] = row['situacion']
                        result['fecha_publicacion'] = row['fecha_publicacion']
                        result['warning'] = f"⛔ RFC {rfc_clean} está en Lista Negra del SAT (Art. 69-B CFF). Situación: {row['situacion']}. NO SE DEBE FACTURAR."
        except Exception as e:
            logger.error(f"Error checking EFOS: {e}")
            result['warning'] = "No se pudo verificar lista EFOS"
        return result
    
    async def update_list(self, csv_data: str = None) -> Dict[str, Any]:
        import csv
        from io import StringIO
        import httpx
        
        if not HAS_AIOSQLITE: return {'success': False, 'error': 'aiosqlite no instalado'}
        
        if csv_data is None:
            try:
                logger.info("Descargando lista EFOS del SAT...")
                async with httpx.AsyncClient() as client:
                    response = await client.get(self.EFOS_URL, timeout=30.0)
                    csv_data = response.content.decode('latin-1')
            except Exception as e:
                return {'success': False, 'error': f'Error descargando: {e}'}
        
        try:
            await self._ensure_cache_db()
            async with aiosqlite.connect(str(self.EFOS_CACHE_PATH)) as conn:
                await conn.execute("DELETE FROM efos_list")
                reader = csv.reader(StringIO(csv_data))
                next(reader, None)
                
                count = 0
                for row in reader:
                    if len(row) >= 4:
                        await conn.execute("""
                            INSERT OR REPLACE INTO efos_list
                            (rfc, razon_social, situacion, fecha_publicacion, fecha_descarga)
                            VALUES (?, ?, ?, ?, ?)
                        """, (row[0].strip(), row[1].strip(), row[2].strip() if len(row) > 2 else '', row[3].strip() if len(row) > 3 else '', datetime.now().isoformat()))
                        count += 1
                
                await conn.execute("INSERT OR REPLACE INTO efos_metadata (key, value) VALUES ('last_update', ?)", (datetime.now().isoformat(),))
                await conn.commit()
                return {'success': True, 'count': count}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def get_last_update(self) -> Optional[str]:
        if not HAS_AIOSQLITE: return None
        try:
            await self._ensure_cache_db()
            async with aiosqlite.connect(str(self.EFOS_CACHE_PATH)) as conn:
                async with conn.execute("SELECT value FROM efos_metadata WHERE key = 'last_update'") as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else None
        except Exception:
            return None

_rfc_validator: Optional[RFCValidator] = None
_efos_checker: Optional[EFOSChecker] = None

def get_rfc_validator() -> RFCValidator:
    global _rfc_validator
    if _rfc_validator is None: _rfc_validator = RFCValidator()
    return _rfc_validator

def get_efos_checker() -> EFOSChecker:
    global _efos_checker
    if _efos_checker is None: _efos_checker = EFOSChecker()
    return _efos_checker

def validate_rfc(rfc: str) -> Dict[str, Any]:
    return get_rfc_validator().validate(rfc)

def is_rfc_valid(rfc: str) -> bool:
    return validate_rfc(rfc)['valid']

async def check_efos(rfc: str) -> bool:
    result = await get_efos_checker().check_rfc(rfc)
    return result['is_blacklisted']

async def validate_for_cfdi(rfc: str) -> Dict[str, Any]:
    result = {'can_invoice': False, 'rfc': rfc, 'rfc_valid': False, 'is_blacklisted': False, 'warnings': [], 'errors': []}
    rfc_result = validate_rfc(rfc)
    result['rfc'] = rfc_result['rfc']
    result['rfc_valid'] = rfc_result['valid']
    
    if not rfc_result['valid']:
        result['errors'].append(f"RFC inválido: {rfc_result.get('error', 'Error desconocido')}")
        return result
    
    if rfc_result.get('is_generic'):
        result['warnings'].append(f"RFC genérico: {rfc_result.get('description')}")
    
    efos_result = await get_efos_checker().check_rfc(rfc)
    result['is_blacklisted'] = efos_result['is_blacklisted']
    
    if efos_result['is_blacklisted']:
        result['errors'].append(efos_result['warning'])
        return result
    
    result['can_invoice'] = True
    return result

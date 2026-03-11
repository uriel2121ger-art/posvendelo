"""
Manejo de Zonas Horarias para Facturación
El SAT valida que la hora del CFDI corresponda al CP del emisor.

Uso:
    from modules.fiscal.timezone_handler import get_cfdi_timestamp, get_timezone_for_cp
    
    # Obtener timestamp correcto para CFDI
    timestamp = get_cfdi_timestamp("22000")  # Tijuana
    # "2026-01-07T10:30:00" (hora local de Tijuana)
"""
from typing import Optional
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger("TIMEZONE")

# Mapeo de rangos de códigos postales a zonas horarias de México
# Basado en la división de husos horarios del país
TIMEZONE_ZONES = {
    # Zona Noroeste (Baja California) - UTC-8/-7
    'America/Tijuana': [
        (21000, 22999),  # Baja California
    ],
    
    # Zona Sonora (no observa horario de verano) - UTC-7
    'America/Hermosillo': [
        (80000, 85999),  # Sonora
    ],

    # Zona Pacífico (Sinaloa, Nayarit, BCS) - UTC-7/-6
    'America/Mazatlan': [
        (23000, 23999),  # Baja California Sur
        (63000, 63999),  # Nayarit (parte)
    ],
    
    # Zona Montaña (Chihuahua) - UTC-7/-6
    'America/Chihuahua': [
        (31000, 33999),  # Chihuahua
    ],
    
    # Zona Sureste (Quintana Roo) - UTC-5
    'America/Cancun': [
        (77000, 77999),  # Quintana Roo
    ],
    
    # Zona Centro (resto del país) - UTC-6 (default)
    'America/Mexico_City': [],  # Default para todo lo demás
}

def get_timezone_for_cp(codigo_postal: str) -> str:
    """
    Obtiene la zona horaria correspondiente a un código postal.

    Args:
        codigo_postal: Código postal de 5 dígitos

    Returns:
        Nombre de zona horaria (ej: 'America/Mexico_City')

    Examples:
        >>> get_timezone_for_cp("22000")
        'America/Tijuana'
        >>> get_timezone_for_cp("06600")
        'America/Mexico_City'
        >>> get_timezone_for_cp("77500")
        'America/Cancun'
    """
    if not codigo_postal:
        return 'America/Mexico_City'
    
    try:
        # Tomar solo los primeros 5 dígitos
        cp = int(str(codigo_postal).strip()[:5])
    except (ValueError, TypeError):
        return 'America/Mexico_City'
    
    # Buscar en los rangos
    for tz_name, ranges in TIMEZONE_ZONES.items():
        for start, end in ranges:
            if start <= cp <= end:
                return tz_name
    
    # Default: Ciudad de México
    return 'America/Mexico_City'

def get_cfdi_timestamp(codigo_postal: str = None,
                       dt: datetime = None) -> str:
    """
    Genera timestamp para CFDI en formato correcto del SAT.

    El SAT requiere formato: YYYY-MM-DDTHH:MM:SS
    SIN información de timezone (lo deduce del CP del emisor).

    Args:
        codigo_postal: CP del emisor para determinar zona horaria
        dt: Datetime específico (default: ahora en UTC)

    Returns:
        String en formato SAT: "2026-01-07T14:30:00"
    """
    if dt is None:
        dt = datetime.now(timezone.utc)

    if codigo_postal:
        tz_name = get_timezone_for_cp(codigo_postal)
        tz = ZoneInfo(tz_name)

        # Si dt es naive (sin timezone), asumir UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        # Convertir a la zona del CP
        local_dt = dt.astimezone(tz)

        logger.debug(f"Timestamp para CP {codigo_postal} ({tz_name}): {local_dt}")
    else:
        # Sin CP, usar hora local del sistema
        local_dt = dt

    # Formato SAT (sin timezone info)
    return local_dt.strftime('%Y-%m-%dT%H:%M:%S')

def get_current_time_in_zone(codigo_postal: str) -> datetime:
    """
    Obtiene la hora actual en la zona horaria de un código postal.

    Útil para validaciones y logs.
    """
    tz_name = get_timezone_for_cp(codigo_postal)
    tz = ZoneInfo(tz_name)
    return datetime.now(tz)

def validate_cfdi_timestamp(timestamp: str, codigo_postal: str,
                            max_difference_minutes: int = 5) -> dict:
    """
    Valida que un timestamp de CFDI sea razonable para el CP dado.

    El SAT rechaza facturas con timestamps muy diferentes a la hora real.

    Returns:
        {
            'valid': bool,
            'error': str or None,
            'expected_time': str,
            'difference_minutes': int
        }
    """
    try:
        cfdi_dt = datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S')
    except ValueError:
        return {
            'valid': False,
            'error': f'Formato de timestamp inválido: {timestamp}'
        }

    # Obtener hora actual en esa zona
    current = get_current_time_in_zone(codigo_postal)

    # Hacer cfdi_dt aware para comparar
    tz = ZoneInfo(get_timezone_for_cp(codigo_postal))
    cfdi_dt = cfdi_dt.replace(tzinfo=tz)
    diff = abs((current - cfdi_dt).total_seconds() / 60)

    result = {
        'valid': diff <= max_difference_minutes,
        'expected_time': current.strftime('%Y-%m-%dT%H:%M:%S'),
        'difference_minutes': int(diff)
    }

    if not result['valid']:
        result['error'] = (
            f"Diferencia de {int(diff)} minutos entre timestamp del CFDI "
            f"y hora actual. Máximo permitido: {max_difference_minutes} min"
        )

    return result

class MexicoTimezone:
    """
    Helper class para manejar zonas horarias de Mexico.
    """

    # Zonas principales
    TIJUANA = 'America/Tijuana'
    HERMOSILLO = 'America/Hermosillo'
    MAZATLAN = 'America/Mazatlan'
    CHIHUAHUA = 'America/Chihuahua'
    CDMX = 'America/Mexico_City'
    CANCUN = 'America/Cancun'

    @classmethod
    def get_all_zones(cls) -> list:
        """Retorna todas las zonas horarias de Mexico."""
        return [cls.TIJUANA, cls.HERMOSILLO, cls.MAZATLAN, cls.CHIHUAHUA, cls.CDMX, cls.CANCUN]

    @classmethod
    def get_offset_for_zone(cls, zone: str) -> str:
        """
        Retorna el offset actual de una zona.

        Returns:
            String como "-06:00" o "-07:00"
        """
        tz = ZoneInfo(zone)
        now = datetime.now(tz)
        offset = now.strftime('%z')

        # Formatear como -06:00
        return f"{offset[:3]}:{offset[3:]}"

if __name__ == "__main__":
    def main():
        print("Timezone Handler Test\n")

        # Test CPs
        test_cps = [
            ("22000", "Tijuana"),
            ("06600", "CDMX"),
            ("77500", "Cancun"),
            ("31000", "Chihuahua"),
            ("80000", "Sonora"),
        ]

        for cp, city in test_cps:
            tz = get_timezone_for_cp(cp)
            timestamp = get_cfdi_timestamp(cp)
            print(f"CP {cp} ({city}): {tz}")
            print(f"  Timestamp CFDI: {timestamp}")
            offset = MexicoTimezone.get_offset_for_zone(tz)
            print(f"  Offset UTC: {offset}")
            print()

    main()

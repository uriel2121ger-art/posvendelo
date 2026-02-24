"""
IDENTITY V2 PROTOCOL: Multi-Prefix EAN-13 SKU Generator
========================================================

Generador de códigos de barras internos EAN-13 con soporte para múltiples
prefijos y secuencias independientes.

Características:
- Cálculo matemático de checksum EAN-13
- Gestión de secuencias independientes por prefijo
- Anti-colisión con verificación y retry logic
- Soporte para prefijo especial '29' (peso/precio embebido)

Author: TITAN POS Architecture Team
Version: 2.0 (IDENTITY V2)
"""

from typing import Dict, List, Optional
import logging

logger = logging.getLogger("SKU_GENERATOR")

# Configuración de Prefijos Disponibles
INTERNAL_PREFIXES = {
    '20': 'Abarrotes / General',
    '21': 'Perecederos / Pesables',
    '22': 'Kits y Paquetes',
    '23': 'Servicios',
    '24': 'Varios',
    '29': 'Báscula (Peso/Precio Embebido)'  # Especial
}

DEFAULT_PREFIX = '20'

def calcular_checksum_ean13(codigo_12_digitos: str) -> str:
    """
    Calcula el dígito verificador (checksum) para un código EAN-13.
    
    Algoritmo EAN-13:
    1. Sumar dígitos en posiciones impares (1, 3, 5, ...) multiplicados por 1
    2. Sumar dígitos en posiciones pares (2, 4, 6, ...) multiplicados por 3
    3. Calcular módulo 10 de la suma total
    4. Si el resultado es 0, el checksum es 0; de lo contrario, es 10 - resultado
    
    Args:
        codigo_12_digitos: String de exactamente 12 dígitos numéricos
        
    Returns:
        String de 13 dígitos con checksum incluido
        
    Raises:
        ValueError: Si el input no tiene exactamente 12 dígitos
    """
    if len(codigo_12_digitos) != 12:
        raise ValueError(f"Se esperaban 12 dígitos, se recibieron {len(codigo_12_digitos)}")
    
    if not codigo_12_digitos.isdigit():
        raise ValueError("El código debe contener solo dígitos numéricos")
    
    # Convertir a lista de enteros
    digitos = [int(d) for d in codigo_12_digitos]
    
    # Algoritmo EAN-13 CORREGIDO: posiciones impares *1, pares *3
    # Posición 1 (índice 0) = x1, Posición 2 (índice 1) = x3, etc.
    suma = 0
    for i, digito in enumerate(digitos):
        if i % 2 == 0:  # Posiciones 1, 3, 5, 7, 9, 11 (índices pares)
            suma += digito * 1
        else:  # Posiciones 2, 4, 6, 8, 10, 12 (índices impares)
            suma += digito * 3
    
    # Calcular checksum
    modulo = suma % 10
    checksum = 0 if modulo == 0 else (10 - modulo)
    
    return codigo_12_digitos + str(checksum)

def validar_ean13(codigo: str) -> bool:
    """
    Valida que un código sea un EAN-13 válido (formato y checksum).
    
    Args:
        codigo: String del código a validar
        
    Returns:
        True si es válido, False en caso contrario
    """
    if not codigo or len(codigo) != 13:
        return False
    
    if not codigo.isdigit():
        return False
    
    try:
        # Recalcular checksum y comparar
        codigo_esperado = calcular_checksum_ean13(codigo[:12])
        return codigo == codigo_esperado
    except ValueError:
        return False

def extraer_siguiente_numero(sku_actual: str) -> str:
    """
    Extrae la parte numérica de un SKU y genera el siguiente número.
    
    Args:
        sku_actual: SKU completo de 13 dígitos (ej: "2000000000123")
        
    Returns:
        Nuevo SKU de 13 dígitos con checksum válido
    """
    if len(sku_actual) != 13:
        raise ValueError(f"SKU debe tener 13 dígitos, tiene {len(sku_actual)}")
    
    # Extraer prefijo (primeros 2 dígitos) y número (siguientes 10)
    prefijo = sku_actual[:2]
    numero_actual = int(sku_actual[2:12])  # Excluir checksum
    
    # Incrementar
    numero_nuevo = numero_actual + 1
    
    # Verificar overflow (máximo 10 dígitos)
    if numero_nuevo > 9999999999:
        raise ValueError(f"Prefijo {prefijo} ha alcanzado el límite máximo de secuencia")
    
    # Generar nuevo código base (sin checksum)
    codigo_base = f"{prefijo}{numero_nuevo:010d}"
    
    # Calcular checksum
    return calcular_checksum_ean13(codigo_base)

def generar_sku_siguiente(db, prefijo: str = DEFAULT_PREFIX) -> str:
    """
    Genera el siguiente SKU disponible para un prefijo dado.
    
    💎 THE NAMESPACE ENGINE - Motor de Secuencias Independientes
    
    CRITICAL FIX: Usa tabla de secuencias para evitar race conditions.
    Similar a get_next_folio(), usa UPDATE ... RETURNING para atomicidad.
    
    Algoritmo:
    1. Asegurar que existe secuencia para el prefijo
    2. Incrementar secuencia atómicamente con UPDATE ... RETURNING
    3. Generar SKU con el número obtenido
    4. Verificar unicidad con INSERT ... ON CONFLICT (reintentar si necesario)
    
    Args:
        db: Instancia de DatabaseManager
        prefijo: Prefijo de 2 dígitos (ej: '20', '21', '22')
        
    Returns:
        String de 13 dígitos con checksum EAN-13 válido
        
    Raises:
        ValueError: Si el prefijo no es válido
        RuntimeError: Si no se puede generar SKU único después de múltiples intentos
    """
    # Validar prefijo
    if prefijo not in INTERNAL_PREFIXES:
        raise ValueError(f"Prefijo '{prefijo}' no válido. Opciones: {list(INTERNAL_PREFIXES.keys())}")
    
    if len(prefijo) != 2 or not prefijo.isdigit():
        raise ValueError(f"Prefijo debe ser 2 dígitos numéricos, recibido: '{prefijo}'")
    
    # CRITICAL FIX: Asegurar que existe secuencia para este prefijo (en transacción separada para evitar deadlocks)
    existing = db.execute_query(
        "SELECT 1 FROM secuencias WHERE serie = %s AND terminal_id = 0",
        (f"SKU-{prefijo}",)
    )
    if not existing:
        try:
            db.execute_write(
                "INSERT INTO secuencias (serie, terminal_id, ultimo_numero, descripcion) VALUES (%s, 0, 0, %s)",
                (f"SKU-{prefijo}", f"SKU Prefijo {prefijo} - {INTERNAL_PREFIXES[prefijo]}")
            )
        except Exception as e:
            # Si falla por duplicado (otra transacción lo creó), continuar
            error_str = str(e).lower()
            if 'duplicate' not in error_str and 'unique' not in error_str:
                raise
    
    # CRITICAL FIX: Incremento atómico con UPDATE ... RETURNING (una sola query atómica)
    # Esto previene condiciones de carrera entre UPDATE y SELECT
    result = db.execute_query(
        """UPDATE secuencias 
           SET ultimo_numero = ultimo_numero + 1 
           WHERE serie = %s AND terminal_id = 0
           RETURNING ultimo_numero""",
        (f"SKU-{prefijo}",)
    )
    
    if not result or not result[0]:
        # Fallback: Si UPDATE no retornó resultado, intentar leer directamente
        logger.warning(f"UPDATE ... RETURNING no retornó resultado para SKU-{prefijo}, usando fallback")
        fallback_result = db.execute_query(
            "SELECT ultimo_numero FROM secuencias WHERE serie = %s AND terminal_id = 0",
            (f"SKU-{prefijo}",)
        )
        if fallback_result:
            numero = fallback_result[0]['ultimo_numero'] or 0
        else:
            numero = 0
    else:
        numero = result[0]['ultimo_numero']
    
    # Generar SKU con el número obtenido
    # Formato: prefijo (2) + número (10 dígitos) = 12 dígitos base
    codigo_base = f"{prefijo}{numero:010d}"
    nuevo_sku = calcular_checksum_ean13(codigo_base)
    
    # CRITICAL FIX: Verificación de unicidad con reintento si hay conflicto
    # Si el SKU ya existe (muy raro pero posible), incrementar secuencia y reintentar
    max_intentos = 10
    intentos = 0
    
    while intentos < max_intentos:
        existe = db.execute_query("SELECT 1 FROM products WHERE sku = %s", (nuevo_sku,))
        if not existe:
            break
        
        logger.warning(f"SKU {nuevo_sku} ya existe (colisión), incrementando secuencia...")
        # Incrementar secuencia nuevamente
        result = db.execute_query(
            """UPDATE secuencias 
               SET ultimo_numero = ultimo_numero + 1 
               WHERE serie = %s AND terminal_id = 0
               RETURNING ultimo_numero""",
            (f"SKU-{prefijo}",)
        )
        if result and result[0]:
            numero = result[0]['ultimo_numero']
            codigo_base = f"{prefijo}{numero:010d}"
            nuevo_sku = calcular_checksum_ean13(codigo_base)
        else:
            # Fallback: incrementar manualmente
            numero += 1
            codigo_base = f"{prefijo}{numero:010d}"
            nuevo_sku = calcular_checksum_ean13(codigo_base)
        
        intentos += 1
    
    if intentos >= max_intentos:
        raise RuntimeError(f"No se pudo generar SKU único después de {max_intentos} intentos para prefijo {prefijo}")
    
    logger.info(f"✓ SKU generado: {nuevo_sku} (Prefijo: {prefijo} - {INTERNAL_PREFIXES[prefijo]}, Número: {numero})")
    return nuevo_sku

def generar_sku_peso_precio(producto_id: str, precio_o_peso: float) -> str:
    """
    Genera un código EAN-13 con prefijo 29 para productos pesables.
    
    🏋️ MODO BÁSCULA - Precio/Peso Embebido
    
    Estructura: 29 + ID_Producto (5 dígitos) + Precio/Peso (5 dígitos) + Check
    
    Ejemplo:
    - Producto ID: 12345
    - Precio: $49.90
    - Código: 29 12345 04990 [check]
    
    NOTA: Implementación stub - requiere integración con báscula para producción.
    
    Args:
        producto_id: ID del producto (máx 5 dígitos)
        precio_o_peso: Precio en pesos o peso en gramos (máx 999.99)
        
    Returns:
        String de 13 dígitos con checksum EAN-13 válido
    """
    # Validar rangos
    id_num = int(producto_id)
    if id_num > 99999:
        raise ValueError("ID de producto para báscula debe ser máximo 5 dígitos (99999)")
    
    # Convertir precio/peso a entero (sin decimales, multiplicado por 100)
    precio_int = int(precio_o_peso * 100)
    if precio_int > 99999:
        raise ValueError("Precio/peso máximo: 999.99")
    
    # Construir código base
    codigo_base = f"29{id_num:05d}{precio_int:05d}"
    
    # Calcular checksum
    return calcular_checksum_ean13(codigo_base)

def get_prefijos_disponibles() -> List[Dict[str, str]]:
    """
    Retorna lista de prefijos disponibles para la UI.
    
    Returns:
        Lista de diccionarios con {'codigo': '20', 'descripcion': 'Abarrotes / General'}
    """
    return [
        {'codigo': codigo, 'descripcion': descripcion}
        for codigo, descripcion in INTERNAL_PREFIXES.items()
        if codigo != '29'  # Excluir prefijo especial de la lista general
    ]

def es_sku_interno(sku: str) -> bool:
    """
    Determina si un SKU es interno (generado por el sistema) o externo.
    
    Args:
        sku: Código a verificar
        
    Returns:
        True si el SKU tiene un prefijo interno, False si es externo
    """
    if not sku or len(sku) < 2:
        return False
    
    prefijo = sku[:2]
    return prefijo in INTERNAL_PREFIXES

# ============================================================================
# TESTING UTILITIES (Para desarrollo)
# ============================================================================

def _test_checksum():
    """Test unitario del cálculo de checksum."""
    # Códigos de prueba con checksums válidos
    test_casos = [
        ("7501052913544", True),   # Coca-Cola (checksum correcto es 4)
        ("7501052913549", False),  # Checksum incorrecto
        ("2000000000018", True),   # Nuestro formato interno
        ("7506195160046", True),   # Sabritas
    ]
    
    print("Validando códigos EAN-13:")
    for codigo, esperado in test_casos:
        resultado = validar_ean13(codigo)
        estado = "✓" if resultado == esperado else "✗"
        status_texto = 'VÁLIDO' if resultado else 'INVÁLIDO'
        print(f"{estado} {codigo}: {status_texto}")

if __name__ == "__main__":
    # Ejecutar tests si se corre directamente
    print("=== IDENTITY V2: SKU Generator Tests ===\n")
    _test_checksum()
    
    print("\n=== Prefijos Disponibles ===")
    for p in get_prefijos_disponibles():
        print(f"  {p['codigo']}: {p['descripcion']}")

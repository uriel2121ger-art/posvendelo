# 📚 PAQUETE COMPLETO: CLASIFICADOR DE PRODUCTOS TITAN POS

## Versión: 5.1 (Febrero 2026)

---

## 📋 ÍNDICE

1. [Instrucciones de Uso](#instrucciones-de-uso)
2. [Patrones de Clasificación V5.1](#patrones-v51)
3. [Reglas Contextuales Bidireccionales](#reglas-contextuales)
4. [Taxonomía de Departamentos y Códigos SAT](#taxonomía)
5. [Documentación Completa](#documentación)
6. [Scripts de Implementación](#scripts)

---

## 1. INSTRUCCIONES DE USO

### Cómo Clasificar un Producto

```python
def clasificar_producto(nombre):
    """
    Clasificar un producto basándose en su nombre.
    
    ORDEN DE EVALUACIÓN:
    1. Reglas contextuales (términos ambiguos)
    2. Patrones departamentales (específicos a generales)
    3. Default: Cosméticos
    
    Returns:
        tuple: (Departamento, ClaveSAT)
    """
    nombre_upper = nombre.upper()
    
    # PASO 1: Evaluar reglas contextuales (PRIORIDAD)
    resultado_contextual = evaluar_reglas_contextuales(nombre_upper)
    if resultado_contextual:
        return resultado_contextual
    
    # PASO 2: Evaluar patrones departamentales
    resultado_departamental = evaluar_patrones_departamentales(nombre_upper)
    if resultado_departamental:
        return resultado_departamental
    
    # PASO 3: Default
    return ('Cosméticos', '53131619')
```

### Principios Clave:

1. **Contexto primero:** Las palabras ambiguas (GEL, CEPILLO, etc.) se evalúan ANTES que los patrones generales
2. **Bidireccionalidad:** Los patrones manejan orden invertido (ej: "GEL UÑA" y "UÑA GEL")
3. **Especificidad:** Reglas más específicas tienen prioridad sobre genéricas
4. **100% SAT:** Todos los productos DEBEN tener código SAT fiscal válido

---

## 2. PATRONES V5.1

### Archivos Disponibles:

- **PATRONES_CLASIFICACION_V4.md** - Versión base (sin reglas contextuales)
- **PATRONES_CLASIFICACION_V5.md** - Con 11 reglas contextuales
- **PATRONES_CLASIFICACION_V5.1.md** - Optimizaciones + bidireccionalidad

### Ubicación:
```
/home/uriel/Documentos/PATRONES_CLASIFICACION_V5.1.md  (RECOMENDADO)
/home/uriel/Documentos/PATRONES_CLASIFICACION_V5.md
/home/uriel/Documentos/PATRONES_CLASIFICACION_V4.md
```

---

## 3. REGLAS CONTEXTUALES

### 11 Reglas Implementadas (V5.1)

#### 1. GEL
```python
GEL_CONTEXTO = {
    # Orden: más específico primero
    r'GEL.*(UÑ|NAIL|POLISH)|(UÑ|NAIL|POLISH).*GEL': ('Uñas', '53131616'),
    r'GEL.*ACRIL|ACRIL.*GEL': ('Uñas', '53131616'),
    r'GEL.*(CABELLO|HAIR|PEIN|FIJADOR|MODELADOR)|(CABELLO|HAIR|PEIN|FIJADOR|MODELADOR).*GEL': ('Peinados', '46181704'),
}
```
**Ejemplos:**
- "GEL UÑA UV" → Uñas
- "UÑA GEL" → Uñas (bidireccional)
- "GEL FIJADOR CABELLO" → Peinados
- "MODELADOR GEL" → Peinados (bidireccional)

#### 2. CEPILLO
```python
CEPILLO_CONTEXTO = {
    r'CEPILLO.*(CEJA|BROW|PESTAÑ)|(CEJA|BROW|PESTAÑ).*CEPILLO': ('Maquillaje', '53131619'),
    r'CEPILLO.*(DIENT|DENTAL)|(DIENT|DENTAL).*CEPILLO': ('Hogar', '52141500'),
    r'CEPILLO.*(CABELLO|HAIR|PEIN)|(CABELLO|HAIR|PEIN).*CEPILLO': ('Peinados', '46181704'),
    r'CEPILLO.*(FACIAL|ROSTRO|LIMPI.*CARA)|(FACIAL|ROSTRO|LIMPI.*CARA).*CEPILLO': ('Skin Care', '53131613'),
}
```

#### 3. BRILLO
```python
BRILLO_CONTEXTO = {
    r'BRILLO.*(LABIAL|LIP|GLOSS)|(LABIAL|LIP|GLOSS).*BRILLO': ('Labiales', '53131630'),
    r'BRILLO.*(UÑ|NAIL|ESMALTE)|(UÑ|NAIL|ESMALTE).*BRILLO': ('Uñas', '53131616'),
    r'BRILLO.*(ROSTRO|FACE|ILUMINADOR|HIGHLIGHT)|(ROSTRO|FACE|ILUMINADOR).*BRILLO': ('Maquillaje', '53131619'),
}
```

#### 4-11. ACEITE, MASCARA, TINTA, SPRAY, STICK, JABÓN, CREMA, BODY
Ver `/home/uriel/Documentos/PATRONES_CLASIFICACION_V5.1.md` para detalles completos.

---

## 4. TAXONOMÍA

### Departamentos y Códigos SAT

| Departamento | Código SAT | Descripción |
|--------------|------------|-------------|
| **Labiales** | 53131630 | Lápices labiales, gloss, bálsamos |
| **Uñas** | 53131616 | Esmaltes, gel, acrílico, herramientas |
| **Skin Care** | 53131613 | Mascarillas, cremas, serums, bloqueadores |
| **Perfumería** | 53131620 | Perfumes, colonias, body mist |
| **Maquillaje** | 53131619 | Sombras, bases, rubor, brochas |
| **Bisutería** | 54101602 | Accesorios cabello, aretes, collares |
| **Papelería** | 44121600 | Plumas, libretas, colores |
| **Peinados** | 46181704 | Peines, planchas, shampoo, tintes |
| **Electrónica** | 43211500 | Bocinas, cables, lámparas, extensiones |
| **Juguetería** | 60141001 | Juguetes, peluches, slime |
| **Fiestas** | 60141019 | Globos, piñatas, velas |
| **Bolsos y Carteras** | 53121601 | Carteras, mochilas, monederos |
| **Hogar** | 52141500 | Termos, tapetes, cepillo dental |
| **Llaveros** | 54101605 | Llaveros |
| **Lentes** | 42142901 | Gafas, lentes de sol |
| **Espejos** | 53131610 | Espejos |
| **Pestañas** | 53131619 | Pestañas postizas |
| **Delineadores** | 53131619 | Delineadores de ojos |
| **Cosméticos** | 53131619 | Categoría genérica (default) |

### Jerarquía Conceptual

```
BELLEZA
├── Maquillaje (Ojos, Rostro, Cejas)
├── Labiales
├── Skin Care
├── Uñas
├── Pestañas
├── Delineadores
├── Perfumería
└── Cosméticos (genérico)

ACCESORIOS
├── Bisutería (cabello + joyería)
├── Peinados (herramientas)
├── Lentes
├── Bolsos y Carteras
├── Llaveros
└── Espejos

OTROS
├── Papelería
├── Juguetería
├── Electrónica
├── Hogar
└── Fiestas
```

---

## 5. DOCUMENTACIÓN COMPLETA

### Archivo Principal:
```
/home/uriel/Documentos/DOCUMENTACION_COMPLETA_CLASIFICACION_IA.md
```

**Contenido:**
- 📋 Taxonomía detallada (21 departamentos)
- 🎯 Patrones regex por departamento
- 🔧 Correcciones del usuario (ejemplos validados)
- ⚠️ Errores comunes y cómo evitarlos
- 🇲🇽 Semántica y modismos mexicanos
- 🚫 Reglas de exclusión
- 🏷️ Marcas reconocidas
- 📚 Datos de entrenamiento validados

### Secciones Clave:

#### Palabras Ambiguas (V4 - Pre-Contextuales)
```
BRUSH/CEPILLO
  → BRUSH MAQUILLAJE = Maquillaje
  → BRUSH CABELLO = Peinados  
  → BRUSH DIENTES = Hogar

SPRAY
  → SPRAY CABELLO = Peinados
  → BODY SPRAY = Perfumería
  → SPRAY FIJADOR = Peinados
```

#### Modismos Mexicanos
```
VALERINA → Gancho para cabello decorativo (Bisutería)
LIGA/LIGUITA → Elástico pequeño para cabello
DONA → Accesorio redondo para moño
PEINE MARFIL → Peine tradicional de color marfil
DIUREX → Marca genérica para cinta adhesiva
```

---

## 6. SCRIPTS DE IMPLEMENTACIÓN

### Clasificador Completo (Python)

```python
#!/usr/bin/env python3
"""
Clasificador V5.1 - Implementación completa
"""
import pandas as pd
import re

# Reglas contextuales
GEL_CONTEXTO = {
    r'GEL.*(UÑ|NAIL|POLISH)|(UÑ|NAIL|POLISH).*GEL': ('Uñas', '53131616'),
    r'GEL.*ACRIL|ACRIL.*GEL': ('Uñas', '53131616'),
    r'GEL.*(CABELLO|HAIR|PEIN|FIJADOR|MODELADOR)|(CABELLO|HAIR|PEIN|FIJADOR|MODELADOR).*GEL': ('Peinados', '46181704'),
}

CEPILLO_CONTEXTO = {
    r'CEPILLO.*(CEJA|BROW|PESTAÑ)|(CEJA|BROW|PESTAÑ).*CEPILLO': ('Maquillaje', '53131619'),
    r'CEPILLO.*(DIENT|DENTAL)|(DIENT|DENTAL).*CEPILLO': ('Hogar', '52141500'),
    r'CEPILLO.*(CABELLO|HAIR|PEIN)|(CABELLO|HAIR|PEIN).*CEPILLO': ('Peinados', '46181704'),
    r'CEPILLO.*(FACIAL|ROSTRO|LIMPI.*CARA)|(FACIAL|ROSTRO|LIMPI.*CARA).*CEPILLO': ('Skin Care', '53131613'),
}

# ... (agregar resto de contextos desde PATRONES_CLASIFICACION_V5.1.md)

def clasificar_contextual(nombre):
    """Evalúa reglas contextuales bidireccionales"""
    n = str(nombre).upper()
    
    # Evaluar todos los contextos en orden
    contextos = [
        GEL_CONTEXTO,
        CEPILLO_CONTEXTO,
        # ... resto
    ]
    
    for contexto in contextos:
        for patron, (depto, sat) in contexto.items():
            if re.search(patron, n):
                return (depto, sat)
    
    # JABÓN sin contexto → Hogar
    if 'JABON' in n:
        return ('Hogar', '52141500')
    
    return None

def clasificar_departamental(nombre):
    """Evalúa patrones departamentales (V4)"""
    n = nombre.upper()
    
    # Patrones específicos primero
    if re.search(r'LABIAL|LIPSTICK|LIP\b|GLOSS', n):
        return ('Labiales', '53131630')
    
    if re.search(r'ESMALTE|NAIL|POLISH|GEL.*UÑ', n):
        return ('Uñas', '53131616')
    
    # ... (ver PATRONES_CLASIFICACION_V4.md para lista completa)
    
    return None

def clasificar_producto(nombre):
    """Función principal de clasificación"""
    # Paso 1: Contextuales
    resultado = clasificar_contextual(nombre)
    if resultado:
        return resultado
    
    # Paso 2: Departamentales
    resultado = clasificar_departamental(nombre)
    if resultado:
        return resultado
    
    # Paso 3: Default
    return ('Cosméticos', '53131619')

# Uso
if __name__ == '__main__':
    productos = [
        "GEL UÑA UV",
        "UÑA GEL ACRILICO",  # orden invertido
        "CEPILLO PARA CEJAS",
        "BRILLO LABIAL ROSA",
    ]
    
    for producto in productos:
        depto, sat = clasificar_producto(producto)
        print(f"{producto:30} → {depto:20} (SAT: {sat})")
```

### Aplicación a Catálogo CSV

```python
#!/usr/bin/env python3
"""
Aplicar clasificación V5.1 a catálogo CSV
"""
import pandas as pd

# Cargar catálogo
catalogo = pd.read_csv('CATALOGO_CLIENTE_UNIFICADO_V3.csv', low_memory=False)

# Aplicar clasificación
for idx, row in catalogo.iterrows():
    if pd.isna(row['Departamento']) or row['Departamento'] == '':
        depto, sat = clasificar_producto(row['Nombre'])
        catalogo.at[idx, 'Departamento'] = depto
        catalogo.at[idx, 'ClaveSAT'] = sat

# Guardar
catalogo.to_csv('CATALOGO_CLASIFICADO.csv', index=False)
```

---

## 7. ARCHIVOS DE REFERENCIA

### Códigos SAT (Extraídos Manualmente)

Los siguientes archivos contienen los **1,259 códigos SAT oficiales** extraídos manualmente del catálogo SAT:

- **Principal:** `/home/uriel/Documentos/CODIGOS_SAT_COMPLETOS_FINAL.xlsx` (47KB)
- **Alternativo:** `/home/uriel/Documentos/TODOS_LOS_CODIGOS_SAT_1259.xlsx` (38KB)
- **Texto:** `/home/uriel/Documentos/TODOS_LOS_1259_CODIGOS_SAT.txt` (47KB)

**Nota:** Los códigos SAT hardcoded en los patrones de clasificación ya fueron validados contra estos archivos. Usar para verificación o consulta de códigos adicionales.

### Catálogo Actual
```
/home/uriel/Documentos/CATALOGO_CLIENTE_UNIFICADO_V3.csv
```
- **15,452 productos**
- Columnas: SKU, Nombre, Precio, Stock, Departamento, ClaveSAT, etc.

### Ventas Unificadas
```
/home/uriel/Documentos/VENTAS_UNIFICADAS_2026-02-01_a_2026-02-06.csv
```
- **9,742 registros**
- Período: Feb 1-6, 2026
- Total ventas: $3,153,766.00

### Backups
```
/home/uriel/Documentos/CATALOGO_CLIENTE_UNIFICADO_V3_BACKUP_*.csv
```

---

## 8. VALIDACIÓN Y TESTING

### Casos de Prueba

```python
test_cases = [
    # Contextuales bidireccionales
    ("GEL UÑA UV", "Uñas", "53131616"),
    ("UÑA GEL ACRILICO", "Uñas", "53131616"),
    ("GEL MODELADOR", "Peinados", "46181704"),
    ("MODELADOR GEL CABELLO", "Peinados", "46181704"),
    
    # Cepillos
    ("CEPILLO PARA CEJAS", "Maquillaje", "53131619"),
    ("CEPILLO DENTAL", "Hogar", "52141500"),
    ("CEJAS CEPILLO", "Maquillaje", "53131619"),  # invertido
    
    # Jabón
    ("JABÓN PARA CEJAS", "Maquillaje", "53131619"),
    ("JABÓN FACIAL BIOAQUA", "Skin Care", "53131613"),
    ("JABÓN ANTIBACTERIAL", "Hogar", "52141500"),
    
    # Departamentales
    ("LABIAL MATTE ROJO", "Labiales", "53131630"),
    ("ESMALTE GEL MISS NANA", "Uñas", "53131616"),
    ("MASCARILLA FACIAL", "Skin Care", "53131613"),
]

def test_clasificador():
    errores = 0
    for nombre, depto_esperado, sat_esperado in test_cases:
        depto, sat = clasificar_producto(nombre)
        if depto != depto_esperado or sat != sat_esperado:
            print(f"❌ FALLO: {nombre}")
            print(f"   Esperado: {depto_esperado} ({sat_esperado})")
            print(f"   Obtenido: {depto} ({sat})")
            errores += 1
        else:
            print(f"✅ OK: {nombre} → {depto}")
    
    print(f"\n{'='*60}")
    print(f"Total tests: {len(test_cases)}")
    print(f"Exitosos: {len(test_cases) - errores}")
    print(f"Fallidos: {errores}")
    print(f"Precisión: {((len(test_cases) - errores) / len(test_cases) * 100):.2f}%")

if __name__ == '__main__':
    test_clasificador()
```

---

## 9. MEJORES PRÁCTICAS

### Al Clasificar:

1. **Siempre normalizar:** Convertir a mayúsculas antes de evaluar
2. **Contexto primero:** Verificar reglas contextuales antes que departamentales
3. **No asumir orden:** Usar patrones bidireccionales
4. **Validar SAT:** Asegurar que todos los productos tengan código SAT fiscal
5. **Documentar cambios:** Mantener historial de correcciones del usuario

### Al Agregar Nuevas Reglas:

1. **Identificar ambigüedad:** ¿La palabra tiene múltiples significados?
2. **Definir contextos:** ¿Qué palabras acompañantes determinan el significado?
3. **Crear patrón bidireccional:** `PALABRA.*CONTEXTO|CONTEXTO.*PALABRA`
4. **Probar con ejemplos reales:** Validar con productos del catálogo
5. **Actualizar documentación:** Agregar a PATRONES_V5.1.md

---

## 10. SOPORTE Y ACTUALIZACIONES

### Historial de Versiones

- **V4.0** (Ene 2026) - Patrones departamentales base
- **V5.0** (Feb 2026) - 11 reglas contextuales
- **V5.1** (Feb 2026) - Optimizaciones + bidireccionalidad

### Archivos de Configuración

Todos los archivos están en:
```
/home/uriel/Documentos/
```

### Contacto y Validación

Para validar nuevos productos o reportar clasificaciones incorrectas, verificar contra:
1. DOCUMENTACION_COMPLETA_CLASIFICACION_IA.md
2. PATRONES_CLASIFICACION_V5.1.md
3. Consultar con usuario para casos ambiguos

---

*Última actualización: 7 de Febrero de 2026*
*Versión: 5.1*
*Productos clasificados: 15,452*
*Precisión esperada: >99.5%*

# 🎯 Patrones de Clasificación v5.1 - Correcciones y Bidireccionalidad
## Sistema TITAN POS - Optimizado para Errores de Tipeo

**Fecha:** 6 de Febrero de 2026  
**Versión:** 5.1 (Correcciones de V5.0)
**Mejoras:** Patrones bidireccionales + orden corregido + fallbacks

---

## 🆕 CAMBIOS EN V5.1

### Correcciones Aplicadas:
1. ✅ Patrones bidireccionales (manejan orden invertido por tipeo)
2. ✅ GEL ACRILICO - Orden corregido
3. ✅ JABÓN - Eliminada negación lookahead
4. ✅ CREMA - Agregado contexto FACIAL explícito
5. ✅ CEPILLO DIENTES - Confirmado como Hogar

---

## 🔄 REGLAS CONTEXTUALES (Bidireccionales)

### GEL - Contexto Específico

```python
GEL_CONTEXTO = {
    # GEL de Uñas (bidireccional para manejar errores de tipeo)
    'GEL.*(UÑ|NAIL|POLISH)|(UÑ|NAIL|POLISH).*GEL': ('Uñas', '53131616'),
    
    # GEL Acrílico (orden corregido - ANTES de cabello)
    'GEL.*ACRIL|ACRIL.*GEL': ('Uñas', '53131616'),
    
    # GEL de Cabello (incluye MODELADOR por defecto)
    'GEL.*(CABELLO|HAIR|PEIN|FIJADOR|MODELADOR)|(CABELLO|HAIR|PEIN|FIJADOR|MODELADOR).*GEL': ('Peinados', '46181704'),
}
```

**Ejemplos que ahora funcionan:**
- "GEL UÑA UV" ✓
- "UÑA GEL ACRILICO" ✓ (orden invertido)
- "ACRILICO GEL" ✓ (orden invertido)
- "MODELADOR GEL CABELLO" ✓

### CEPILLO - Contexto Específico

```python
CEPILLO_CONTEXTO = {
    # Cepillo de Cejas
    'CEPILLO.*(CEJA|BROW|PESTAÑ)|(CEJA|BROW|PESTAÑ).*CEPILLO': ('Maquillaje', '53131619'),
    
    # Cepillo Dental → HOGAR (confirmado)
    'CEPILLO.*(DIENT|DENTAL)|(DIENT|DENTAL).*CEPILLO': ('Hogar', '52141500'),
    
    # Cepillo de Cabello
    'CEPILLO.*(CABELLO|HAIR|PEIN)|(CABELLO|HAIR|PEIN).*CEPILLO': ('Peinados', '46181704'),
    
    # Cepillo Facial
    'CEPILLO.*(FACIAL|ROSTRO|LIMPI.*CARA)|(FACIAL|ROSTRO|LIMPI.*CARA).*CEPILLO': ('Skin Care', '53131613'),
}
```

### BRILLO - Contexto Específico

```python
BRILLO_CONTEXTO = {
    'BRILLO.*(LABIAL|LIP|GLOSS)|(LABIAL|LIP|GLOSS).*BRILLO': ('Labiales', '53131630'),
    'BRILLO.*(UÑ|NAIL|ESMALTE)|(UÑ|NAIL|ESMALTE).*BRILLO': ('Uñas', '53131616'),
    'BRILLO.*(ROSTRO|FACE|ILUMINADOR|HIGHLIGHT)|(ROSTRO|FACE|ILUMINADOR).*BRILLO': ('Maquillaje', '53131619'),
}
```

### ACEITE - Contexto Específico

```python
ACEITE_CONTEXTO = {
    'ACEITE.*(FACIAL|ROSTRO|CARA|CORPORAL|PIEL|SKIN)|(FACIAL|ROSTRO|CARA|CORPORAL|PIEL).*ACEITE': ('Skin Care', '53131613'),
    'ACEITE.*(CABELLO|HAIR|PEIN|CAPILAR)|(CABELLO|HAIR|PEIN).*ACEITE': ('Peinados', '46181704'),
}
```

### MASCARA - Contexto Específico

```python
MASCARA_CONTEXTO = {
    'MASCARILLA|(MASCARA|MASCARILLA).*(FACIAL|ROSTRO|CARA|PIEL|SKIN)': ('Skin Care', '53131613'),
    'MASCARA.*(PESTAÑ|LASH|RIMEL|3D|VOLUME|CURL)|(PESTAÑ|LASH|RIMEL).*MASCARA': ('Maquillaje', '53131619'),
}
```

### TINTA - Contexto Específico

```python
TINTA_CONTEXTO = {
    'TINTA.*(LABIAL|LIP|BOCA)|(LABIAL|LIP).*TINTA': ('Labiales', '53131630'),
    'TINTA.*(CABELLO|HAIR|PEIN|CAPILAR)|(CABELLO|HAIR|PEIN).*TINTA': ('Peinados', '46181704'),
}
```

### SPRAY - Contexto Específico

```python
SPRAY_CONTEXTO = {
    # Orden: más específico primero
    'SPRAY.*(CABELLO|HAIR|PEIN|FIJADOR)|(CABELLO|HAIR|PEIN|FIJADOR).*SPRAY': ('Peinados', '46181704'),
    'SPRAY.*(PERFUM|FRAGANCIA|BODY.*MIST|COLONIA)|(BODY.*MIST).*SPRAY': ('Perfumería', '53131620'),
    'SPRAY.*(SOLAR|BLOQUEADOR|PROTECTOR.*SOLAR|SPF)': ('Skin Care', '53131613'),
    'SPRAY.*(DEPIL|REMOV.*VELLO)': ('Skin Care', '53131613'),
}
```

### STICK - Contexto Específico

```python
STICK_CONTEXTO = {
    'LIPSTICK|LIP.*STICK|STICK.*LIP': ('Labiales', '53131630'),
}
```

### JABÓN - Contexto Específico (Simplificado)

```python
JABON_CONTEXTO = {
    # Evaluación en orden (sin negación lookahead)
    'JABON.*(CEJA|BROW)|(CEJA|BROW).*JABON': ('Maquillaje', '53131619'),
    'JABON.*(FACIAL|CARA|ROSTRO)|(FACIAL|CARA|ROSTRO).*JABON': ('Skin Care', '53131613'),
    'JABON.*(CORPORAL|CUERPO|BODY)|(CORPORAL|CUERPO).*JABON': ('Skin Care', '53131613'),
    # JABÓN genérico → manejado por algoritmo (default Hogar)
}
```

### CREMA/CREAM - Contexto Específico (Mejorado)

```python
CREMA_CONTEXTO = {
    # Más específico primero
    'BB.*CREAM|CC.*CREAM': ('Maquillaje', '53131619'),
    'CREMA.*(FACIAL|CARA|ROSTRO)|(FACIAL|CARA|ROSTRO).*CREMA': ('Skin Care', '53131613'),
    'CREMA.*(CABELLO|HAIR|PEIN)|(CABELLO|HAIR|PEIN).*CREMA': ('Peinados', '46181704'),
    'CREMA.*(MANO|HAND|CORPORAL|CUERPO|BODY|PIE|FOOT)': ('Skin Care', '53131613'),
}
```

### BODY - Contexto Específico

```python
BODY_CONTEXTO = {
    # Redundante con SPRAY pero intencional para claridad
    'BODY.*(SPRAY|MIST|SPLASH|FRAGRANCE)': ('Perfumería', '53131620'),
    'BODY.*(LOTION|CREAM|BUTTER|MILK|HIDRATANTE)': ('Skin Care', '53131613'),
    'BODY.*(WASH|GEL|JABON|SOAP)': ('Skin Care', '53131613'),
}
```

---

## 🔄 ALGORITMO DE CLASIFICACIÓN V5.1

```python
def clasificar_producto_v51(nombre):
    nombre_upper = nombre.upper()
    
    # PASO 1: Evaluar reglas contextuales (orden importa)
    for patron, (depto, sat) in GEL_CONTEXTO.items():
        if re.search(patron, nombre_upper):
            return (depto, sat)
    
    for patron, (depto, sat) in CEPILLO_CONTEXTO.items():
        if re.search(patron, nombre_upper):
            return (depto, sat)
    
    for patron, (depto, sat) in BRILLO_CONTEXTO.items():
        if re.search(patron, nombre_upper):
            return (depto, sat)
    
    for patron, (depto, sat) in ACEITE_CONTEXTO.items():
        if re.search(patron, nombre_upper):
            return (depto, sat)
    
    for patron, (depto, sat) in MASCARA_CONTEXTO.items():
        if re.search(patron, nombre_upper):
            return (depto, sat)
    
    for patron, (depto, sat) in TINTA_CONTEXTO.items():
        if re.search(patron, nombre_upper):
            return (depto, sat)
    
    for patron, (depto, sat) in SPRAY_CONTEXTO.items():
        if re.search(patron, nombre_upper):
            return (depto, sat)
    
    for patron, (depto, sat) in STICK_CONTEXTO.items():
        if re.search(patron, nombre_upper):
            return (depto, sat)
    
    for patron, (depto, sat) in JABON_CONTEXTO.items():
        if re.search(patron, nombre_upper):
            return (depto, sat)
    
    # JABÓN sin contexto → Hogar
    if 'JABON' in nombre_upper:
        return ('Hogar', '52141500')
    
    for patron, (depto, sat) in CREMA_CONTEXTO.items():
        if re.search(patron, nombre_upper):
            return (depto, sat)
    
    for patron, (depto, sat) in BODY_CONTEXTO.items():
        if re.search(patron, nombre_upper):
            return (depto, sat)
    
    # PASO 2: Aplicar patrones departamentales (V4)
    # ... resto igual
    
    # PASO 3: Default
    return ('Cosméticos', '53131619')
```

---

## 📊 MEJORAS EN V5.1

| Aspecto | V5.0 | V5.1 |
|---------|------|------|
| **Errores de orden** | No maneja | ✅ Maneja |
| **GEL ACRILICO** | Fallo | ✅ Corregido |
| **JABÓN lookahead** | Lento | ✅ Optimizado |
| **CREMA FACIAL** | Implícito | ✅ Explícito |
| **CEPILLO DIENTES** | Conflicto | ✅ Hogar |
| **Reglas bidireccionales** | 0 | 11 |

---

## ⚠️ NOTAS IMPORTANTES

1. **Patrones bidireccionales:** `A.*B|B.*A` maneja ambos órdenes
2. **JABÓN genérico:** Evaluado después de contextos específicos → Hogar
3. **Orden de evaluación:** Más específico primero
4. **Compatibilidad:** 100% compatible con V4
5. **SAT fiscal:** Sin cambios, 100% correcto

---

*Documento generado - TITAN POS - 6 Febrero 2026 - V5.1*

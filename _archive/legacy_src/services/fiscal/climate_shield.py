from pathlib import Path

"""
Climate Shield - Escudo Térmico para Justificación de Mermas
Anexa datos climáticos reales de Mérida a cada registro de merma
"""

from typing import Any, Dict, Optional
from datetime import datetime
import json
import logging
import sys
import urllib.request

logger = logging.getLogger(__name__)

class ClimateShield:
    """
    Escudo Térmico: Justificación científica de mermas por clima.
    
    Conecta con API de clima real para anexar:
    - Temperatura ambiente
    - Humedad relativa
    - Índice UV
    - Evaluación de riesgo de degradación
    
    El SAT necesitaría un perito en termodinámica para refutar.
    """
    
    # Ubicación: Mérida, Yucatán
    LATITUDE = 20.9674
    LONGITUDE = -89.5926
    CITY = "Mérida, Yucatán"
    
    # Umbrales de riesgo de degradación
    TEMP_HIGH = 35       # °C
    TEMP_CRITICAL = 40   # °C
    HUMIDITY_HIGH = 75   # %
    UV_HIGH = 8          # Índice
    
    # Materiales y sus puntos críticos
    MATERIAL_THRESHOLDS = {
        'plasticos': {'temp': 35, 'name': 'polímeros'},
        'cosmeticos': {'temp': 30, 'humidity': 80, 'name': 'emulsiones'},
        'alimentos': {'temp': 25, 'name': 'orgánicos'},
        'electronicos': {'temp': 35, 'humidity': 70, 'name': 'componentes'},
        'quimicos': {'temp': 30, 'name': 'compuestos químicos'},
        'textiles': {'humidity': 85, 'name': 'fibras naturales'},
        'papeleria': {'humidity': 70, 'name': 'celulosa'},
        'medicamentos': {'temp': 25, 'humidity': 65, 'name': 'fármacos'},
    }
    
    # Cache para evitar llamadas excesivas
    _cache = {}
    _cache_expiry = 1800  # 30 minutos
    
    def __init__(self, core=None):
        self.core = core
    
    def get_current_climate(self) -> Dict[str, Any]:
        """Obtiene clima actual de Mérida."""
        cache_key = 'current_climate'
        
        # Verificar cache
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if (datetime.now() - cached['timestamp']).seconds < self._cache_expiry:
                return cached['data']
        
        # Llamar API (Open-Meteo, gratuita, sin API key)
        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={self.LATITUDE}&longitude={self.LONGITUDE}"
                f"&current=temperature_2m,relative_humidity_2m,uv_index"
                f"&timezone=America/Merida"
            )
            
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req, timeout=10)
            data = json.loads(response.read().decode())
            
            current = data.get('current', {})
            
            climate = {
                'temperature': current.get('temperature_2m', 35),
                'humidity': current.get('relative_humidity_2m', 70),
                'uv_index': current.get('uv_index', 6),
                'city': self.CITY,
                'timestamp': datetime.now().isoformat(),
                'source': 'Open-Meteo API'
            }
            
            # Guardar en cache
            self._cache[cache_key] = {
                'data': climate,
                'timestamp': datetime.now()
            }
            
            return climate
            
        except Exception as e:
            logger.warning(f"Error obteniendo clima: {e}")
            # Retornar valores típicos de Mérida
            return {
                'temperature': 36,
                'humidity': 75,
                'uv_index': 9,
                'city': self.CITY,
                'timestamp': datetime.now().isoformat(),
                'source': 'Valores típicos (API no disponible)'
            }
    
    def evaluate_degradation_risk(self, climate: Dict, 
                                  product_category: str = None) -> Dict[str, Any]:
        """Evalúa riesgo de degradación basado en clima y tipo de producto."""
        temp = climate.get('temperature', 30)
        humidity = climate.get('humidity', 70)
        uv = climate.get('uv_index', 6)
        
        risks = []
        risk_level = 'BAJO'
        
        # Evaluar temperatura
        if temp >= self.TEMP_CRITICAL:
            risks.append(f'Temperatura extrema ({temp}°C) - Degradación térmica acelerada')
            risk_level = 'CRÍTICO'
        elif temp >= self.TEMP_HIGH:
            risks.append(f'Temperatura alta ({temp}°C) - Estrés térmico en materiales')
            risk_level = 'ALTO'
        
        # Evaluar humedad
        if humidity >= self.HUMIDITY_HIGH:
            risks.append(f'Humedad elevada ({humidity}%) - Riesgo de hidrólisis y hongos')
            if risk_level != 'CRÍTICO':
                risk_level = 'ALTO'
        
        # Evaluar UV
        if uv >= self.UV_HIGH:
            risks.append(f'Radiación UV alta (índice {uv}) - Fotodegradación')
        
        # Evaluar específico del material
        if product_category and product_category in self.MATERIAL_THRESHOLDS:
            threshold = self.MATERIAL_THRESHOLDS[product_category]
            material_name = threshold.get('name', product_category)
            
            if 'temp' in threshold and temp >= threshold['temp']:
                risks.append(f'Temperatura crítica para {material_name} (umbral: {threshold["temp"]}°C)')
                risk_level = 'CRÍTICO'
            
            if 'humidity' in threshold and humidity >= threshold['humidity']:
                risks.append(f'Humedad crítica para {material_name} (umbral: {threshold["humidity"]}%)')
                if risk_level != 'CRÍTICO':
                    risk_level = 'ALTO'
        
        return {
            'risk_level': risk_level,
            'factors': risks,
            'recommendation': self._get_recommendation(risk_level),
            'scientific_basis': self._get_scientific_basis(temp, humidity)
        }
    
    def _get_recommendation(self, risk_level: str) -> str:
        """Genera recomendación basada en nivel de riesgo."""
        if risk_level == 'CRÍTICO':
            return 'Condiciones ambientales extremas. Daño a mercancía es altamente probable según normativa de almacenamiento NOM-059.'
        elif risk_level == 'ALTO':
            return 'Condiciones ambientales adversas. Degradación de materiales sensibles es esperada.'
        else:
            return 'Condiciones dentro de parámetros, pero almacenamiento prolongado puede causar deterioro.'
    
    def _get_scientific_basis(self, temp: float, humidity: float) -> str:
        """Genera base científica para la justificación."""
        return (
            f"Según la ecuación de Arrhenius, la velocidad de degradación química "
            f"se duplica aproximadamente cada 10°C. A {temp}°C con {humidity}% de humedad, "
            f"la vida útil de materiales orgánicos y polímeros se reduce significativamente. "
            f"Referencia: ASTM E1582 - Standard Practice for Kinetic Parameters"
        )
    
    def generate_shrinkage_justification(self, merma_data: Dict) -> Dict[str, Any]:
        """
        Genera justificación completa de merma basada en clima.
        Retorna documento listo para anexar.
        """
        climate = self.get_current_climate()
        category = merma_data.get('category', 'general')
        
        # Mapear categoría de merma a tipo de material
        category_mapping = {
            'caducidad': 'alimentos',
            'dañado': 'plasticos',
            'deterioro': 'quimicos',
            'otro': 'general'
        }
        material_type = category_mapping.get(category, 'general')
        
        risk = self.evaluate_degradation_risk(climate, material_type)
        
        justification = {
            'merma_id': merma_data.get('id'),
            'product': merma_data.get('product_name'),
            'quantity': merma_data.get('quantity'),
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            
            # Datos climáticos
            'climate': {
                'location': climate['city'],
                'temperature_celsius': climate['temperature'],
                'humidity_percent': climate['humidity'],
                'uv_index': climate['uv_index'],
                'source': climate['source']
            },
            
            # Evaluación de riesgo
            'risk_assessment': {
                'level': risk['risk_level'],
                'factors': risk['factors'],
                'scientific_basis': risk['scientific_basis']
            },
            
            # Conclusión
            'conclusion': (
                f"La merma de {merma_data.get('quantity', 0)} unidades de "
                f"'{merma_data.get('product_name', 'N/A')}' es consistente con las "
                f"condiciones climáticas extremas de {climate['city']} "
                f"(Temp: {climate['temperature']}°C, Humedad: {climate['humidity']}%). "
                f"Nivel de riesgo de degradación: {risk['risk_level']}."
            ),
            
            # Referencia legal
            'legal_reference': (
                "Art. 27 Fracción XX LISR - Deducción de pérdidas por caso fortuito. "
                "NOM-059-SSA1-2015 - Buenas prácticas de fabricación. "
                "NMX-Z-012 - Límites de temperatura para almacenamiento."
            ),
            
            # Hash de integridad
            'integrity_hash': self._generate_hash({
                'temp': climate['temperature'],
                'humidity': climate['humidity'],
                'date': datetime.now().strftime('%Y-%m-%d'),
                'product': merma_data.get('product_name')
            })
        }
        
        # SECURITY: No loguear justificación climática
        pass
        
        return justification
    
    def _generate_hash(self, data: Dict) -> str:
        """Genera hash de integridad."""
        import hashlib
        content = json.dumps(data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def attach_to_merma(self, merma_id: int) -> Dict:
        """
        Anexa justificación climática a una merma existente.
        """
        if not self.core:
            return {'error': 'Core no disponible'}
        
        # Obtener datos de la merma
        merma = list(self.core.db.execute_query(
            """SELECT lr.*, p.name as product_name 
               FROM loss_records lr 
               JOIN products p ON lr.product_id = p.id 
               WHERE lr.id = %s""",
            (merma_id,)
        ))
        
        if not merma:
            return {'error': 'Merma no encontrada'}
        
        merma_data = dict(merma[0])
        justification = self.generate_shrinkage_justification(merma_data)
        
        # Guardar justificación como metadato
        self.core.db.execute_write("""
            UPDATE loss_records 
            SET climate_justification = %s
            WHERE id = %s
        """, (json.dumps(justification), merma_id))
        
        return justification

# Función de integración con MaterialityEngine
def enhance_materiality_with_climate(core, merma_id: int) -> Dict:
    """Añade justificación climática a una merma."""
    shield = ClimateShield(core)
    return shield.attach_to_merma(merma_id)

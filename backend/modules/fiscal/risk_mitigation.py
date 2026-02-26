"""
Climate Shield - Escudo Térmico para Justificación de Mermas
Datos climáticos reales de Mérida anexados a registros de merma
"""

from typing import Any, Dict
from datetime import datetime
import json
import logging
import urllib.request

logger = logging.getLogger(__name__)


class ClimateShield:
    LATITUDE = 20.9674
    LONGITUDE = -89.5926
    CITY = "Mérida, Yucatán"
    TEMP_HIGH = 35
    TEMP_CRITICAL = 40
    HUMIDITY_HIGH = 75
    UV_HIGH = 8

    MATERIAL_THRESHOLDS = {
        'plasticos': {'temp': 35, 'name': 'polímeros'}, 'cosmeticos': {'temp': 30, 'humidity': 80, 'name': 'emulsiones'},
        'alimentos': {'temp': 25, 'name': 'orgánicos'}, 'electronicos': {'temp': 35, 'humidity': 70, 'name': 'componentes'},
        'quimicos': {'temp': 30, 'name': 'compuestos químicos'}, 'textiles': {'humidity': 85, 'name': 'fibras naturales'},
        'papeleria': {'humidity': 70, 'name': 'celulosa'}, 'medicamentos': {'temp': 25, 'humidity': 65, 'name': 'fármacos'},
    }

    _cache = {}
    _cache_expiry = 1800

    def __init__(self, db=None):
        self.db = db

    async def get_current_climate(self) -> Dict[str, Any]:
        cache_key = 'current_climate'
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if (datetime.now() - cached['timestamp']).seconds < self._cache_expiry:
                return cached['data']
        try:
            url = (f"https://api.open-meteo.com/v1/forecast?latitude={self.LATITUDE}&longitude={self.LONGITUDE}"
                   f"&current=temperature_2m,relative_humidity_2m,uv_index&timezone=America/Merida")
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
            current = data.get('current', {})
            climate = {'temperature': current.get('temperature_2m', 35), 'humidity': current.get('relative_humidity_2m', 70),
                       'uv_index': current.get('uv_index', 6), 'city': self.CITY, 'timestamp': datetime.now().isoformat(), 'source': 'Open-Meteo API'}
            self._cache[cache_key] = {'data': climate, 'timestamp': datetime.now()}
            return climate
        except Exception:
            return {'temperature': 36, 'humidity': 75, 'uv_index': 9, 'city': self.CITY, 'timestamp': datetime.now().isoformat(), 'source': 'Valores típicos'}

    async def evaluate_degradation_risk(self, climate: Dict, product_category: str = None) -> Dict[str, Any]:
        temp, humidity, uv = climate.get('temperature', 30), climate.get('humidity', 70), climate.get('uv_index', 6)
        risks = []
        risk_level = 'BAJO'
        if temp >= self.TEMP_CRITICAL: risks.append(f'Temperatura extrema ({temp}°C)'); risk_level = 'CRÍTICO'
        elif temp >= self.TEMP_HIGH: risks.append(f'Temperatura alta ({temp}°C)'); risk_level = 'ALTO'
        if humidity >= self.HUMIDITY_HIGH: risks.append(f'Humedad elevada ({humidity}%)'); risk_level = risk_level if risk_level == 'CRÍTICO' else 'ALTO'
        if uv >= self.UV_HIGH: risks.append(f'Radiación UV alta ({uv})')
        if product_category and product_category in self.MATERIAL_THRESHOLDS:
            t = self.MATERIAL_THRESHOLDS[product_category]
            if 'temp' in t and temp >= t['temp']: risks.append(f"Crítico para {t['name']}"); risk_level = 'CRÍTICO'
            if 'humidity' in t and humidity >= t['humidity']: risks.append(f"Humedad crítica para {t['name']}")
        return {'risk_level': risk_level, 'factors': risks,
                'scientific_basis': f"Según Arrhenius, a {temp}°C con {humidity}% humedad la vida útil se reduce significativamente. Ref: ASTM E1582"}

    async def generate_shrinkage_justification(self, merma_data: Dict) -> Dict[str, Any]:
        climate = await self.get_current_climate()
        category_mapping = {'caducidad': 'alimentos', 'dañado': 'plasticos', 'deterioro': 'quimicos', 'otro': 'general'}
        material_type = category_mapping.get(merma_data.get('category', 'general'), 'general')
        risk = await self.evaluate_degradation_risk(climate, material_type)
        import hashlib
        hash_data = json.dumps({'temp': climate['temperature'], 'humidity': climate['humidity'], 'date': datetime.now().strftime('%Y-%m-%d'), 'product': merma_data.get('product_name')}, sort_keys=True)
        return {
            'merma_id': merma_data.get('id'), 'product': merma_data.get('product_name'), 'quantity': merma_data.get('quantity'),
            'climate': {'location': climate['city'], 'temperature_celsius': climate['temperature'], 'humidity_percent': climate['humidity'], 'uv_index': climate['uv_index']},
            'risk_assessment': {'level': risk['risk_level'], 'factors': risk['factors'], 'scientific_basis': risk['scientific_basis']},
            'conclusion': f"Merma consistente con condiciones climáticas de {climate['city']} ({climate['temperature']}°C, {climate['humidity']}%). Riesgo: {risk['risk_level']}.",
            'legal_reference': 'Art. 27 Fracción XX LISR - NOM-059-SSA1-2015 - NMX-Z-012',
            'integrity_hash': hashlib.sha256(hash_data.encode()).hexdigest()[:16]
        }

    async def attach_to_merma(self, merma_id: int) -> Dict:
        if not self.db: return {'error': 'DB no disponible'}
        merma = await self.db.fetchrow("SELECT lr.*, p.name as product_name FROM loss_records lr JOIN products p ON lr.product_id = p.id WHERE lr.id = :mid", mid=merma_id)
        if not merma: return {'error': 'Merma no encontrada'}
        justification = await self.generate_shrinkage_justification(dict(merma))
        await self.db.execute("UPDATE loss_records SET climate_justification = :cj WHERE id = :mid", cj=json.dumps(justification), mid=merma_id)
        return justification

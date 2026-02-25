"""
PAC (Proveedor Autorizado de Certificación) Connector Framework
for CFDI electronic invoicing in Mexico
"""

from typing import Any, Dict, Optional
from abc import ABC, abstractmethod
import logging

import httpx

logger = logging.getLogger(__name__)

class PACConnector(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.base_url = config.get('pac_base_url', '')
        self.user = config.get('pac_user', '')
        self.password = config.get('pac_password', '')
        self.mode = config.get('pac_mode', 'test')
        self.timeout = 30.0  # seconds
    
    @abstractmethod
    async def timbrar_cfdi(self, xml_string: str) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    async def cancelar_cfdi(self, uuid: str, motivo: str = '02', folio_sustitucion: Optional[str] = None) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    async def consultar_creditos(self) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    async def consultar_estatus(self, uuid: str) -> Dict[str, Any]:
        pass

class CustomPACConnector(PACConnector):
    async def timbrar_cfdi(self, xml_string: str) -> Dict[str, Any]:
        try:
            endpoint = f"{self.base_url}/timbrar"
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    endpoint,
                    json={'xml': xml_string},
                    auth=(self.user, self.password),
                    timeout=self.timeout,
                    headers={'Content-Type': 'application/json'}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'success': True,
                        'uuid': data.get('uuid'),
                        'xml_timbrado': data.get('xml_timbrado'),
                        'fecha_timbrado': data.get('fecha_timbrado'),
                    }
                else:
                    return {'success': False, 'error': f"HTTP {response.status_code}: {response.text}"}
        except Exception as e:
            logger.error(f"Error timbrando CFDI: {e}")
            return {'success': False, 'error': str(e)}
    
    async def cancelar_cfdi(self, uuid: str, motivo: str = '02', folio_sustitucion: Optional[str] = None) -> Dict[str, Any]:
        try:
            endpoint = f"{self.base_url}/cancelar"
            payload = {'uuid': uuid, 'motivo': motivo}
            if motivo == '01' and folio_sustitucion:
                payload['folio_sustitucion'] = folio_sustitucion
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    endpoint,
                    json=payload,
                    auth=(self.user, self.password),
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'success': True,
                        'acuse': data.get('acuse'),
                        'fecha_cancelacion': data.get('fecha_cancelacion')
                    }
                else:
                    return {'success': False, 'error': f"HTTP {response.status_code}: {response.text}"}
        except Exception as e:
            logger.error(f"Error cancelando CFDI: {e}")
            return {'success': False, 'error': str(e)}
    
    async def consultar_creditos(self) -> Dict[str, Any]:
        try:
            endpoint = f"{self.base_url}/creditos"
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    endpoint,
                    auth=(self.user, self.password),
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {'success': True, 'creditos': data.get('creditos', 0)}
                else:
                    return {'success': False, 'error': f"HTTP {response.status_code}: {response.text}"}
        except Exception as e:
            logger.error(f"Error consultando créditos: {e}")
            return {'success': False, 'error': str(e), 'creditos': 0}
    
    async def consultar_estatus(self, uuid: str) -> Dict[str, Any]:
        try:
            endpoint = f"{self.base_url}/estatus/{uuid}"
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    endpoint,
                    auth=(self.user, self.password),
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'success': True,
                        'estado': data.get('estado'),
                        'es_cancelable': data.get('es_cancelable', False)
                    }
                else:
                    return {'success': False, 'error': f"HTTP {response.status_code}: {response.text}"}
        except Exception as e:
            logger.error(f"Error consultando estatus: {e}")
            return {'success': False, 'error': str(e)}

def create_pac_connector(config: Dict[str, Any]) -> PACConnector:
    provider = config.get('pac_provider', 'custom').lower()
    if provider == 'custom':
        return CustomPACConnector(config)
    else:
        logger.warning(f"Unknown PAC provider '{provider}', using CustomPACConnector")
        return CustomPACConnector(config)

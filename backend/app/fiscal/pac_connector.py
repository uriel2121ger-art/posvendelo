"""
PAC (Proveedor Autorizado de Certificación) Connector Framework
for CFDI electronic invoicing in Mexico

This module provides base classes and implementations for connecting
to different PAC providers (Finkok, SW Sapien, Facturama, etc.)
"""

from typing import Any, Dict, Optional
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class PACConnector(ABC):
    """Abstract base class for PAC provider connectors."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize PAC connector with configuration.
        
        Args:
            config: Dictionary with PAC configuration including:
                - pac_base_url: Base URL of PAC API
                - pac_user: Username for PAC authentication
                - pac_password: Password for PAC authentication
                - pac_mode: 'test' or 'production'
        """
        self.base_url = config.get('pac_base_url', '')
        self.user = config.get('pac_user', '')
        self.password = config.get('pac_password', '')
        self.mode = config.get('pac_mode', 'test')
        self.timeout = 30  # seconds
    
    @abstractmethod
    def timbrar_cfdi(self, xml_string: str) -> Dict[str, Any]:
        """
        Send CFDI XML to PAC for timbrado (stamping).
        
        Args:
            xml_string: Complete CFDI XML string
            
        Returns:
            Dictionary with:
            - success: bool
            - uuid: str (fiscal folio UUID)
            - xml_timbrado: str (stamped XML with SAT seal)
            - fecha_timbrado: str (timestamp)
            - error: str (if failed)
        """
        pass
    
    @abstractmethod
    def cancelar_cfdi(self, uuid: str, motivo: str = '02', folio_sustitucion: Optional[str] = None) -> Dict[str, Any]:
        """
        Cancel a previously stamped CFDI.
        
        Args:
            uuid: UUID of the CFDI to cancel
            motivo: Cancellation reason code (01-04)
            folio_sustitucion: UUID of replacement CFDI (if motivo='01')
            
        Returns:
            Dictionary with:
            - success: bool
            - acuse: str (acknowledgement XML)
            - fecha_cancelacion: str
            - error: str (if failed)
        """
        pass
    
    @abstractmethod
    def consultar_creditos(self) -> Dict[str, Any]:
        """
        Check available credits/tokens from PAC.
        
        Returns:
            Dictionary with:
            - success: bool
            - creditos: int (available credits)
            - error: str (if failed)
        """
        pass
    
    @abstractmethod
    def consultar_estatus(self, uuid: str) -> Dict[str, Any]:
        """
        Query status of a CFDI.
        
        Args:
            uuid: UUID of the CFDI
            
        Returns:
            Dictionary with:
            - success: bool
            - estado: str ('vigente', 'cancelado', 'no_encontrado')
            - es_cancelable: bool
            - error: str (if failed)
        """
        pass

class CustomPACConnector(PACConnector):
    """
    Generic REST API connector for custom PAC providers.
    
    This implementation assumes a standard REST API with the following endpoints:
    - POST /timbrar - For stamping
    - POST /cancelar - For cancellation
    - GET /creditos - For checking credits
    - GET /estatus/{uuid} - For status query
    
    Adapt this class or create specific implementations for your PAC provider.
    """
    
    def timbrar_cfdi(self, xml_string: str) -> Dict[str, Any]:
        """Send CFDI to PAC for timbrado."""
        try:
            import requests
            
            endpoint = f"{self.base_url}/timbrar"
            
            response = requests.post(
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
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error timbr ando CFDI: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def cancelar_cfdi(self, uuid: str, motivo: str = '02', folio_sustitucion: Optional[str] = None) -> Dict[str, Any]:
        """Cancel CFDI."""
        try:
            import requests
            
            endpoint = f"{self.base_url}/cancelar"
            
            payload = {
                'uuid': uuid,
                'motivo': motivo
            }
            
            if motivo == '01' and folio_sustitucion:
                payload['folio_sustitucion'] = folio_sustitucion
            
            response = requests.post(
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
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error cancelando CFDI: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def consultar_creditos(self) -> Dict[str, Any]:
        """Check available credits."""
        try:
            import requests
            
            endpoint = f"{self.base_url}/creditos"
            
            response = requests.get(
                endpoint,
                auth=(self.user, self.password),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'creditos': data.get('creditos', 0)
                }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error consultando créditos: {e}")
            return {
                'success': False,
                'error': str(e),
                'creditos': 0
            }
    
    def consultar_estatus(self, uuid: str) -> Dict[str, Any]:
        """Query CFDI status."""
        try:
            import requests
            
            endpoint = f"{self.base_url}/estatus/{uuid}"
            
            response = requests.get(
                endpoint,
                auth=(self.user, self.password),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'estado': data.get('estado'),
                    'es_cancelable': data.get('es_cancelable', False)
                }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error consultando estatus: {e}")
            return {
                'success': False,
                'error': str(e)
            }

# Factory function for creating PAC connectors
def create_pac_connector(config: Dict[str, Any]) -> PACConnector:
    """
    Factory function to create appropriate PAC connector.
    
    Args:
        config: Configuration dictionary with pac_provider field
        
    Returns:
        Instance of appropriate PACConnector subclass
    """
    provider = config.get('pac_provider', 'custom').lower()
    
    if provider == 'custom':
        return CustomPACConnector(config)
    else:
        # Add specific implementations here
        # elif provider == 'finkok':
        #     return FinkokConnector(config)
        # elif provider == 'sw':
        #     return SWConnector(config)
        logger.warning(f"Unknown PAC provider '{provider}', using CustomPACConnector")
        return CustomPACConnector(config)

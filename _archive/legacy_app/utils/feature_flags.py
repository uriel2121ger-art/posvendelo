"""
🚩 Feature Flags - Control dinámico de funcionalidades
Permite activar/desactivar features sin deploy

Uso:
    from app.utils.feature_flags import is_enabled, Features
    
    if is_enabled(Features.NEW_CHECKOUT):
        use_new_checkout()
    else:
        use_old_checkout()
"""
from typing import Any, Optional
from functools import lru_cache
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("FEATURE_FLAGS")

class Features:
    """Catálogo de features disponibles."""
    
    # UI/UX
    DARK_MODE_V2 = "dark_mode_v2"
    NEW_CHECKOUT = "new_checkout_flow"
    QUICK_SALE_MODE = "quick_sale_mode"
    
    # Fiscal
    CFDI_40 = "cfdi_40_enabled"
    GLOBAL_INVOICING = "global_invoicing"
    RESICO_ALERTS = "resico_alerts"
    
    # Comunicación
    TELEGRAM_ALERTS = "telegram_alerts"
    EMAIL_RECEIPTS = "email_receipts"
    SMS_NOTIFICATIONS = "sms_notifications"
    
    # IA y Avanzado
    AI_SUGGESTIONS = "ai_product_suggestions"
    PREDICTIVE_STOCK = "predictive_stock"
    SMART_PRICING = "smart_pricing"
    
    # Beta Features
    MULTI_CURRENCY = "multi_currency"
    CRYPTO_PAYMENTS = "crypto_payments"
    BIOMETRIC_LOGIN = "biometric_login"

class FeatureFlagManager:
    """
    Manejador de Feature Flags.
    
    Soporta múltiples backends:
    1. Archivo local (default)
    2. Flagsmith (cloud)
    3. LaunchDarkly (enterprise)
    """
    
    def __init__(self):
        self._flags: dict = {}
        self._backend = "local"
        self._cloud_client = None
        self._load_local_flags()
        self._try_connect_cloud()
    
    def _get_flags_path(self) -> Path:
        """Obtiene ruta al archivo de flags."""
        return Path(__file__).parent.parent.parent / "data" / "config" / "feature_flags.json"
    
    def _load_local_flags(self):
        """Carga flags desde archivo local."""
        flags_path = self._get_flags_path()
        
        if flags_path.exists():
            try:
                with open(flags_path) as f:
                    self._flags = json.load(f)
                logger.debug(f"Loaded {len(self._flags)} feature flags")
            except Exception as e:
                logger.warning(f"Error loading flags: {e}")
                self._flags = self._get_default_flags()
        else:
            self._flags = self._get_default_flags()
            self._save_local_flags()
    
    def _save_local_flags(self):
        """Guarda flags al archivo local."""
        flags_path = self._get_flags_path()
        flags_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(flags_path, 'w') as f:
            json.dump(self._flags, f, indent=2)
    
    def _get_default_flags(self) -> dict:
        """Flags por defecto."""
        return {
            # Habilitados por defecto
            Features.DARK_MODE_V2: True,
            Features.CFDI_40: True,
            Features.GLOBAL_INVOICING: True,
            Features.RESICO_ALERTS: True,
            
            # Deshabilitados por defecto
            Features.NEW_CHECKOUT: False,
            Features.QUICK_SALE_MODE: False,
            Features.TELEGRAM_ALERTS: False,
            Features.EMAIL_RECEIPTS: False,
            Features.SMS_NOTIFICATIONS: False,
            Features.AI_SUGGESTIONS: False,
            Features.PREDICTIVE_STOCK: False,
            Features.SMART_PRICING: False,
            Features.MULTI_CURRENCY: False,
            Features.CRYPTO_PAYMENTS: False,
            Features.BIOMETRIC_LOGIN: False,
        }
    
    def _try_connect_cloud(self):
        """Intenta conectar a servicio cloud de feature flags."""
        flagsmith_key = os.getenv("FLAGSMITH_KEY")
        launchdarkly_key = os.getenv("LAUNCHDARKLY_KEY")
        
        if flagsmith_key:
            try:
                from flagsmith import Flagsmith
                self._cloud_client = Flagsmith(environment_key=flagsmith_key)
                self._backend = "flagsmith"
                logger.info("✅ Conectado a Flagsmith")
            except ImportError:
                logger.debug("Flagsmith no instalado")
            except Exception as e:
                logger.warning(f"Error conectando a Flagsmith: {e}")
        
        elif launchdarkly_key:
            try:
                import ldclient
                ldclient.set_config(ldclient.Config(launchdarkly_key))
                self._cloud_client = ldclient.get()
                self._backend = "launchdarkly"
                logger.info("✅ Conectado a LaunchDarkly")
            except ImportError:
                logger.debug("LaunchDarkly no instalado")
            except Exception as e:
                logger.warning(f"Error conectando a LaunchDarkly: {e}")
    
    def is_enabled(self, feature: str, user_id: str = None, default: bool = False) -> bool:
        """
        Verifica si una feature está habilitada.
        
        Args:
            feature: Nombre del feature flag
            user_id: ID del usuario (para targeting)
            default: Valor por defecto si no existe
        
        Returns:
            True si la feature está habilitada
        """
        # Intentar cloud primero
        if self._cloud_client:
            try:
                if self._backend == "flagsmith":
                    flags = self._cloud_client.get_environment_flags()
                    return flags.is_feature_enabled(feature)
                elif self._backend == "launchdarkly":
                    user = {"key": user_id or "anonymous"}
                    return self._cloud_client.variation(feature, user, default)
            except Exception as e:
                logger.debug(f"Cloud flag check failed: {e}")
        
        # Fallback a local
        return self._flags.get(feature, default)
    
    def get_value(self, feature: str, default: Any = None) -> Any:
        """
        Obtiene el valor de un feature flag.
        
        Útil para configuración dinámica y A/B testing.
        """
        if self._cloud_client:
            try:
                if self._backend == "flagsmith":
                    flags = self._cloud_client.get_environment_flags()
                    return flags.get_feature_value(feature) or default
            except Exception:
                pass
        
        return self._flags.get(feature, default)
    
    def set_flag(self, feature: str, enabled: bool):
        """
        Activa o desactiva un feature flag localmente.
        
        Args:
            feature: Nombre del flag
            enabled: True para activar, False para desactivar
        """
        self._flags[feature] = enabled
        self._save_local_flags()
        logger.info(f"🚩 Flag '{feature}' = {enabled}")
    
    def list_flags(self) -> dict:
        """Retorna todos los flags y sus valores."""
        return self._flags.copy()
    
    def get_backend(self) -> str:
        """Retorna el backend actual (local, flagsmith, launchdarkly)."""
        return self._backend

# Singleton instance
_manager: Optional[FeatureFlagManager] = None

def get_manager() -> FeatureFlagManager:
    """Obtiene el manejador de feature flags."""
    global _manager
    if _manager is None:
        _manager = FeatureFlagManager()
    return _manager

# Funciones de conveniencia
def is_enabled(feature: str, user_id: str = None, default: bool = False) -> bool:
    """Verifica si un feature está habilitado."""
    return get_manager().is_enabled(feature, user_id, default)

def get_value(feature: str, default: Any = None) -> Any:
    """Obtiene el valor de un feature flag."""
    return get_manager().get_value(feature, default)

def set_flag(feature: str, enabled: bool):
    """Activa o desactiva un feature flag."""
    get_manager().set_flag(feature, enabled)

def list_flags() -> dict:
    """Lista todos los flags."""
    return get_manager().list_flags()

# Decorador para features
def requires_feature(feature: str, fallback=None):
    """
    Decorador que ejecuta función solo si feature está habilitado.
    
    Uso:
        @requires_feature(Features.AI_SUGGESTIONS)
        def get_ai_suggestions(product_id):
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if is_enabled(feature):
                return func(*args, **kwargs)
            elif fallback:
                return fallback(*args, **kwargs)
            else:
                return None
        return wrapper
    return decorator

if __name__ == "__main__":
    # Test
    print("🚩 Feature Flags Test")
    print(f"Backend: {get_manager().get_backend()}")
    print("\nFlags actuales:")
    for flag, value in list_flags().items():
        status = "✅" if value else "❌"
        print(f"  {status} {flag}")

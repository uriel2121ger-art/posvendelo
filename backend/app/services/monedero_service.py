"""
Monedero Service - Business Logic for Loyalty Points

Extracted from payment_dialog.py for separation of concerns.
Handles MIDAS and Anonymous wallet search, creation, and point calculations.
"""
from typing import Any, Dict, List, Optional
from decimal import Decimal, ROUND_HALF_UP
import logging

logger = logging.getLogger(__name__)

class MonederoService:
    """
    Service layer for wallet/monedero operations.

    Responsibilities:
    - Search MIDAS customers by phone or name
    - Search Anonymous wallets by phone
    - Create new anonymous wallets
    - Calculate points to earn/redeem
    - Validate wallet balances

    Usage:
        service = MonederoService(core)
        result = service.search_midas("5551234567")
        if result:
            options = service.get_wallet_options(result, 'midas', sale_total)
    """

    # FIX 2026-02-01: Definir MIDAS_POINTS_RATE que se usaba sin estar definido
    # $1 punto = $1 peso, 1% de cashback por defecto
    MIDAS_POINTS_RATE = 0.01

    def __init__(self, core):
        """
        Initialize MonederoService.
        
        Args:
            core: POSCore instance for database access
        """
        self.core = core
        self._anonymous_loyalty = None
    
    @property
    def anonymous_loyalty(self):
        """Lazy load AnonymousLoyalty to avoid circular imports."""
        if self._anonymous_loyalty is None:
            from app.services.anonymous_loyalty import AnonymousLoyalty
            self._anonymous_loyalty = AnonymousLoyalty(self.core)
        return self._anonymous_loyalty
    
    def search_midas(self, search_term: str) -> Optional[Dict[str, Any]]:
        """
        Search for MIDAS customer by phone or name.
        
        Args:
            search_term: Phone number or name to search
            
        Returns:
            Dict with customer_id, name, balance, tier or None if not found
        """
        try:
            results = list(self.core.db.execute_query(
                """SELECT id, name, phone FROM customers 
                   WHERE (phone = %s OR name LIKE %s) AND is_active = 1 
                   LIMIT 10""",
                (search_term, f"%{search_term}%")
            ))
            
            if not results:
                return None
            
            return {
                'results': results,
                'count': len(results)
            }
        except Exception as e:
            logger.error(f"Error searching MIDAS: {e}")
            return None
    
    def get_midas_customer_details(self, customer_id: int) -> Optional[Dict[str, Any]]:
        """
        Get full MIDAS customer details including loyalty account.
        
        Args:
            customer_id: Customer ID
            
        Returns:
            Dict with customer details and loyalty balance
        """
        try:
            # Get customer info
            customer = list(self.core.db.execute_query(
                "SELECT id, name, phone FROM customers WHERE id = %s",
                (customer_id,)
            ))
            
            if not customer:
                return None
            
            customer = customer[0]
            
            # Get loyalty account
            loyalty = list(self.core.db.execute_query(
                "SELECT saldo_actual, nivel_lealtad FROM loyalty_accounts WHERE customer_id = %s",
                (customer_id,)
            ))
            
            # Create account if doesn't exist
            if not loyalty:
                if hasattr(self.core, 'loyalty_engine'):
                    self.core.loyalty_engine.get_or_create_account(customer_id)
                    loyalty = list(self.core.db.execute_query(
                        "SELECT saldo_actual, nivel_lealtad FROM loyalty_accounts WHERE customer_id = %s",
                        (customer_id,)
                    ))
            
            # Use Decimal for monetary balance
            raw_balance = loyalty[0]['saldo_actual'] or 0 if loyalty else 0
            balance = float(Decimal(str(raw_balance)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
            tier = loyalty[0]['nivel_lealtad'] if loyalty else 'BRONCE'
            
            return {
                'customer_id': customer_id,
                'name': customer['name'],
                'phone': customer.get('phone', ''),
                'balance': balance,
                'tier': tier or 'BRONCE',
                'source': 'midas'
            }
        except Exception as e:
            logger.error(f"Error getting MIDAS customer details: {e}")
            return None
    
    def search_anonymous(self, phone: str, min_points: int = 100) -> Optional[Dict[str, Any]]:
        """
        Search for anonymous wallet by phone.
        
        Args:
            phone: Phone number to search
            min_points: Minimum points required to return result
            
        Returns:
            Dict with wallet_id, nickname, balance, redeem_value or None
        """
        try:
            status = self.anonymous_loyalty.get_wallet_status(phone)
            
            if not status.get('found'):
                return None
            
            if status.get('points_balance', 0) < min_points:
                return None
            
            wallet = self.anonymous_loyalty.find_wallet(phone)
            if not wallet:
                return None
            
            return {
                'wallet_id': wallet['wallet_id'],
                'phone': phone,
                'nickname': status.get('nickname', 'Cliente'),
                'balance': status['points_balance'],
                'redeem_value': status['redeem_value'],
                'source': 'anonymous'
            }
        except Exception as e:
            logger.error(f"Error searching anonymous wallet: {e}")
            return None
    
    def create_anonymous_wallet(self, phone: str, nickname: str = None) -> Dict[str, Any]:
        """
        Create a new anonymous wallet.
        
        Args:
            phone: Phone number for wallet
            nickname: Optional nickname
            
        Returns:
            Dict with wallet_id and success status
        """
        try:
            result = self.anonymous_loyalty.create_wallet(phone, nickname)
            return {
                'success': True,
                'wallet_id': result.get('wallet_id'),
                'message': 'Monedero creado exitosamente'
            }
        except Exception as e:
            logger.error(f"Error creating anonymous wallet: {e}")
            return {
                'success': False,
                'wallet_id': None,
                'message': str(e)
            }
    
    def calculate_points_to_earn(self, sale_total: float, source: str = 'midas') -> int:
        """
        Calculate points customer will earn from purchase.
        
        Args:
            sale_total: Total purchase amount
            source: 'midas' or 'anonymous'
            
        Returns:
            Number of points to earn
        """
        if source == 'midas':
            return int(sale_total * self.MIDAS_POINTS_RATE)
        else:
            # Anonymous uses POINTS_PER_PESO from AnonymousLoyalty
            return int(sale_total * self.anonymous_loyalty.POINTS_PER_PESO)
    
    def get_max_redeemable(self, balance: float, sale_total: float) -> float:
        """
        Calculate maximum redeemable amount.
        
        Args:
            balance: Current wallet balance
            sale_total: Total sale amount
            
        Returns:
            Maximum amount that can be redeemed
        """
        return min(balance, sale_total)
    
    def validate_redeem_amount(self, amount: float, balance: float, 
                                sale_total: float) -> Dict[str, Any]:
        """
        Validate redemption amount.
        
        Args:
            amount: Amount to redeem
            balance: Current wallet balance
            sale_total: Total sale amount
            
        Returns:
            Dict with 'valid' boolean and 'message'
        """
        if amount <= 0:
            return {'valid': False, 'message': 'El monto debe ser mayor a cero'}
        
        if amount > balance:
            return {'valid': False, 'message': f'Saldo insuficiente. Disponible: ${balance:.2f}'}
        
        if amount > sale_total:
            return {'valid': False, 'message': f'El monto excede el total de la venta: ${sale_total:.2f}'}
        
        return {'valid': True, 'message': 'OK'}
    
    def get_wallet_options(self, wallet_data: Dict[str, Any], 
                           sale_total: float) -> Dict[str, Any]:
        """
        Get available options for a wallet (use points, accumulate, both).
        
        Args:
            wallet_data: Wallet data from search_midas or search_anonymous
            sale_total: Total sale amount
            
        Returns:
            Dict with available options and calculations
        """
        source = wallet_data.get('source', 'midas')
        balance = wallet_data.get('balance', 0) if source == 'midas' else wallet_data.get('redeem_value', 0)
        
        points_to_earn = self.calculate_points_to_earn(sale_total, source)
        max_redeemable = self.get_max_redeemable(balance, sale_total)
        
        can_use = balance >= 1
        
        return {
            'name': wallet_data.get('name', wallet_data.get('nickname', 'Cliente')),
            'balance': balance,
            'points_to_earn': points_to_earn,
            'max_redeemable': max_redeemable,
            'can_accumulate': True,
            'can_use': can_use,
            'can_both': can_use,
            'source': source,
            'customer_id': wallet_data.get('customer_id'),
            'wallet_id': wallet_data.get('wallet_id')
        }

# Singleton instance for convenience (thread-safe)
import threading

_service_lock = threading.Lock()
_service_instance = None


def get_monedero_service(core) -> MonederoService:
    """Get or create MonederoService singleton. Thread-safe."""
    global _service_instance
    if _service_instance is None:
        with _service_lock:
            # Double-check after acquiring lock
            if _service_instance is None:
                _service_instance = MonederoService(core)
    return _service_instance

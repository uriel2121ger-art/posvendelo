"""
TITAN POS - Loyalty Module

Bounded context for MIDAS loyalty program:
- Points earning and redemption
- Loyalty levels/tiers
- Customer wallets (monederos)
- Gift cards
- Promotions engine

Public API:
    - LoyaltyEngine: Loyalty program engine
    - GiftCardEngine: Gift card system
    - PromoEngine: Promotions engine
    - MonederoService: Wallet/monedero service
"""

from modules.loyalty.engine import LoyaltyEngine
from modules.loyalty.gift_card import GiftCardEngine
from modules.loyalty.promo_engine import PromoEngine
from modules.loyalty.monedero_service import MonederoService

__all__ = [
    "LoyaltyEngine",
    "GiftCardEngine",
    "PromoEngine",
    "MonederoService",
]

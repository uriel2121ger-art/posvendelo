"""
TITAN POS - Inventory Module

Bounded context for inventory management:
- Stock movements (IN/OUT/ADJUST)
- Low stock alerts
- Stock valuation
- Inventory transfers between branches
- Bin locations

Public API:
    - InventoryService: Inventory business logic
    - InventoryManager: Core inventory engine
"""

from modules.inventory.service import InventoryService
from modules.inventory.manager import InventoryManager

__all__ = [
    "InventoryService",
    "InventoryManager",
]

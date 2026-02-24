"""
TITAN POS - Inventory Service (Modular)

Re-exports InventoryService from its original location.
"""

from app.services.inventory_service import InventoryService

__all__ = ["InventoryService"]

"""
TITAN POS - Foreign Key Validator

Validates foreign keys before sync operations to prevent FK violations.
See docs/ANALISIS_ISSUES_FK_SYNC.md for details.
"""

import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class FKValidator:
    """
    Validates foreign keys before sync operations.

    Uses cache to avoid repeated database queries for the same IDs.
    """

    # Mapping of FK field names to their reference tables
    FK_TABLES = {
        'customer_id': 'customers',
        'user_id': 'users',
        'turn_id': 'turns',
        'branch_id': 'branches',
        'product_id': 'products',
    }

    # FKs that should always be NULL in sync (local-only data)
    LOCAL_ONLY_FKS = {'turn_id'}

    # Default fallback values for required FKs
    FK_DEFAULTS = {
        'user_id': 1,      # Fallback to admin user
        'branch_id': 1,    # Fallback to main branch
    }

    def __init__(self, db):
        """
        Initialize FK validator.

        Args:
            db: Database manager instance with execute_query method
        """
        self.db = db
        self._cache: Dict[str, bool] = {}

    def validate(self, fk_name: str, fk_value: Any) -> Tuple[bool, Any]:
        """
        Validate if FK exists in reference table.

        Args:
            fk_name: Name of the FK field (e.g., 'customer_id')
            fk_value: Value to validate

        Returns:
            Tuple of (exists: bool, safe_value: Any)
            - If exists: (True, original_value)
            - If not exists: (False, fallback_value or None)
        """
        # NULL is always valid
        if fk_value is None:
            return True, None

        # Local-only FKs should always be NULL in sync
        if fk_name in self.LOCAL_ONLY_FKS:
            logger.debug(f"FK {fk_name} is local-only, using NULL")
            return True, None

        # Get reference table
        table = self.FK_TABLES.get(fk_name)
        if not table:
            # Unknown FK, pass through
            return True, fk_value

        # Check cache first
        cache_key = f"{table}:{fk_value}"
        if cache_key in self._cache:
            exists = self._cache[cache_key]
            if exists:
                return True, fk_value
            else:
                fallback = self.FK_DEFAULTS.get(fk_name)
                logger.warning(f"FK {fk_name}={fk_value} not found (cached), using {fallback}")
                return False, fallback

        # Query database
        try:
            result = self.db.execute_query(
                f"SELECT id FROM {table} WHERE id = %s",
                (fk_value,)
            )
            exists = bool(result and len(result) > 0)
            self._cache[cache_key] = exists

            if exists:
                return True, fk_value
            else:
                fallback = self.FK_DEFAULTS.get(fk_name)
                logger.warning(f"FK {fk_name}={fk_value} not found in {table}, using {fallback}")
                return False, fallback

        except Exception as e:
            logger.error(f"Error validating FK {fk_name}={fk_value}: {e}")
            # On error, use fallback to be safe
            fallback = self.FK_DEFAULTS.get(fk_name)
            return False, fallback

    def validate_sale(self, sale: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate all FKs in a sale dictionary.

        Args:
            sale: Sale dictionary with potential FK fields

        Returns:
            Sale dictionary with validated/corrected FK values
        """
        validated = sale.copy()

        for fk_name in ['customer_id', 'user_id', 'turn_id', 'branch_id']:
            if fk_name in validated:
                _, safe_value = self.validate(fk_name, validated.get(fk_name))
                validated[fk_name] = safe_value

        return validated

    def validate_item(self, item: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate FKs in a sale item dictionary.

        Args:
            item: Sale item dictionary

        Returns:
            Tuple of (is_valid: bool, validated_item: Dict)
            - is_valid is False if product_id doesn't exist (item should be skipped)
        """
        validated = item.copy()

        product_id = item.get('product_id')
        if product_id:
            exists, _ = self.validate('product_id', product_id)
            if not exists:
                # Product doesn't exist - item is invalid
                logger.warning(f"Product {product_id} not found, item will be skipped")
                return False, validated

        return True, validated

    def clear_cache(self):
        """Clear the validation cache."""
        self._cache.clear()
        logger.debug("FK validation cache cleared")

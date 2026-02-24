"""
TITAN POS - Sales Module

Bounded context for all sales-related operations:
- Sale creation, cancellation, voiding
- Cart management
- Layaways (apartados)
- Checkout and payment processing
- Sales reporting

Public API:
    - SalesService: Sales business logic
    - SalesRepository: Sales data access
    - SaleEventStore: Event sourcing for sale aggregates (Phase 5)
    - SaleEventTypes: Event type constants
    - SagaOrchestrator: Saga pattern for distributed operations (Phase 5)
"""

from modules.sales.service import SalesService
from modules.sales.repository import SalesRepository
from modules.sales.event_sourcing import SaleEventStore, SaleEventTypes, SaleEvent
from modules.sales.saga import SagaOrchestrator, SagaDefinition, SagaStep, SagaResult

__all__ = [
    "SalesService",
    "SalesRepository",
    "SaleEventStore",
    "SaleEventTypes",
    "SaleEvent",
    "SagaOrchestrator",
    "SagaDefinition",
    "SagaStep",
    "SagaResult",
]

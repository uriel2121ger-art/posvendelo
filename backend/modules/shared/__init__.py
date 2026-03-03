"""
TITAN POS - Shared Module

Cross-cutting concerns shared across all domain modules:
- auth.py: JWT single source of truth
- domain_event.py: DomainEvent system
- event_bridge.py: Legacy EventBus → DomainEvent bridge
- event_bus.py: Re-export of legacy EventBus
- cache.py: Simple TTL cache
- pin_auth.py: verify_manager_pin() — verificación de PIN compartida
- turn_service.py: calculate_turn_summary() — resumen financiero de turno
"""

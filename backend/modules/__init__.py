"""
TITAN POS - Modular Monolith

Domain modules organized by bounded context.
Each module exposes its public API via __init__.py.

RULE: Inter-module communication ONLY via __init__.py imports.
      Never import internal files from another module.
"""

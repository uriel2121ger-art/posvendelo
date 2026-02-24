"""
TITAN POS - Saga Pattern for Distributed Operations

Orchestrates multi-step operations with automatic compensation (rollback)
if any step fails. Primary use case: inventory transfers between branches.

A saga defines:
  - Forward steps: the happy path
  - Compensation steps: how to undo each forward step if a later step fails

Example: Inventory Transfer Saga
  Step 1: reserve_source      → compensate: release_source
  Step 2: confirm_transport    → compensate: cancel_transport
  Step 3: receive_destination  → compensate: return_to_source
  Step 4: release_source       → (no compensation needed, already done)

Usage:
    from modules.sales.saga import SagaOrchestrator, SagaDefinition, SagaStep

    transfer_saga = SagaDefinition(
        saga_type="inventory_transfer",
        steps=[
            SagaStep("reserve_source", reserve_fn, compensate_reserve_fn),
            SagaStep("ship_items", ship_fn, cancel_ship_fn),
            SagaStep("receive_destination", receive_fn, return_fn),
        ]
    )

    orchestrator = SagaOrchestrator(db_session)
    result = await orchestrator.execute(transfer_saga, {"product_id": 42, "qty": 10, ...})
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SagaStep:
    """A single step in a saga with its forward action and compensation."""
    name: str
    action: Callable[..., Coroutine]  # async def action(context) -> result
    compensation: Optional[Callable[..., Coroutine]] = None  # async def compensate(context, result) -> None


@dataclass
class SagaDefinition:
    """Definition of a saga with ordered steps."""
    saga_type: str
    steps: List[SagaStep]


@dataclass
class SagaResult:
    """Result of saga execution."""
    saga_id: str
    saga_type: str
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    completed_steps: int = 0
    compensated_steps: int = 0


class SagaOrchestrator:
    """
    Executes sagas with automatic compensation on failure.

    Persists saga state in the saga_instances/saga_steps tables
    for crash recovery and auditing.
    """

    def __init__(self, db_session=None):
        self._db = db_session

    def _get_db(self):
        if self._db is not None:
            return self._db
        from src.infra.database import db_instance
        return db_instance

    async def execute(
        self,
        definition: SagaDefinition,
        context: Dict[str, Any],
    ) -> SagaResult:
        """
        Execute a saga definition with the given context.

        Args:
            definition: The saga to execute
            context: Shared data dict passed to each step

        Returns:
            SagaResult with success/failure info
        """
        saga_id = str(uuid.uuid4())
        result = SagaResult(
            saga_id=saga_id,
            saga_type=definition.saga_type,
            success=False,
        )

        # Persist saga start
        await self._persist_saga(saga_id, definition, context)

        completed_results: List[Dict[str, Any]] = []

        # Execute steps in order
        for i, step in enumerate(definition.steps):
            try:
                logger.info(f"Saga {saga_id}: executing step {i+1}/{len(definition.steps)} — {step.name}")
                step_result = await step.action(context)
                completed_results.append({"step": step.name, "result": step_result})
                context[f"_step_{step.name}_result"] = step_result
                result.completed_steps = i + 1

                await self._persist_step(saga_id, i, step.name, "completed", step_result)

            except Exception as e:
                logger.error(f"Saga {saga_id}: step {step.name} failed — {e}")
                result.error = f"Step '{step.name}' failed: {str(e)}"
                await self._persist_step(saga_id, i, step.name, "failed", error=str(e))

                # Compensate completed steps in reverse order
                await self._compensate(
                    saga_id, definition.steps[:i], completed_results, context, result
                )
                await self._update_saga_state(saga_id, "failed", str(e))
                return result

        # All steps completed
        result.success = True
        result.data = {r["step"]: r["result"] for r in completed_results}
        await self._update_saga_state(saga_id, "completed")

        logger.info(f"Saga {saga_id} ({definition.saga_type}): completed successfully")
        return result

    async def _compensate(
        self,
        saga_id: str,
        completed_steps: List[SagaStep],
        completed_results: List[Dict[str, Any]],
        context: Dict[str, Any],
        result: SagaResult,
    ):
        """Run compensation steps in reverse order."""
        for i in range(len(completed_steps) - 1, -1, -1):
            step = completed_steps[i]
            step_result = completed_results[i]["result"] if i < len(completed_results) else None

            if step.compensation is None:
                logger.info(f"Saga {saga_id}: no compensation for step {step.name}, skipping")
                continue

            try:
                logger.info(f"Saga {saga_id}: compensating step {step.name}")
                await step.compensation(context, step_result)
                result.compensated_steps += 1
                await self._persist_step(saga_id, i, step.name, "compensated")
            except Exception as e:
                logger.error(
                    f"Saga {saga_id}: compensation failed for {step.name} — {e}. "
                    f"MANUAL INTERVENTION REQUIRED."
                )
                await self._persist_step(
                    saga_id, i, step.name, "compensation_failed", error=str(e)
                )

    async def _persist_saga(
        self, saga_id: str, definition: SagaDefinition, context: Dict[str, Any]
    ):
        """Persist initial saga state."""
        db = self._get_db()
        import json

        if hasattr(db, "execute"):
            from sqlalchemy import text
            await db.execute(
                text("""
                    INSERT INTO saga_instances (saga_id, saga_type, state, data, total_steps, created_at)
                    VALUES (:saga_id, :saga_type, 'started', :data::jsonb, :total_steps, NOW())
                """),
                {
                    "saga_id": saga_id,
                    "saga_type": definition.saga_type,
                    "data": json.dumps(context, default=str),
                    "total_steps": len(definition.steps),
                },
            )
        else:
            db.execute_update(
                """INSERT INTO saga_instances (saga_id, saga_type, state, data, total_steps, created_at)
                   VALUES (?, ?, 'started', ?::jsonb, ?, NOW())""",
                (saga_id, definition.saga_type, json.dumps(context, default=str), len(definition.steps)),
            )

    async def _persist_step(
        self,
        saga_id: str,
        step_number: int,
        step_name: str,
        status: str,
        result: Any = None,
        error: Optional[str] = None,
    ):
        """Persist a step execution result."""
        db = self._get_db()
        import json

        if hasattr(db, "execute"):
            from sqlalchemy import text
            await db.execute(
                text("""
                    INSERT INTO saga_steps (saga_id, step_number, step_name, status, result, error_message, executed_at)
                    VALUES (:saga_id, :step_number, :step_name, :status, :result::jsonb, :error, NOW())
                    ON CONFLICT DO NOTHING
                """),
                {
                    "saga_id": saga_id,
                    "step_number": step_number,
                    "step_name": step_name,
                    "status": status,
                    "result": json.dumps(result, default=str) if result else "{}",
                    "error": error,
                },
            )

    async def _update_saga_state(
        self, saga_id: str, state: str, error: Optional[str] = None
    ):
        """Update saga instance state."""
        db = self._get_db()
        if hasattr(db, "execute"):
            from sqlalchemy import text
            await db.execute(
                text("""
                    UPDATE saga_instances
                    SET state = :state, error_message = :error, updated_at = NOW(),
                        completed_at = CASE WHEN :state IN ('completed', 'failed') THEN NOW() ELSE NULL END
                    WHERE saga_id = :saga_id
                """),
                {"saga_id": saga_id, "state": state, "error": error},
            )


# ============================================================================
# Pre-built Saga: Inventory Transfer
# ============================================================================

async def _reserve_source_stock(context: Dict[str, Any]):
    """Reserve stock at source branch (FOR UPDATE)."""
    # This would call the inventory service
    logger.info(f"Reserving {context['qty']} units of product {context['product_id']} at branch {context['source_branch_id']}")
    return {"reserved": True, "qty": context["qty"]}


async def _release_source_reservation(context: Dict[str, Any], step_result: Any):
    """Compensate: release the reservation at source."""
    logger.info(f"Releasing reservation for product {context['product_id']} at branch {context['source_branch_id']}")


async def _create_transfer_record(context: Dict[str, Any]):
    """Create the transfer record in DB."""
    logger.info(f"Creating transfer record: {context['source_branch_id']} → {context['dest_branch_id']}")
    return {"transfer_id": "TRF-001"}


async def _cancel_transfer_record(context: Dict[str, Any], step_result: Any):
    """Compensate: cancel the transfer record."""
    logger.info(f"Cancelling transfer {step_result.get('transfer_id')}")


async def _receive_at_destination(context: Dict[str, Any]):
    """Add stock at destination branch."""
    logger.info(f"Receiving {context['qty']} units at branch {context['dest_branch_id']}")
    return {"received": True}


async def _return_from_destination(context: Dict[str, Any], step_result: Any):
    """Compensate: remove stock from destination."""
    logger.info(f"Returning stock from branch {context['dest_branch_id']}")


async def _confirm_source_deduction(context: Dict[str, Any]):
    """Finalize: deduct stock from source (reservation → real deduction)."""
    logger.info(f"Confirming stock deduction at branch {context['source_branch_id']}")
    return {"confirmed": True}


# Pre-built definition
INVENTORY_TRANSFER_SAGA = SagaDefinition(
    saga_type="inventory_transfer",
    steps=[
        SagaStep("reserve_source", _reserve_source_stock, _release_source_reservation),
        SagaStep("create_transfer", _create_transfer_record, _cancel_transfer_record),
        SagaStep("receive_destination", _receive_at_destination, _return_from_destination),
        SagaStep("confirm_deduction", _confirm_source_deduction, None),  # No compensation — already received
    ],
)

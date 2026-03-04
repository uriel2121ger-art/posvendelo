"""
TITAN POS - Saga Pattern for Distributed Operations

Orchestrates multi-step operations with automatic compensation (rollback)
if any step fails. Primary use case: inventory transfers between branches.

A saga defines:
  - Forward steps: the happy path
  - Compensation steps: how to undo each forward step if a later step fails

Example: Inventory Transfer Saga
  Step 1: reserve_source      -> compensate: release_source
  Step 2: confirm_transport    -> compensate: cancel_transport
  Step 3: receive_destination  -> compensate: return_to_source
  Step 4: release_source       -> (no compensation needed, already done)

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

    orchestrator = SagaOrchestrator()
    result = await orchestrator.execute(transfer_saga, {"product_id": 42, "qty": 10, ...})
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
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

    def __init__(self, db=None):
        self._db = db

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
                logger.info(f"Saga {saga_id}: executing step {i+1}/{len(definition.steps)} -- {step.name}")
                step_result = await step.action(context)
                completed_results.append({"step": step.name, "result": step_result})
                context[f"_step_{step.name}_result"] = step_result
                result.completed_steps = i + 1

                await self._persist_step(saga_id, i, step.name, "completed", step_result)

            except Exception as e:
                logger.error(f"Saga {saga_id}: step {step.name} failed -- {e}")
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
                    f"Saga {saga_id}: compensation failed for {step.name} -- {e}. "
                    f"MANUAL INTERVENTION REQUIRED."
                )
                await self._persist_step(
                    saga_id, i, step.name, "compensation_failed", error=str(e)
                )

    async def _persist_saga(
        self, saga_id: str, definition: SagaDefinition, context: Dict[str, Any]
    ):
        """Persist initial saga state."""
        try:
            from db.connection import get_connection
            async with get_connection() as db:
                await db.execute(
                    """
                    INSERT INTO saga_instances (saga_id, saga_type, state, data, total_steps, created_at)
                    VALUES (:saga_id, :saga_type, 'started', :data::jsonb, :total_steps, NOW())
                    """,
                    {
                        "saga_id": saga_id,
                        "saga_type": definition.saga_type,
                        "data": json.dumps(context, default=str),
                        "total_steps": len(definition.steps),
                    },
                )
        except Exception as e:
            logger.warning(f"Failed to persist saga {saga_id}: {e}")

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
        try:
            from db.connection import get_connection
            async with get_connection() as db:
                await db.execute(
                    """
                    INSERT INTO saga_steps (saga_id, step_number, step_name, status, result, error_message, executed_at)
                    VALUES (:saga_id, :step_number, :step_name, :status, :result::jsonb, :error, NOW())
                    ON CONFLICT DO NOTHING
                    """,
                    {
                        "saga_id": saga_id,
                        "step_number": step_number,
                        "step_name": step_name,
                        "status": status,
                        "result": json.dumps(result, default=str) if result else "{}",
                        "error": error,
                    },
                )
        except Exception as e:
            logger.warning(f"Failed to persist saga step {saga_id}/{step_name}: {e}")

    async def _update_saga_state(
        self, saga_id: str, state: str, error: Optional[str] = None
    ):
        """Update saga instance state."""
        try:
            from db.connection import get_connection
            async with get_connection() as db:
                await db.execute(
                    """
                    UPDATE saga_instances
                    SET state = :state, error_message = :error, updated_at = NOW(),
                        completed_at = CASE WHEN :state IN ('completed', 'failed') THEN NOW() ELSE NULL END
                    WHERE saga_id = :saga_id
                    """,
                    {"saga_id": saga_id, "state": state, "error": error},
                )
        except Exception as e:
            logger.warning(f"Failed to update saga state {saga_id}: {e}")


# ============================================================================
# Pre-built Saga: Inventory Transfer
# ============================================================================

async def _reserve_source_stock(context: Dict[str, Any]):
    """Reserve stock at source branch (FOR UPDATE to prevent race conditions)."""
    from db.connection import get_connection

    product_id = context["product_id"]
    qty = context["qty"]

    async with get_connection() as db:
        async with db.connection.transaction():
            row = await db.fetchrow(
                "SELECT stock, shadow_stock FROM products WHERE id = :pid FOR UPDATE",
                {"pid": product_id},
            )
            if not row:
                raise ValueError(f"Producto {product_id} no encontrado")

            current_stock = Decimal(str(row["stock"] or 0))
            reserved = Decimal(str(row.get("shadow_stock") or 0))
            available = current_stock - reserved
            qty_dec = Decimal(str(qty))
            if available < qty_dec:
                raise ValueError(
                    f"Stock insuficiente para producto {product_id}: "
                    f"disponible {available} (stock={current_stock}, reservado={reserved}), necesita {qty}"
                )

            await db.execute(
                "UPDATE products SET shadow_stock = shadow_stock + :qty WHERE id = :pid",
                {"qty": qty_dec, "pid": product_id},
            )

    logger.info(f"Reserved {qty} units of product {product_id}")
    return {"reserved": True, "qty": qty, "previous_stock": current_stock}


async def _release_source_reservation(context: Dict[str, Any], step_result: Any):
    """Compensate: release the reservation at source."""
    from db.connection import get_connection
    async with get_connection() as db:
        await db.execute(
            "UPDATE products SET shadow_stock = shadow_stock - :qty WHERE id = :pid",
            {"qty": context["qty"], "pid": context["product_id"]},
        )
    logger.info(f"Released reservation for product {context['product_id']}")


async def _create_transfer_record(context: Dict[str, Any]):
    """Create the inventory transfer record in DB."""
    from db.connection import get_connection

    transfer_id = f"TRF-{uuid.uuid4().hex[:8].upper()}"

    async with get_connection() as db:
        # Patrón seguro: usar NOW() en SQL para timestamp (evita bug asyncpg naive/aware)
        await db.execute(
            """
            INSERT INTO inventory_movements
                (product_id, movement_type, type, quantity, reason, reference_type, reference_id, user_id, timestamp, synced)
            VALUES
                (:pid, 'OUT', 'transfer', :qty, :reason, 'transfer', :ref, 0, NOW(), 0)
            """,
            {
                "pid": context["product_id"],
                "qty": round(abs(float(context["qty"])), 2),
                "reason": f"Transfer to branch {context['dest_branch_id']}",
                "ref": transfer_id,
            },
        )

    logger.info(f"Transfer record created: {transfer_id}")
    return {"transfer_id": transfer_id, "timestamp": None}


async def _cancel_transfer_record(context: Dict[str, Any], step_result: Any):
    """Compensate: delete the transfer movement record."""
    from db.connection import get_connection

    transfer_id = step_result.get("transfer_id") if step_result else None
    if not transfer_id:
        return

    async with get_connection() as db:
        await db.execute(
            "DELETE FROM inventory_movements WHERE reference_id = :ref",
            {"ref": transfer_id},
        )
    logger.info(f"Transfer record {transfer_id} cancelled")


async def _receive_at_destination(context: Dict[str, Any]):
    """Add stock at destination branch and record incoming movement."""
    from db.connection import get_connection

    transfer_id = context.get("_step_create_transfer_result", {}).get("transfer_id", "")

    async with get_connection() as db:
        # Patrón seguro: usar NOW() en SQL para timestamp (evita bug asyncpg naive/aware)
        await db.execute(
            """
            INSERT INTO inventory_movements
                (product_id, movement_type, type, quantity, reason, reference_type, reference_id, user_id, timestamp, synced)
            VALUES
                (:pid, 'IN', 'transfer', :qty, :reason, 'transfer', :ref, 0, NOW(), 0)
            """,
            {
                "pid": context["product_id"],
                "qty": round(abs(float(context["qty"])), 2),
                "reason": f"Transfer from branch {context['source_branch_id']}",
                "ref": transfer_id,
            },
        )

    logger.info(f"Received {context['qty']} units at destination")
    return {"received": True, "transfer_id": transfer_id}


async def _return_from_destination(context: Dict[str, Any], step_result: Any):
    """Compensate: remove the incoming movement record."""
    from db.connection import get_connection

    transfer_id = step_result.get("transfer_id") if step_result else None
    if not transfer_id:
        return

    async with get_connection() as db:
        await db.execute(
            "DELETE FROM inventory_movements WHERE reference_id = :ref AND movement_type = 'IN' AND type = 'transfer'",
            {"ref": transfer_id},
        )
    logger.info(f"Returned stock from destination (transfer {transfer_id})")


async def _confirm_source_deduction(context: Dict[str, Any]):
    """Finalize: deduct real stock from source (convert reservation to actual deduction)."""
    from db.connection import get_connection

    async with get_connection() as db:
        async with db.connection.transaction():
            await db.execute(
                """
                UPDATE products
                SET stock = stock - :qty,
                    shadow_stock = shadow_stock - :qty
                WHERE id = :pid
                """,
                {"qty": context["qty"], "pid": context["product_id"]},
            )

    logger.info(f"Source stock deduction confirmed for product {context['product_id']}")
    return {"confirmed": True}


# Pre-built definition
INVENTORY_TRANSFER_SAGA = SagaDefinition(
    saga_type="inventory_transfer",
    steps=[
        SagaStep("reserve_source", _reserve_source_stock, _release_source_reservation),
        SagaStep("create_transfer", _create_transfer_record, _cancel_transfer_record),
        SagaStep("receive_destination", _receive_at_destination, _return_from_destination),
        SagaStep("confirm_deduction", _confirm_source_deduction, None),  # No compensation -- already received
    ],
)

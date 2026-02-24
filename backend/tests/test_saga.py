"""Tests for modules/sales/saga.py — Saga orchestrator logic"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from modules.sales.saga import (
    SagaOrchestrator,
    SagaDefinition,
    SagaStep,
    SagaResult,
)


def _mock_orchestrator():
    """Create a SagaOrchestrator with mocked DB persistence."""
    orch = SagaOrchestrator.__new__(SagaOrchestrator)
    orch._db = MagicMock()
    # Mock persistence methods to be no-ops
    orch._persist_saga = AsyncMock()
    orch._persist_step = AsyncMock()
    orch._update_saga_state = AsyncMock()
    return orch


# ============================================================================
# Happy path
# ============================================================================

async def test_saga_all_steps_succeed():
    """Saga completes successfully when all steps pass."""
    orch = _mock_orchestrator()

    step1 = SagaStep("step1", AsyncMock(return_value={"a": 1}), AsyncMock())
    step2 = SagaStep("step2", AsyncMock(return_value={"b": 2}), AsyncMock())

    saga = SagaDefinition(saga_type="test_saga", steps=[step1, step2])
    result = await orch.execute(saga, {"key": "value"})

    assert result.success is True
    assert result.completed_steps == 2
    assert result.compensated_steps == 0
    assert result.error is None
    assert "step1" in result.data
    assert "step2" in result.data


async def test_saga_generates_unique_id():
    """Each saga execution gets a unique ID."""
    orch = _mock_orchestrator()
    step = SagaStep("s", AsyncMock(return_value={}), None)
    saga = SagaDefinition(saga_type="test", steps=[step])

    r1 = await orch.execute(saga, {})
    r2 = await orch.execute(saga, {})

    assert r1.saga_id != r2.saga_id


# ============================================================================
# Failure + compensation
# ============================================================================

async def test_saga_compensates_on_failure():
    """When step 2 fails, step 1's compensation runs."""
    orch = _mock_orchestrator()

    comp1 = AsyncMock()
    step1 = SagaStep("step1", AsyncMock(return_value={"reserved": True}), comp1)
    step2 = SagaStep("step2", AsyncMock(side_effect=ValueError("DB error")), AsyncMock())

    saga = SagaDefinition(saga_type="test", steps=[step1, step2])
    result = await orch.execute(saga, {})

    assert result.success is False
    assert "step2" in result.error
    assert result.completed_steps == 1
    assert result.compensated_steps == 1
    comp1.assert_called_once()


async def test_saga_compensates_in_reverse_order():
    """Compensation runs in reverse order of completed steps."""
    orch = _mock_orchestrator()

    order = []
    comp1 = AsyncMock(side_effect=lambda ctx, res: order.append("comp1"))
    comp2 = AsyncMock(side_effect=lambda ctx, res: order.append("comp2"))

    step1 = SagaStep("step1", AsyncMock(return_value={}), comp1)
    step2 = SagaStep("step2", AsyncMock(return_value={}), comp2)
    step3 = SagaStep("step3", AsyncMock(side_effect=RuntimeError("fail")), None)

    saga = SagaDefinition(saga_type="test", steps=[step1, step2, step3])
    result = await orch.execute(saga, {})

    assert result.success is False
    assert order == ["comp2", "comp1"]  # Reverse order


async def test_saga_skips_steps_without_compensation():
    """Steps without compensation function are skipped during rollback."""
    orch = _mock_orchestrator()

    comp1 = AsyncMock()
    step1 = SagaStep("step1", AsyncMock(return_value={}), comp1)
    step2 = SagaStep("step2", AsyncMock(return_value={}), None)  # No compensation
    step3 = SagaStep("step3", AsyncMock(side_effect=RuntimeError("fail")), None)

    saga = SagaDefinition(saga_type="test", steps=[step1, step2, step3])
    result = await orch.execute(saga, {})

    assert result.compensated_steps == 1  # Only step1
    comp1.assert_called_once()


async def test_saga_first_step_fails():
    """If first step fails, no compensation needed."""
    orch = _mock_orchestrator()

    step1 = SagaStep("step1", AsyncMock(side_effect=ValueError("bad")), AsyncMock())

    saga = SagaDefinition(saga_type="test", steps=[step1])
    result = await orch.execute(saga, {})

    assert result.success is False
    assert result.completed_steps == 0
    assert result.compensated_steps == 0


# ============================================================================
# Context propagation
# ============================================================================

async def test_saga_passes_context_to_steps():
    """Each step receives the shared context dict."""
    orch = _mock_orchestrator()
    captured_ctx = []

    async def capture_step(ctx):
        captured_ctx.append(dict(ctx))
        return {"done": True}

    step1 = SagaStep("step1", capture_step, None)
    saga = SagaDefinition(saga_type="test", steps=[step1])

    await orch.execute(saga, {"product_id": 42, "qty": 10})

    assert captured_ctx[0]["product_id"] == 42
    assert captured_ctx[0]["qty"] == 10


async def test_saga_step_results_in_context():
    """Step results are available in context for subsequent steps."""
    orch = _mock_orchestrator()

    async def step1_action(ctx):
        return {"transfer_id": "TRF-001"}

    async def step2_action(ctx):
        # Should see step1's result in context
        assert ctx.get("_step_step1_result") == {"transfer_id": "TRF-001"}
        return {"received": True}

    step1 = SagaStep("step1", step1_action, None)
    step2 = SagaStep("step2", step2_action, None)

    saga = SagaDefinition(saga_type="test", steps=[step1, step2])
    result = await orch.execute(saga, {})

    assert result.success is True


# ============================================================================
# SagaResult
# ============================================================================

def test_saga_result_defaults():
    """SagaResult has sensible defaults."""
    r = SagaResult(saga_id="abc", saga_type="test", success=False)
    assert r.data == {}
    assert r.error is None
    assert r.completed_steps == 0
    assert r.compensated_steps == 0

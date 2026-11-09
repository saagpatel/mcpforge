"""Real asynchronous operations run inside the failure boundary."""

import asyncio

import pytest

from mcpforge.failure.runtime_py import call_operation

CONTRACT = {"retryable": True, "partial_result_allowed": True}
SCHEMA = {"type": "object", "required": ["value"]}


@pytest.mark.asyncio
async def test_operation_success_and_malformed():
    async def operation():
        return {"value": 1}

    assert await call_operation(operation, CONTRACT, 1, SCHEMA) == {
        "status": "complete",
        "failure": None,
        "items": [{"value": 1}],
    }
    result = await call_operation(operation, CONTRACT, 1, {"required": ["missing"]})
    assert result["failure"]["kind"] == "malformed"
    assert result["items"] == []


@pytest.mark.asyncio
async def test_iterator_timeout_preserves_partial_and_closes():
    closed = False

    async def operation():
        nonlocal closed
        try:
            yield {"value": 1}
            await asyncio.Event().wait()
        finally:
            closed = True

    result = await call_operation(operation(), CONTRACT, 0.01, SCHEMA)
    assert result["status"] == "incomplete"
    assert result["failure"]["kind"] == "timeout"
    assert result["items"] == [{"value": 1}]
    assert closed


@pytest.mark.asyncio
async def test_operation_cancellation_propagates_and_cleans_up():
    started = asyncio.Event()
    closed = asyncio.Event()

    async def operation():
        try:
            started.set()
            await asyncio.Event().wait()
        finally:
            closed.set()

    task = asyncio.create_task(call_operation(operation, CONTRACT, 10, SCHEMA))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed.is_set()


@pytest.mark.asyncio
async def test_operation_exception_is_normalized():
    async def operation():
        raise RuntimeError("private upstream detail")

    result = await call_operation(operation, CONTRACT, 1)
    assert result["failure"]["kind"] == "upstream_error"
    assert result["failure"]["detail"] == "upstream failed"

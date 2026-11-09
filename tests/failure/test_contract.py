"""The vendored Python resolver must stay aligned with the shared contract."""

import asyncio
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from mcpforge.contracts import FailureContract, resolve_outcome
from mcpforge.failure.runtime_py import resolve_failure


@pytest.mark.parametrize(
    "kind",
    ["timeout", "malformed", "cancelled", "upstream_error", "cursor_expired", "page_shifted"],
)
@pytest.mark.parametrize("retryable", [False, True])
@pytest.mark.parametrize("partial_result_allowed", [False, True])
@pytest.mark.parametrize("have_partial", [False, True])
def test_contract_resolver_parity(kind, retryable, partial_result_allowed, have_partial):
    contract = FailureContract(retryable=retryable, partial_result_allowed=partial_result_allowed)
    detail = "fixture detail"
    expected = resolve_outcome(contract, kind, have_partial, detail).model_dump(exclude_none=True)
    actual = resolve_failure(contract.model_dump(), kind, have_partial, detail)
    assert actual == expected


@pytest.mark.asyncio
async def test_runtime_caller_cancellation_records_releases_and_reraises():
    contract = {"retryable": True, "partial_result_allowed": True}
    upstream = {
        "response_schema": {"type": "object"},
        "script": [{"hang": True}],
    }
    task = asyncio.create_task(resolve_call(upstream, contract))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert upstream["_released"] is True
    assert upstream["_cancelled_outcome"] == {
        "status": "failed",
        "failure": {
            "kind": "cancelled",
            "retryable": False,
            "partial_result": False,
            "detail": "upstream cancelled",
        },
        "items": [],
    }


async def resolve_call(upstream, contract):
    from mcpforge.failure.runtime_py import call_upstream

    return await call_upstream(upstream, contract, 0.05)


@pytest.mark.asyncio
async def test_runtime_timeout_is_deterministic_and_releases_upstream():
    from mcpforge.failure.runtime_py import call_upstream

    upstream = {"response_schema": {}, "script": [{"hang": True}]}
    result = await call_upstream(
        upstream,
        {"retryable": True, "partial_result_allowed": False},
        0.001,
    )
    assert result["failure"]["kind"] == "timeout"
    assert result["failure"]["retryable"] is True
    assert upstream["_released"] is True


@pytest.mark.asyncio
async def test_runtime_schema_subset_checks_nested_required_items_and_enum():
    from mcpforge.failure.runtime_py import call_upstream

    upstream = {
        "response_schema": {
            "type": "object",
            "required": ["records"],
            "properties": {
                "records": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["state"],
                        "properties": {"state": {"enum": ["ok", "done"]}},
                    },
                }
            },
        },
        "script": [{"emit": {"records": [{"state": "bad"}]}}],
    }
    result = await call_upstream(
        upstream,
        {"retryable": False, "partial_result_allowed": False},
        0.05,
    )
    assert result["failure"]["kind"] == "malformed"
    assert result["items"] == []


@pytest.mark.parametrize("cancel_during_hang", [False, True])
def test_typescript_external_cancellation(cancel_during_hang):
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js 22.6+ is required to test TypeScript cancellation")
    runtime = Path(__file__).parents[2] / "src" / "mcpforge" / "failure" / "runtime_ts.ts"
    setup = (
        "const controller = new AbortController();\n"
        + ("" if cancel_during_hang else "controller.abort();\n")
        + "const upstream = { response_schema: { type: 'object' }, script: [{ hang: true }] };\n"
        + "let recorded;\n"
        + "const contract = { retryable: true, partial_result_allowed: true };\n"
        + "const options = { signal: controller.signal,\n"
        + "  onCancelled: (value) => recorded = value };\n"
        + "const pending = callUpstream(upstream, contract, 50, options);\n"
        + ("await Promise.resolve(); controller.abort();\n" if cancel_during_hang else "")
        + "try { await pending; process.exitCode = 2; }\n"
        + "catch (error) { if (error.message !== 'cancelled') process.exitCode = 3; }\n"
        + "process.stdout.write(JSON.stringify(recorded));\n"
    )
    source = f"import {{ callUpstream }} from {json.dumps(runtime.as_uri())};\n{setup}"
    completed = subprocess.run(
        [node, "--input-type=module", "-e", source],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
    outcome = json.loads(completed.stdout)
    assert outcome["failure"]["kind"] == "cancelled"
    assert outcome["status"] == "failed"
    assert outcome["items"] == []

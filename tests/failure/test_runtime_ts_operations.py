"""Real TypeScript operations follow the same normalization as descriptors."""

import asyncio
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from mcpforge.failure.runtime_py import call_operation as call_operation_py

NODE = shutil.which("node")
RUNTIME = Path(__file__).parents[2] / "src" / "mcpforge" / "failure" / "runtime_ts.ts"


def run_typescript(source: str) -> dict:
    if NODE is None:
        pytest.fail("Node.js 22.6+ is required to test TypeScript operations")
    program = f"import {{ callOperation }} from {json.dumps(RUNTIME.as_uri())};\n{source}"
    completed = subprocess.run(
        [NODE, "--input-type=module", "-e", program],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


@pytest.mark.parametrize(
    ("operation", "expected_items"),
    [
        (
            "async (signal) => ({ value: 'ok', signalAborted: signal.aborted })",
            [{"value": "ok", "signalAborted": False}],
        ),
        (
            "({ async *[Symbol.asyncIterator]() { yield { value: 'one' }; "
            "yield { value: 'two' }; } })",
            [{"value": "one"}, {"value": "two"}],
        ),
    ],
)
def test_call_operation_success(operation, expected_items):
    result = run_typescript(
        "const result = await callOperation("
        + operation
        + ", "
        + "{ retryable: true, partial_result_allowed: true }, 100, { type: 'object' });"
        + "process.stdout.write(JSON.stringify(result));"
    )
    assert result == {"status": "complete", "failure": None, "items": expected_items}


@pytest.mark.parametrize(
    ("response_schema", "value"),
    [
        ({"type": "object", "required": ["constructor"]}, {}),
        ({"type": "object", "required": ["toString"]}, {}),
        (
            {
                "type": "object",
                "properties": {
                    "constructor": {"type": "string"},
                    "toString": {"type": "string"},
                },
            },
            {},
        ),
    ],
)
def test_inherited_property_schema_behavior_matches_python(response_schema, value):
    contract = {"retryable": False, "partial_result_allowed": False}
    py_result = asyncio.run(call_operation_py(lambda: value, contract, 1, response_schema))
    ts_result = run_typescript(
        "const result = await callOperation(async () => ({}), "
        f"{json.dumps(contract)}, 100, {json.dumps(response_schema)});"
        "process.stdout.write(JSON.stringify(result));"
    )
    assert ts_result == py_result


@pytest.mark.parametrize("case", ["success", "timeout", "malformed"])
def test_operation_outcomes_match_python(case):
    contract = {"retryable": True, "partial_result_allowed": True}
    schema = {
        "type": "object",
        "required": ["value"],
        "properties": {"value": {"type": "string"}},
    }
    if case == "success":

        async def py_operation():
            return {"value": "ok"}

        ts_operation = "async (_signal) => ({ value: 'ok' })"
        timeout_s = 1
        timeout_ms = 1000
    elif case == "timeout":

        async def py_operation():
            async def stream():
                yield {"value": "first"}
                await asyncio.Event().wait()

            return stream()

        ts_operation = (
            "async function* (signal) { yield { value: 'first' }; "
            "await new Promise((resolve) => signal.addEventListener('abort', resolve, "
            "{ once: true })); }"
        )
        timeout_s = 0.02
        timeout_ms = 20
    else:

        async def py_operation():
            return {"value": 5}

        ts_operation = "async (_signal) => ({ value: 5 })"
        timeout_s = 1
        timeout_ms = 1000
    py_result = asyncio.run(call_operation_py(py_operation, contract, timeout_s, schema))
    ts_result = run_typescript(
        f"const result = await callOperation({ts_operation}, {json.dumps(contract)}, "
        f"{timeout_ms}, {json.dumps(schema)});"
        "process.stdout.write(JSON.stringify(result));"
    )
    assert ts_result == py_result


def test_uncooperative_generator_cleanup_is_bounded_and_preserves_partial():
    # JavaScript cannot interrupt the await inside a generator: return() queues
    # behind next(). The finite cleanup budget must report that limitation.
    result = run_typescript(
        "const operation = async function* () { yield { value: 'first' }; "
        "await new Promise(() => {}); };\n"
        "const result = await callOperation(operation, "
        "{ retryable: true, partial_result_allowed: true }, 10, {}, "
        "{ cleanupTimeoutMs: 20 });\n"
        "process.stdout.write(JSON.stringify(result));"
    )
    assert result == {
        "status": "incomplete",
        "failure": {
            "kind": "timeout",
            "retryable": True,
            "partial_result": True,
            "detail": "upstream timed out; cleanup_timed_out",
        },
        "items": [{"value": "first"}],
    }


def test_call_operation_timeout_preserves_partial_and_aborts_signal():
    result = run_typescript(
        "let signalAborted = false;\n"
        "const operation = async function* (signal) {\n"
        "  yield { value: 'first' };\n"
        "  await new Promise((resolve) => signal.addEventListener("
        "'abort', resolve, { once: true }));\n"
        "  signalAborted = signal.aborted;\n"
        "};\n"
        "const result = await callOperation(operation, "
        "{ retryable: true, partial_result_allowed: true }, 10, { type: 'object' });\n"
        "process.stdout.write(JSON.stringify({ result, signalAborted }));"
    )
    assert result["result"]["status"] == "incomplete"
    assert result["result"]["failure"]["kind"] == "timeout"
    assert result["result"]["items"] == [{"value": "first"}]


def test_abort_aware_operation_rejection_does_not_mask_timeout():
    result = run_typescript(
        "let observedAbort = false;\n"
        "const operation = (signal) => new Promise((_resolve, reject) => "
        "signal.addEventListener('abort', () => { observedAbort = true; "
        "reject(new Error('stopped')); }, { once: true }));\n"
        "const result = await callOperation(operation, "
        "{ retryable: true, partial_result_allowed: false }, 10);\n"
        "process.stdout.write(JSON.stringify({ result, observedAbort }));"
    )
    assert result["observedAbort"] is True
    assert result["result"]["failure"]["kind"] == "timeout"


def test_pre_aborted_signal_is_cancellation():
    result = run_typescript(
        "const controller = new AbortController(); controller.abort(); let recorded;\n"
        "const pending = callOperation(async () => ({ value: 'late' }), "
        "{ retryable: true, partial_result_allowed: true }, 1000, {}, "
        "{ signal: controller.signal, onCancelled: (value) => recorded = value });\n"
        "try { await pending; process.exitCode = 2; } catch (error) { "
        "if (error.message !== 'cancelled') process.exitCode = 3; }\n"
        "process.stdout.write(JSON.stringify(recorded));"
    )
    assert result["failure"]["kind"] == "cancelled"
    assert result["items"] == []


def test_call_operation_malformed_value_is_normalized():
    result = run_typescript(
        "const result = await callOperation(async () => ({ value: 3 }), "
        "{ retryable: false, partial_result_allowed: false }, 100, "
        "{ type: 'object', required: ['value'], properties: { value: { type: 'string' } } });"
        "process.stdout.write(JSON.stringify(result));"
    )
    assert result["status"] == "failed"
    assert result["failure"]["kind"] == "malformed"
    assert result["items"] == []


def test_call_operation_external_cancellation_propagates():
    result = run_typescript(
        "const controller = new AbortController(); let recorded;\n"
        "const operation = async (signal) => new Promise((resolve) => "
        "signal.addEventListener('abort', resolve, { once: true }));\n"
        "const pending = callOperation(operation, "
        "{ retryable: true, partial_result_allowed: true }, 1000, {}, "
        "{ signal: controller.signal, onCancelled: (value) => recorded = value });\n"
        "controller.abort();\n"
        "try { await pending; process.exitCode = 2; } catch (error) { "
        "if (error.message !== 'cancelled') process.exitCode = 3; }\n"
        "process.stdout.write(JSON.stringify(recorded));"
    )
    assert result["status"] == "failed"
    assert result["failure"]["kind"] == "cancelled"


@pytest.mark.parametrize(
    "schema",
    [
        "{ type: 'object', required: ['constructor'] }",
        "{ type: 'object', required: ['toString'] }",
        "{ type: 'object', properties: { constructor: { type: 'string' }, "
        "toString: { type: 'string' } } }",
    ],
)
def test_call_operation_schema_checks_use_own_properties(schema):
    result = run_typescript(
        f"const result = await callOperation(async () => ({{}}), "
        f"{{ retryable: false, partial_result_allowed: false }}, 100, {schema});"
        "process.stdout.write(JSON.stringify(result));"
    )
    expect_malformed = "required" in schema
    assert result["status"] == ("failed" if expect_malformed else "complete")
    assert (result["failure"] or {}).get("kind") == ("malformed" if expect_malformed else None)

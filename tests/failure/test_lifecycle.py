"""Lifecycle tables exercise cleanup, cancellation and late results in both runtimes."""

import asyncio
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from mcpforge.failure.codegen import generate_server
from mcpforge.failure.runtime_py import call_operation, resolve_failure
from mcpforge.models import ServerPlan, ToolDef

ROOT = Path(__file__).parents[2]
CONTRACT = {"retryable": True, "partial_result_allowed": True}
SCHEMA = {"type": "object", "required": ["value"]}
CASES = (
    "success",
    "malformed",
    "malformed_cleanup_error",
    "next_error",
    "cleanup_error",
    "timeout",
    "timeout_cleanup_error",
    "cancel",
    "cancel_cleanup_error",
    "cleanup_cancel",
    "cleanup_cancel_cleanup_error",
    "late_factory_timeout",
    "late_factory_cancel",
    "late_factory_timeout_cleanup_error",
    "late_factory_cancel_cleanup_error",
    "late_value_timeout",
    "late_value_cancel",
    "late_reject_timeout",
    "late_reject_cancel",
    "late_next_timeout",
    "late_next_cancel",
    "late_next_error_timeout",
    "late_next_error_cancel",
)


async def python_case(mode, call=call_operation):
    acquired = closed = reads = 0
    cleaned = settled = escaped = False
    started = asyncio.Event()
    cleanup_started = asyncio.Event()
    cleanup_gate = asyncio.Event()
    late = mode.startswith("late_")
    cancels = "cancel" in mode

    class Stream:
        def __aiter__(self):
            nonlocal acquired
            acquired += 1
            return self

        async def __anext__(self):
            nonlocal reads
            reads += 1
            if reads == 1:
                return {"value": 1}
            if mode.startswith("malformed"):
                return "invalid"
            if mode == "next_error":
                raise RuntimeError("private upstream detail")
            if "timeout" in mode or (cancels and not mode.startswith("cleanup_")):
                started.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    if not mode.startswith("late_next"):
                        raise
                    if mode.startswith("late_next_error"):
                        raise RuntimeError("late next failure") from None
                    return {"value": 9}
            raise StopAsyncIteration

        async def aclose(self):
            nonlocal closed, cleaned
            closed += 1
            try:
                if mode.startswith("cleanup_cancel"):
                    cleanup_started.set()
                    await cleanup_gate.wait()
                await asyncio.sleep(0)
                if "cleanup_error" in mode:
                    raise RuntimeError("private cleanup detail")
            finally:
                cleaned = True

    async def operation():
        nonlocal settled
        try:
            if late and not mode.startswith("late_next"):
                started.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    await asyncio.sleep(0.001)
                    if mode.startswith("late_reject"):
                        raise RuntimeError("late factory failure") from None
                    if mode.startswith("late_value"):
                        return {"value": 9}
            return Stream()
        finally:
            settled = True

    before = asyncio.all_tasks()
    task = asyncio.create_task(call(operation, CONTRACT, 0.02 if "timeout" in mode else 1, SCHEMA))
    if cancels:
        await (cleanup_started if mode.startswith("cleanup_") else started).wait()
        task.cancel()
        if mode.startswith("cleanup_"):
            # Cancellation while closing must not interrupt or repeat cleanup.
            await asyncio.sleep(0)
            task.cancel()
            cleanup_gate.set()
    try:
        outcome = await task
    except asyncio.CancelledError:
        escaped = True
        outcome = resolve_failure(CONTRACT, "cancelled", False, "upstream cancelled")
        outcome["items"] = []
    assert not (asyncio.all_tasks() - before), "operation or cleanup task was orphaned"
    return dict(
        outcome=outcome,
        escaped=escaped,
        acquired=acquired,
        closed=closed,
        cleaned=cleaned,
        settled=settled,
        reads=reads,
    )


def typescript_case(mode, runtime=None):
    node = shutil.which("node")
    assert node is not None, "Node.js 22.6+ is required for lifecycle checks"
    runtime = runtime or ROOT / "src/mcpforge/failure/runtime_ts.ts"
    harness = ROOT / "tests/failure/lifecycle_cases.ts"
    program = (
        f"import {{ callOperation }} from {json.dumps(runtime.as_uri())};\n"
        f"import {{ lifecycleCase }} from {json.dumps(harness.as_uri())};\n"
        "const unhandled = [];\n"
        "process.on('unhandledRejection', (error) => unhandled.push(String(error)));\n"
        f"const result = await lifecycleCase(callOperation, {json.dumps(mode)});\n"
        "await new Promise((resolve) => setTimeout(resolve, 5));\n"
        "process.stdout.write(JSON.stringify({ ...result, unhandled }));\n"
    )
    completed = subprocess.run(
        [node, "--unhandled-rejections=strict", "--input-type=module", "-e", program],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result.pop("unhandled") == []
    return result


def assert_lifecycle(mode, result):
    no_stream = mode.startswith(("late_value", "late_reject"))
    assert result["acquired"] == result["closed"] == (0 if no_stream else 1)
    assert result["cleaned"] is not no_stream
    assert result["settled"] is True
    assert result["escaped"] is ("cancel" in mode)
    if mode.startswith("late_") and not mode.startswith("late_next"):
        assert result["reads"] == 0
    else:
        assert result["reads"] == 2
    outcome = result["outcome"]
    if mode == "success":
        assert outcome == {"status": "complete", "failure": None, "items": [{"value": 1}]}
        return
    kind = (
        "cancelled"
        if "cancel" in mode
        else "timeout"
        if "timeout" in mode
        else "malformed"
        if mode == "malformed"
        else "upstream_error"
    )
    partial = kind != "cancelled" and (not mode.startswith("late_") or "late_next" in mode)
    assert outcome["failure"]["kind"] == kind
    assert outcome["status"] == ("incomplete" if partial else "failed")
    assert outcome["failure"]["retryable"] is (kind in {"timeout", "upstream_error"})
    assert outcome["failure"]["partial_result"] is partial
    assert outcome["items"] == ([{"value": 1}] if partial else [])


@pytest.mark.parametrize("mode", CASES)
@pytest.mark.asyncio
async def test_python_lifecycle_table(mode):
    assert_lifecycle(mode, await python_case(mode))


@pytest.mark.parametrize("mode", CASES)
def test_typescript_lifecycle_table(mode):
    assert_lifecycle(mode, typescript_case(mode))


@pytest.mark.parametrize("mode", CASES)
def test_lifecycle_outcomes_match_between_runtimes(mode):
    assert typescript_case(mode) == asyncio.run(python_case(mode))


@pytest.mark.parametrize("server_type", ("python-single", "python-multi", "typescript"))
def test_codegen_vends_canonical_runtime(tmp_path, server_type):
    plan = ServerPlan(
        name="Lifecycle",
        description="Lifecycle probes",
        tools=[ToolDef(name="probe", description="Probe", params=[])],
    )
    generate_server(plan, tmp_path, server_type)
    runtime = ROOT / "src/mcpforge/failure"
    if server_type == "typescript":
        vendored = tmp_path / "failureRuntime.ts"
        assert vendored.read_bytes() == (runtime / "runtime_ts.ts").read_bytes()
        for mode in ("late_factory_timeout", "late_factory_cancel_cleanup_error"):
            assert_lifecycle(mode, typescript_case(mode, vendored))
    else:
        source = tmp_path / (
            "server.py" if server_type == "python-single" else "failure_runtime.py"
        )
        canonical = (runtime / "runtime_py.py").read_text()
        if server_type == "python-single":
            assert source.read_text().startswith(canonical.rstrip())
        else:
            assert source.read_text() == canonical
        namespace = {"__name__": "lifecycle_probe"}
        # Exercise the embedded/copied runtime without starting an MCP service.
        exec(compile(source.read_text(), str(source), "exec"), namespace)
        mode = "cancel_cleanup_error"
        assert_lifecycle(mode, asyncio.run(python_case(mode, namespace["call_operation"])))

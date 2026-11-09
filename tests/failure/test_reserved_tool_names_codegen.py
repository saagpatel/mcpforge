"""Generated handlers keep internal names separate from public tool names."""

import asyncio
import importlib.util
import json
import shutil
import subprocess
import sys

import pytest

from mcpforge.failure.codegen import generate_server
from mcpforge.failure.fixtures import _run_generated_typescript, load_upstreams
from mcpforge.models import ServerPlan, ToolDef

RESERVED_NAMES = (
    "mcp",
    "call_upstream",
    "handle_upstream",
    "call_operation",
    "__proto__",
    "constructor",
    "prototype",
    "hasOwnProperty",
)


def _python_identifier(name: str) -> str:
    return name.strip("_") or "tool"


def _plan(name: str) -> ServerPlan:
    return ServerPlan(
        name="Reserved names",
        description="Exercise public tool names that overlap with runtime symbols.",
        tools=[ToolDef(name=name, description="Return a fixture result.", params=[])],
    )


def _success_descriptor() -> dict:
    return {
        "script": [{"emit": {"ok": True}}],
        "response_schema": {"type": "object"},
        "contract": {"retryable": False, "partial_result_allowed": False},
    }


def _load_module(name: str, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _clear_tools_modules():
    for module_name in list(sys.modules):
        if module_name == "tools" or module_name.startswith("tools."):
            sys.modules.pop(module_name, None)


@pytest.mark.parametrize("tool_name", RESERVED_NAMES)
@pytest.mark.parametrize("server_type", ("python-single", "python-multi"))
def test_python_reserved_tool_names_import_and_call(tmp_path, tool_name, server_type):
    out = tmp_path / server_type
    generate_server(_plan(tool_name), out, server_type)
    _clear_tools_modules()
    sys.path.insert(0, str(out))
    try:
        server_module = _load_module(f"generated_{server_type}_{tool_name}", out / "server.py")
        assert server_module.mcp is not None
        if server_type == "python-single":
            handler = server_module.TOOL_HANDLERS[tool_name]
        else:
            identifier = _python_identifier(tool_name)
            module = _load_module(
                f"generated_tool_{identifier}", out / "tools" / f"{identifier}.py"
            )
            handler = getattr(module, f"_tool_{identifier}")
        result = asyncio.run(handler(_success_descriptor()))
        assert result["status"] == "complete"
        assert result["items"] == [{"ok": True}]
    finally:
        sys.path.remove(str(out))
        identifier = _python_identifier(tool_name)
        for module_name in (
            f"generated_{server_type}_{tool_name}",
            f"generated_tool_{tool_name}",
            f"generated_tool_{identifier}",
        ):
            sys.modules.pop(module_name, None)
        _clear_tools_modules()


@pytest.mark.parametrize("tool_name", RESERVED_NAMES)
def test_typescript_reserved_tool_names_are_callable(tmp_path, tool_name):
    out = tmp_path / tool_name
    generate_server(_plan(tool_name), out, "typescript")
    descriptor = load_upstreams()[0]
    descriptor["contract"] = _plan(tool_name).tools[0].failure_contract or descriptor["contract"]
    descriptor["response_schema"] = {"type": "object"}
    descriptor["script"] = [{"emit": {"ok": True}}]

    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for generated TypeScript checks")
    server_uri = json.dumps((out / "server.ts").as_uri())
    inspect_maps = (
        "import { FAILURE_CONTRACTS, TOOL_HANDLERS } from "
        f"{server_uri};\n"
        f"const name = {json.dumps(tool_name)};\n"
        "process.stdout.write(JSON.stringify({ contracts: Object.keys(FAILURE_CONTRACTS), "
        "handlers: Object.keys(TOOL_HANDLERS), "
        "hasContract: Object.hasOwn(FAILURE_CONTRACTS, name), "
        "hasHandler: Object.hasOwn(TOOL_HANDLERS, name) }));"
    )
    completed = subprocess.run(
        [node, "--input-type=module", "-e", inspect_maps],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "contracts": [tool_name],
        "handlers": [tool_name],
        "hasContract": True,
        "hasHandler": True,
    }

    assert _run_generated_typescript(out, descriptor) == {
        "status": "complete",
        "failure": None,
        "items": [{"ok": True}],
    }
    generated = (out / "server.ts").read_text(encoding="utf-8")
    assert "Object.fromEntries([" in generated


@pytest.mark.parametrize("server_type", ("python-single", "python-multi"))
def test_generated_python_handler_runs_operation_cases(tmp_path, server_type):
    out = tmp_path / server_type
    generate_server(_plan("call_operation"), out, server_type)
    _clear_tools_modules()
    sys.path.insert(0, str(out))
    try:
        server_module = _load_module(f"operation_{server_type}", out / "server.py")
        if server_type == "python-single":
            handler = server_module.TOOL_HANDLERS["call_operation"]
        else:
            module = _load_module("operation_tool", out / "tools" / "call_operation.py")
            handler = module._tool_call_operation

        async def success():
            return {"ok": True}

        success_result = asyncio.run(handler(success, response_schema={"type": "object"}))
        assert success_result["status"] == "complete"

        async def malformed():
            return "wrong type"

        malformed_result = asyncio.run(handler(malformed, response_schema={"type": "object"}))
        assert malformed_result["failure"]["kind"] == "malformed"

        async def timeout():
            await asyncio.Event().wait()

        timeout_result = asyncio.run(handler(timeout, timeout_s=0.01))
        assert timeout_result["failure"]["kind"] == "timeout"

        async def cancelled_call():
            started = asyncio.Event()

            async def waiting_operation():
                started.set()
                await asyncio.Event().wait()

            task = asyncio.create_task(handler(waiting_operation))
            await started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        asyncio.run(cancelled_call())
    finally:
        sys.path.remove(str(out))
        sys.modules.pop(f"operation_{server_type}", None)
        sys.modules.pop("operation_tool", None)
        _clear_tools_modules()


@pytest.mark.parametrize("mode", ("success", "malformed", "timeout", "cancellation"))
def test_generated_typescript_handler_runs_operation_cases(tmp_path, mode):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for generated TypeScript operation checks")
    out = tmp_path / "typescript"
    generate_server(_plan("call_operation"), out, "typescript")
    runner = out / "run_operation.ts"
    runner.write_text(
        """import { TOOL_HANDLERS } from './server.ts';
const mode = process.argv[2];
const controller = new AbortController();
let cancellationOutcome;
const operation = async (signal: AbortSignal) => {
  if (mode === 'timeout' || mode === 'cancellation') {
    await new Promise<never>((_resolve, reject) => {
      signal.addEventListener('abort', () => reject(new Error('aborted')), { once: true });
    });
  }
  return mode === 'malformed' ? 'wrong type' : { ok: true };
};
const call = TOOL_HANDLERS['call_operation'](operation, mode === 'timeout' ? 10 : 1000,
  { type: 'object' }, {
    signal: mode === 'cancellation' ? controller.signal : undefined,
    onCancelled: (outcome) => { cancellationOutcome = outcome; },
  });
if (mode === 'cancellation') {
  setTimeout(() => controller.abort(), 5);
  try { await call; } catch { process.stdout.write(JSON.stringify(cancellationOutcome)); }
} else {
  process.stdout.write(JSON.stringify(await call));
}
""",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [node, str(runner), mode], capture_output=True, text=True, timeout=3, check=False
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    if mode == "success":
        assert result["status"] == "complete"
    elif mode == "cancellation":
        assert result["failure"]["kind"] == "cancelled"
    else:
        assert result["failure"]["kind"] == mode

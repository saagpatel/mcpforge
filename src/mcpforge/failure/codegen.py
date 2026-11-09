"""Deterministic writers for failure-aware generated server shells."""

from __future__ import annotations

import json
import keyword
import re
import shutil
from pathlib import Path
from typing import Literal

from mcpforge.contracts import default_contract
from mcpforge.models import ServerPlan

ServerType = Literal["python-single", "python-multi", "typescript"]


def _contracts(plan: ServerPlan) -> dict[str, dict[str, bool]]:
    return {
        tool.name: (tool.failure_contract or default_contract(tool)).model_dump()
        for tool in plan.tools
    }


def _identifier(name: str) -> str:
    value = re.sub(r"\W+", "_", name, flags=re.ASCII).strip("_") or "tool"
    if value[0].isdigit():
        value = f"tool_{value}"
    if keyword.iskeyword(value):
        value += "_tool"
    return value


def _tool_identifiers(plan: ServerPlan) -> dict[str, str]:
    identifiers = {tool.name: _identifier(tool.name) for tool in plan.tools}
    if len(set(identifiers.values())) != len(identifiers):
        raise ValueError("tool names collide after conversion to Python identifiers")
    return identifiers


def _runtime_path(name: str) -> Path:
    path = Path(__file__).with_name(name)
    if not path.is_file():
        raise FileNotFoundError(f"failure runtime not found: {path}")
    return path


def _python_handlers(plan: ServerPlan) -> str:
    contracts = _contracts(plan)
    identifiers = _tool_identifiers(plan)
    contract_json = json.dumps(contracts, sort_keys=True, separators=(",", ":"))
    lines = [
        "\n# Generated per-tool failure contracts.",
        f"FAILURE_CONTRACTS = __import__('json').loads({contract_json!r})",
        f"mcp = FastMCP({plan.name!r})",
        "",
        "async def _failure_handle_upstream(",
        "    operation, contract=None, timeout_s=0.05, response_schema=None",
        "):",
        '    """Run one upstream operation or descriptor under its failure contract."""',
        "    selected = contract or next(iter(FAILURE_CONTRACTS.values()), {",
        "        'retryable': False, 'partial_result_allowed': False})",
        "    return await call_upstream(operation, selected, timeout_s, response_schema)",
        "",
        "TOOL_HANDLERS = {}",
    ]
    for tool in plan.tools:
        ident = f"_tool_{identifiers[tool.name]}"
        lines.extend(
            [
                f"async def {ident}(operation, timeout_s=0.05, response_schema=None):",
                '    """Run this tool operation and return its outcome envelope."""',
                "    return await _failure_handle_upstream(",
                f"        operation, FAILURE_CONTRACTS[{tool.name!r}], timeout_s,",
                "        response_schema",
                "    )",
                f"mcp.tool(name={tool.name!r})({ident})",
                f"TOOL_HANDLERS[{tool.name!r}] = {ident}",
                "",
            ]
        )
    return "\n".join(lines)


def _write_python_single(plan: ServerPlan, out: Path) -> None:
    runtime = _runtime_path("runtime_py.py").read_text(encoding="utf-8")
    source = (
        runtime.rstrip()
        + "\n\nfrom fastmcp import FastMCP\n"
        + _python_handlers(plan)
        + "\nif __name__ == '__main__':\n    mcp.run(transport='streamable-http')\n"
    )
    (out / "server.py").write_text(source, encoding="utf-8")


def _write_python_multi(plan: ServerPlan, out: Path) -> None:
    shutil.copyfile(_runtime_path("runtime_py.py"), out / "failure_runtime.py")
    identifiers = _tool_identifiers(plan)
    imports = "\n".join(
        f"from tools.{identifiers[tool.name]} import _tool_{identifiers[tool.name]}"
        for tool in plan.tools
    )
    registrations = "\n".join(
        f"mcp.tool(name={tool.name!r})(_tool_{identifiers[tool.name]})" for tool in plan.tools
    )
    encoded_contracts = json.dumps(
        json.dumps(_contracts(plan), sort_keys=True, separators=(",", ":"))
    )
    (out / "server.py").write_text(
        '"""Generated failure-aware Python server shell."""\n\n'
        "from fastmcp import FastMCP\n"
        "from failure_runtime import call_upstream\n\n"
        "import json\n\n"
        f"{imports}\n\n"
        "FAILURE_CONTRACTS = "
        f"json.loads({encoded_contracts})\n"
        f"mcp = FastMCP({plan.name!r})\n\n"
        "async def _failure_handle_upstream(\n"
        "    operation, contract=None, timeout_s=0.05, response_schema=None\n"
        "):\n"
        "    selected = contract or next(iter(FAILURE_CONTRACTS.values()), {\n"
        "        'retryable': False, 'partial_result_allowed': False})\n"
        "    return await call_upstream(\n"
        "        operation, selected, timeout_s, response_schema\n"
        "    )\n\n"
        f"{registrations}\n\n"
        "if __name__ == '__main__':\n"
        "    mcp.run(transport='streamable-http')\n",
        encoding="utf-8",
    )
    tools_dir = out / "tools"
    tools_dir.mkdir(exist_ok=True)
    (tools_dir / "__init__.py").write_text('"""Generated tool handlers."""\n', encoding="utf-8")
    for tool in plan.tools:
        ident = f"_tool_{identifiers[tool.name]}"
        contract = _contracts(plan)[tool.name]
        encoded_contract = json.dumps(json.dumps(contract, sort_keys=True, separators=(",", ":")))
        (tools_dir / f"{identifiers[tool.name]}.py").write_text(
            "from failure_runtime import call_upstream\n\n"
            "import json\n\n"
            f"FAILURE_CONTRACT = json.loads({encoded_contract})\n\n"
            f"async def {ident}(operation, timeout_s=0.05, response_schema=None):\n"
            "    return await call_upstream(\n"
            "        operation, FAILURE_CONTRACT, timeout_s, response_schema\n"
            "    )\n",
            encoding="utf-8",
        )


def _write_typescript(plan: ServerPlan, out: Path) -> None:
    shutil.copyfile(_runtime_path("runtime_ts.ts"), out / "failureRuntime.ts")
    contracts = json.dumps(_contracts(plan), sort_keys=True, separators=(",", ":"))
    (out / "server.ts").write_text(
        "// Generated handler shell; MCP SDK wiring may import these handlers.\n"
        "import { callOperation, callUpstream, type Operation, type Upstream, "
        "type FailureContract, type RuntimeOptions } "
        "from './failureRuntime.ts';\n\n"
        f"export const FAILURE_CONTRACTS = {contracts} as const;\n"
        "const isOperation = (value: Upstream | Operation): value is Operation =>\n"
        "  typeof value === 'function' || (typeof value === 'object' &&\n"
        "    Symbol.asyncIterator in value);\n\n"
        "export const TOOL_HANDLERS = {\n"
        + "\n".join(
            f"  {json.dumps(tool.name)}: (\n"
            "    operation: Upstream | Operation,\n"
            "    timeoutMs = 50,\n"
            "    responseSchema: Record<string, unknown> = {},\n"
            "    options: RuntimeOptions = {},\n"
            "  ) => isOperation(operation)\n"
            "    ? callOperation(operation, "
            f"FAILURE_CONTRACTS[{json.dumps(tool.name)}] "
            "as FailureContract, timeoutMs, responseSchema, options)\n"
            "    : callUpstream(operation as Upstream, "
            f"FAILURE_CONTRACTS[{json.dumps(tool.name)}] "
            "as FailureContract, timeoutMs, options),"
            for tool in plan.tools
        )
        + "\n};\n",
        encoding="utf-8",
    )
    (out / "run_fixture.ts").write_text(
        """import { readFile } from 'node:fs/promises';
import { TOOL_HANDLERS, FAILURE_CONTRACTS } from './server.ts';

const path = process.argv[2];
if (!path) throw new Error('usage: node run_fixture.ts <descriptor.json>');
const upstream = JSON.parse(await readFile(path, 'utf8'));
const toolName = Object.keys(FAILURE_CONTRACTS)[0];
let cancellationOutcome;
let result;
try {
    result = await TOOL_HANDLERS[toolName](upstream, 50, {}, {
    onCancelled: (outcome) => { cancellationOutcome = outcome; },
  });
} catch (error) {
  if (!cancellationOutcome) throw error;
  result = cancellationOutcome;
}
process.stdout.write(JSON.stringify(result) + '\\n');
""",
        encoding="utf-8",
    )


def _write_readme(plan: ServerPlan, out: Path) -> None:
    from mcpforge.failure.docs import failure_readme_section

    (out / "README.md").write_text(
        f"# {plan.name}\n\n" + failure_readme_section().rstrip() + "\n",
        encoding="utf-8",
    )


def generate_server(plan: ServerPlan, output_dir: str | Path, server_type: ServerType) -> Path:
    """Emit one deterministic failure-aware server shell and its contract manifest."""
    if server_type not in {"python-single", "python-multi", "typescript"}:
        raise ValueError(f"unsupported server type: {server_type}")
    _tool_identifiers(plan)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest = _contracts(plan)
    (out / "failure_contracts.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    if server_type == "python-single":
        _write_python_single(plan, out)
    elif server_type == "python-multi":
        _write_python_multi(plan, out)
    else:
        _write_typescript(plan, out)
    _write_readme(plan, out)
    return out

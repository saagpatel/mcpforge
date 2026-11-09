"""Deterministic runners for the packaged upstream failure scenarios."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from mcpforge.failure.codegen import generate_server
from mcpforge.failure.runtime_py import call_upstream
from mcpforge.models import ServerPlan, ToolDef

UPSTREAMS_DIR = Path(__file__).with_name("upstreams")
SERVER_TYPES = ("python-single", "python-multi", "typescript")


def load_upstreams() -> list[dict[str, Any]]:
    """Load the sorted, packaged fixture descriptors."""
    upstreams = [
        json.loads(path.read_text(encoding="utf-8")) for path in UPSTREAMS_DIR.glob("*.json")
    ]
    return sorted(upstreams, key=lambda upstream: upstream["name"])


def normalize_result(result: dict[str, Any]) -> dict[str, Any]:
    """Keep only the stable MCP outcome envelope fields."""
    failure = result.get("failure")
    normalized_failure = None
    if failure is not None:
        normalized_failure = {
            "kind": failure["kind"],
            "retryable": failure["retryable"],
            "partial_result": failure["partial_result"],
            "detail": failure["detail"],
        }
    return {
        "status": result["status"],
        "failure": normalized_failure,
        "items": result.get("items", []),
    }


async def _run_python(upstream: dict[str, Any]) -> dict[str, Any]:
    descriptor = json.loads(json.dumps(upstream))
    try:
        result = await call_upstream(
            descriptor,
            descriptor["contract"],
            timeout_s=0.025,
        )
    except asyncio.CancelledError:
        # MCP cancellation has no response. The fixture runner observes the
        # runtime's recorded envelope so cross-language semantics stay testable.
        result = descriptor.get("_cancelled_outcome")
        if result is None:
            raise AssertionError(
                "runtime re-raised cancellation without recording its fixture outcome"
            )
    return normalize_result(result)


def run_python_fixture(upstream: dict[str, Any]) -> dict[str, Any]:
    """Run one descriptor against the self-contained Python runtime."""
    return asyncio.run(_run_python(upstream))


def run_fixture(
    server_type: str,
    upstream: dict[str, Any],
    generated_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run one upstream fixture for a generated server type.

    Python variants use the exact vendored runtime implementation in-process.
    TypeScript uses the generated, dependency-free Node fixture runner. The
    generated directory is required for TypeScript because that runner is part
    of the server artifact.
    """
    if server_type not in SERVER_TYPES:
        raise ValueError(f"unsupported server type: {server_type}")
    tool_name = "fixture_tool"
    plan = ServerPlan(
        name="Failure Fixture",
        description="Synthetic upstream failure semantics fixture.",
        tools=[
            ToolDef(
                name=tool_name,
                description="Run one synthetic upstream descriptor.",
                params=[],
                failure_contract=upstream["contract"],
            )
        ],
    )
    if generated_dir is None:
        temp_context = tempfile.TemporaryDirectory(prefix="mcpforge-fixture-")
        out = Path(temp_context.name)
    else:
        temp_context = None
        out = Path(generated_dir)
    try:
        generate_server(plan, out, server_type)
        if server_type in {"python-single", "python-multi"}:
            result = _run_generated_python(out, server_type, tool_name, upstream)
            return normalize_result(result)
        return _run_generated_typescript(out, upstream)
    finally:
        if temp_context is not None:
            temp_context.cleanup()


def _run_generated_python(
    generated_dir: Path,
    server_type: str,
    tool_name: str,
    upstream: dict[str, Any],
) -> dict[str, Any]:
    module_name = f"mcpforge_fixture_{server_type.replace('-', '_')}"
    sys.path.insert(0, str(generated_dir))
    try:
        if server_type == "python-single":
            module_path = generated_dir / "server.py"
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"could not load generated Python server: {module_path}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            handler = module.TOOL_HANDLERS[tool_name]
        else:
            module_path = generated_dir / "tools" / f"{tool_name}.py"
            spec = importlib.util.spec_from_file_location(f"{module_name}_tool", module_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"could not load generated Python tool: {module_path}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            handler = getattr(module, tool_name)
        descriptor = json.loads(json.dumps(upstream))
        try:
            result = asyncio.run(handler(descriptor, timeout_s=0.025))
        except asyncio.CancelledError:
            result = descriptor.get("_cancelled_outcome")
            if result is None:
                raise AssertionError(
                    "generated handler re-raised cancellation without recording its outcome"
                )
        return result
    finally:
        sys.path.remove(str(generated_dir))


def _run_generated_typescript(generated_dir: Path, upstream: dict[str, Any]) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        raise RuntimeError(
            "TypeScript fixture checks require Node.js 22.6 or later, but node was not found"
        )
    runner = generated_dir / "run_fixture.ts"
    if not runner.is_file():
        raise FileNotFoundError(f"generated TypeScript fixture runner not found: {runner}")
    with tempfile.TemporaryDirectory(prefix="mcpforge-fixture-") as temp_dir:
        descriptor_path = Path(temp_dir) / "upstream.json"
        descriptor_path.write_text(json.dumps(upstream), encoding="utf-8")
        completed = subprocess.run(
            [node, str(runner), str(descriptor_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    if completed.returncode:
        raise RuntimeError(
            f"TypeScript fixture runner failed ({completed.returncode}): {completed.stderr.strip()}"
        )
    try:
        return normalize_result(json.loads(completed.stdout))
    except (json.JSONDecodeError, KeyError) as exc:
        raise RuntimeError(
            "TypeScript fixture runner did not print a valid outcome envelope"
        ) from exc


def run_all_fixtures(
    server_type: str,
    generated_dir: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Run every upstream descriptor and return outcomes keyed by name."""
    return {
        upstream["name"]: run_fixture(server_type, upstream, generated_dir)
        for upstream in load_upstreams()
    }


def assert_expected(upstream: dict[str, Any], actual: dict[str, Any]) -> None:
    """Raise an assertion with fixture context when an expectation differs."""
    expected = normalize_result(upstream["expect"])
    normalized = normalize_result(actual)
    if normalized != expected:
        raise AssertionError(
            f"{upstream['name']} expected {json.dumps(expected, sort_keys=True)}, "
            f"got {json.dumps(normalized, sort_keys=True)}"
        )


def run_and_assert_all(
    server_type: str,
    generated_dir: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Run all fixtures and compare each normalized result with its contract."""
    outcomes = run_all_fixtures(server_type, generated_dir)
    descriptors = {upstream["name"]: upstream for upstream in load_upstreams()}
    for name, outcome in outcomes.items():
        assert_expected(descriptors[name], outcome)
    return outcomes

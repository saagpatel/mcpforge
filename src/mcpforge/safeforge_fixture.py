"""Deterministic, offline SafeForge echo fixture generation."""

from __future__ import annotations

from datetime import datetime
from importlib.resources import files
from pathlib import Path

from mcpforge.forge_receipt import ForgeReceiptV0, build_forge_receipt
from mcpforge.generator import generate_server
from mcpforge.models import ServerPlan, ToolDef, ToolParam
from mcpforge.planner import extract_plan
from mcpforge.replay_client import ReplayClient
from mcpforge.test_generator import generate_tests
from mcpforge.validator import check_plan_conformance, validate_server
from mcpforge.writer import write_server

SAFEFORGE_ECHO_DESCRIPTION = (
    "A local read-only MCP server that returns the supplied message unchanged."
)


def build_safeforge_echo_plan() -> ServerPlan:
    """Return the recorded, explicitly annotated SafeForge echo plan."""
    return ServerPlan(
        name="SafeForge Echo",
        slug="safeforge-echo",
        description="Returns a supplied message unchanged without external access.",
        tools=[
            ToolDef(
                name="echo",
                description="Return the supplied message unchanged.",
                params=[
                    ToolParam(
                        name="message",
                        type="str",
                        description="Message to return unchanged.",
                    )
                ],
                return_type="dict",
                retry_safe=True,
                read_only_hint=True,
                destructive_hint=False,
                idempotent_hint=True,
                open_world_hint=False,
            )
        ],
        transport="stdio",
    )


def load_safeforge_echo_client() -> ReplayClient:
    """Return a replay client with no provider, credential, or network dependency."""
    assets = files("mcpforge").joinpath("safeforge_assets")
    server_code = assets.joinpath("server.py").read_text(encoding="utf-8")
    test_code = assets.joinpath("test_server.py").read_text(encoding="utf-8")
    return ReplayClient(build_safeforge_echo_plan(), [server_code, test_code])


async def generate_safeforge_echo_fixture(
    output_dir: Path,
    *,
    created_at: datetime,
    producer_revision: str,
    producer_dirty: bool,
) -> ForgeReceiptV0:
    """Generate and statically validate the fixture without installing or executing it."""
    client = load_safeforge_echo_client()
    plan = await extract_plan(SAFEFORGE_ECHO_DESCRIPTION, client, transport="stdio")
    server_code = await generate_server(plan, client)
    test_code = await generate_tests(plan, server_code, client)
    write_server(plan, server_code, test_code, output_dir)
    lock_bytes = files("mcpforge").joinpath("safeforge_assets", "uv.lock").read_bytes()
    (output_dir / "uv.lock").write_bytes(lock_bytes)

    warnings = check_plan_conformance(server_code, plan)
    if warnings:
        raise ValueError(f"SafeForge fixture does not conform to its plan: {warnings}")
    validation = await validate_server(output_dir, skip_execution=True, strict=True)
    return build_forge_receipt(
        receipt_id="safeforge-echo-v1",
        description=SAFEFORGE_ECHO_DESCRIPTION,
        plan=plan,
        output_dir=output_dir,
        validation=validation,
        created_at=created_at,
        producer_revision=producer_revision,
        producer_dirty=producer_dirty,
        provider="replay",
        model="safeforge-echo-v1",
        no_execute=True,
    )

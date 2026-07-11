#!/usr/bin/env python3
"""Replay the trusted SafeForge fixture through MCPAudit's public CLI."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mcpforge.forge_receipt import forge_receipt_json_schema
from mcpforge.safeforge_fixture import generate_safeforge_echo_fixture

_CREATED_AT = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
_PREINSTALL_STAGES = [
    "source.bind",
    "forge.plan",
    "forge.generate",
    "validate.static",
    "contract.preinstall",
    "audit.config",
]
_EXPECTED_STAGES = [
    *_PREINSTALL_STAGES,
    "sandbox.prepare",
    "sandbox.materialize",
    "audit.connected",
    "trust.grade",
    "runtime.policy.bind",
    "publication.dry_run",
    "receipt.finalize",
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the no-execute mcpforge to MCPAudit SafeForge handoff."
    )
    parser.add_argument(
        "--mcpaudit-repo",
        type=Path,
        required=True,
        help="MCPAudit checkout with an existing .venv; no dependency installation is attempted.",
    )
    args = parser.parse_args()
    return asyncio.run(_verify(args.mcpaudit_repo.resolve()))


async def _verify(mcpaudit_repo: Path) -> int:
    executable = mcpaudit_repo / ".venv" / "bin" / "mcp-audit"
    if not executable.is_file():
        raise SystemExit(f"existing MCPAudit executable is required: {executable}")

    with tempfile.TemporaryDirectory(prefix="safeforge-handoff-") as temporary:
        root = Path(temporary)
        artifact_root = root / "artifact"
        receipt = await generate_safeforge_echo_fixture(
            artifact_root,
            created_at=_CREATED_AT,
            producer_revision="safeforge-acceptance-fixture",
            producer_dirty=False,
        )
        if not receipt.generation.no_execute or receipt.validation.mode != "static-no-execute":
            raise SystemExit("fixture escaped the no-execute generation contract")

        schema_path = root / "forge-receipt-v0.schema.json"
        receipt_path = root / "forge-receipt-v0.json"
        schema_path.write_text(
            json.dumps(forge_receipt_json_schema(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        receipt_path.write_text(receipt.model_dump_json(indent=2), encoding="utf-8")

        command = [
            str(executable),
            "safeforge-preinstall",
            "--producer-schema",
            str(schema_path),
            "--receipt",
            str(receipt_path),
            "--artifact-root",
            str(artifact_root),
            "--run-id",
            "safeforge-echo-acceptance",
            "--created-at",
            _CREATED_AT.isoformat(),
            "--coordinator-revision",
            "safeforge-acceptance-fixture",
        ]
        first = _run(command)
        second = _run(command)
        if first.stdout != second.stdout:
            raise SystemExit("identical SafeForge CLI replays produced different JSON bytes")

        payload: dict[str, Any] = json.loads(first.stdout)
        if payload.get("accepted") is not True:
            raise SystemExit(f"SafeForge handoff was not accepted: {first.stdout}")
        manifest = payload.get("preinstall", {}).get("manifest", {})
        stages = [stage.get("stage_id") for stage in manifest.get("stages", [])]
        if stages != _PREINSTALL_STAGES:
            raise SystemExit(f"unexpected SafeForge stage sequence: {stages}")
        audit_report = payload.get("preinstall", {}).get("audit_report", {})
        if audit_report.get("hostname") != "<canonical-host>":
            raise SystemExit("SafeForge audit report was not canonicalized")

        runtime_command = [*command]
        runtime_command[1] = "safeforge-run"
        runtime_first = _run(runtime_command, timeout=120)
        runtime_second = _run(runtime_command, timeout=120)
        runtime_payload: dict[str, Any] = json.loads(runtime_first.stdout)
        replay_payload: dict[str, Any] = json.loads(runtime_second.stdout)
        if runtime_payload.get("accepted") is not True:
            raise SystemExit(f"SafeForge runtime was not accepted: {runtime_first.stdout}")
        forbidden_output = (
            str(Path.home()),
            "safeforge-runtime-",
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
        )
        if any(item in runtime_first.stdout for item in forbidden_output):
            raise SystemExit("SafeForge runtime output leaked a private path or credential key")
        if runtime_payload.get("manifest") != replay_payload.get("manifest"):
            raise SystemExit(
                "identical SafeForge runtime replays produced different final manifests"
            )
        final_manifest = runtime_payload["manifest"]
        final_stages = [stage.get("stage_id") for stage in final_manifest.get("stages", [])]
        if final_stages != _EXPECTED_STAGES:
            raise SystemExit(f"unexpected SafeForge final stage sequence: {final_stages}")
        if final_manifest.get("run", {}).get("decision") != "eligible":
            raise SystemExit("SafeForge runtime did not finalize as eligible")
        sandbox = final_manifest.get("sandbox", {})
        if not sandbox.get("cleanup_verified") or sandbox.get("network") != "none":
            raise SystemExit("SafeForge runtime did not prove zero-egress cleanup")

        digest = hashlib.sha256(first.stdout.encode()).hexdigest()
        runtime_digest = hashlib.sha256(
            json.dumps(final_manifest, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        print(
            json.dumps(
                {
                    "accepted": True,
                    "output_sha256": f"sha256:{digest}",
                    "replays": 2,
                    "preinstall_stages": stages,
                    "runtime_manifest_sha256": f"sha256:{runtime_digest}",
                    "runtime_replays": 2,
                    "stages": final_stages,
                },
                sort_keys=True,
            )
        )
    return 0


def _run(command: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise SystemExit(
            f"SafeForge CLI failed with exit {result.returncode}: {result.stderr or result.stdout}"
        )
    return result


if __name__ == "__main__":
    raise SystemExit(main())

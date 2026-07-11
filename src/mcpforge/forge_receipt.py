"""Versioned, secret-minimizing evidence for an offline mcpforge generation."""

from __future__ import annotations

import ast
import hashlib
import json
import tomllib
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from mcpforge import __version__
from mcpforge.models import ServerPlan, ToolDef, ValidationResult

Digest = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
Identifier = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]*$")]
ToolName = Annotated[str, StringConstraints(pattern=r"^[A-Za-z_][A-Za-z0-9_.-]*$")]
EnvKey = Annotated[str, StringConstraints(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")]

_FIXTURE_ARTIFACT_PATHS = (
    ".env.example",
    "README.md",
    "config.json",
    "fastmcp.json",
    "pyproject.toml",
    "server.py",
    "test_server.py",
    "uv.lock",
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CheckState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    UNKNOWN = "unknown"


class ForgeProducerIdentity(_StrictModel):
    name: Literal["mcpforge"] = "mcpforge"
    version: str
    source: Literal["io.github.saagpatel/mcpforge"] = "io.github.saagpatel/mcpforge"
    revision: str
    dirty: bool
    executable: Literal["mcpforge"] = "mcpforge"


class ForgeSourceBinding(_StrictModel):
    kind: Literal["natural-language"] = "natural-language"
    server_id: Identifier
    description_digest: Digest
    transport: Literal["stdio", "streamable-http"]


class ForgeGenerationEvidence(_StrictModel):
    provider: str
    model: str
    no_execute: Literal[True] = True
    plan_digest: Digest
    required_env_keys: list[EnvKey] = Field(default_factory=list)


class ForgeLaunchConfig(_StrictModel):
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    url: str | None = None
    env_keys: list[EnvKey] = Field(default_factory=list)


class ForgeArtifactFile(_StrictModel):
    path: str
    media_type: str
    digest: Digest

    @model_validator(mode="after")
    def portable_path(self) -> ForgeArtifactFile:
        normalized = self.path.replace("\\", "/")
        parts = normalized.split("/")
        if normalized.startswith("/") or ":" in parts[0] or ".." in parts:
            raise ValueError("artifact path must be portable and relative")
        return self


class ForgeArtifactInventory(_StrictModel):
    tree_digest: Digest
    files: list[ForgeArtifactFile] = Field(min_length=1)
    dependency_manifest_digest: Digest
    lockfile_digest: Digest | None = None
    package_identities: list[str] = Field(default_factory=list)


class ForgeToolAnnotations(_StrictModel):
    read_only: bool
    destructive: bool
    idempotent: bool
    open_world: bool


class ForgeDeclaredCapabilities(_StrictModel):
    permissions: list[str] = Field(default_factory=list)
    auth_scopes: list[str] = Field(default_factory=list)
    data_zones: list[str] = Field(default_factory=list)
    egress_destinations: list[str] = Field(default_factory=list)
    credential_keys: list[EnvKey] = Field(default_factory=list)


class ForgeToolBOMEntry(_StrictModel):
    tool_id: str
    name: ToolName
    description_digest: Digest
    input_schema_digest: Digest
    output_schema_digest: Digest
    implementation_digest: Digest
    observed_capabilities: list[Literal["filesystem", "network"]] = Field(default_factory=list)
    observed_egress_destinations: list[str] = Field(default_factory=list)
    annotations: ForgeToolAnnotations
    declared: ForgeDeclaredCapabilities


class ForgeValidationEvidence(_StrictModel):
    mode: Literal["static-no-execute"] = "static-no-execute"
    syntax: CheckState
    security: CheckState
    lint: CheckState
    import_check: Literal["skipped"] = "skipped"
    tests: Literal["skipped"] = "skipped"
    security_warning_count: int = Field(ge=0)
    eligible_for_preinstall_audit: bool


class ForgeReceiptV0(_StrictModel):
    receipt_id: Identifier
    receipt_version: Literal["0.1.0"] = "0.1.0"
    created_at: datetime
    producer: ForgeProducerIdentity
    source: ForgeSourceBinding
    generation: ForgeGenerationEvidence
    launch: ForgeLaunchConfig | None = None
    artifact: ForgeArtifactInventory
    toolbom: list[ForgeToolBOMEntry] = Field(min_length=1)
    validation: ForgeValidationEvidence
    limitations: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def bound_identity_and_inventory(self) -> ForgeReceiptV0:
        paths = [item.path for item in self.artifact.files]
        if len(paths) != len(set(paths)):
            raise ValueError("artifact paths must be unique")
        tool_ids = [item.tool_id for item in self.toolbom]
        if len(tool_ids) != len(set(tool_ids)):
            raise ValueError("tool IDs must be unique")
        for tool in self.toolbom:
            expected = f"{self.source.server_id}#{tool.name}"
            if tool.tool_id != expected:
                raise ValueError(f"tool_id {tool.tool_id!r} must equal {expected!r}")
        if self.launch is not None:
            if self.source.transport == "stdio" and (
                not self.launch.command or self.launch.url is not None
            ):
                raise ValueError("stdio launch requires command and forbids url")
            if self.source.transport == "streamable-http" and (
                self.launch.command is not None or not self.launch.url
            ):
                raise ValueError("streamable-http launch requires url and forbids command")
        passed = all(
            state is CheckState.PASSED
            for state in (self.validation.syntax, self.validation.security, self.validation.lint)
        )
        if self.validation.eligible_for_preinstall_audit != passed:
            raise ValueError("preinstall eligibility must match static validation states")
        return self


def build_forge_receipt(
    *,
    receipt_id: str,
    description: str,
    plan: ServerPlan,
    output_dir: Path,
    validation: ValidationResult,
    created_at: datetime,
    producer_revision: str,
    producer_dirty: bool,
    provider: str,
    model: str,
    no_execute: bool,
) -> ForgeReceiptV0:
    """Build a receipt without installing dependencies or executing generated code."""
    if not no_execute:
        raise ValueError("ForgeReceiptV0 requires the no-execute generation path")
    files = _inventory_fixture_files(output_dir)
    plan_payload = plan.model_dump(mode="json")
    security_errors = [item for item in validation.errors if item.startswith("DANGEROUS:")]
    security_warnings = [item for item in validation.errors if item.startswith("WARNING:")]
    syntax = CheckState.PASSED if validation.syntax_ok else CheckState.FAILED
    security = CheckState.FAILED if security_errors or security_warnings else CheckState.PASSED
    lint = CheckState.PASSED if not validation.lint_errors else CheckState.FAILED

    return ForgeReceiptV0(
        receipt_id=receipt_id,
        created_at=created_at,
        producer=ForgeProducerIdentity(
            version=__version__, revision=producer_revision, dirty=producer_dirty
        ),
        source=ForgeSourceBinding(
            server_id=plan.slug,
            description_digest=_digest_bytes(description.encode()),
            transport=plan.transport,
        ),
        generation=ForgeGenerationEvidence(
            provider=provider,
            model=model,
            plan_digest=_digest_json(plan_payload),
            required_env_keys=sorted(plan.env_vars),
        ),
        launch=_launch_config(output_dir / "config.json", plan.slug),
        artifact=ForgeArtifactInventory(
            tree_digest=_digest_json([item.model_dump(mode="json") for item in files]),
            files=files,
            dependency_manifest_digest=_file_digest(output_dir / "pyproject.toml"),
            lockfile_digest=_file_digest(output_dir / "uv.lock"),
            package_identities=_package_identities(output_dir / "pyproject.toml"),
        ),
        toolbom=[_toolbom_entry(plan, tool, output_dir / "server.py") for tool in plan.tools],
        validation=ForgeValidationEvidence(
            syntax=syntax,
            security=security,
            lint=lint,
            security_warning_count=len(security_warnings),
            eligible_for_preinstall_audit=all(
                state is CheckState.PASSED for state in (syntax, security, lint)
            ),
        ),
        limitations=[
            "Import and generated tests were skipped by the no-execute fixture path.",
            "This receipt is generation evidence, not an audit, grade, or publication approval.",
        ],
    )


def _inventory_fixture_files(output_dir: Path) -> list[ForgeArtifactFile]:
    root = output_dir.resolve()
    actual = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    )
    expected = list(_FIXTURE_ARTIFACT_PATHS)
    if actual != expected:
        raise ValueError(f"fixture artifact set differs: expected {expected}, got {actual}")

    files: list[ForgeArtifactFile] = []
    for relative in expected:
        path = root / relative
        if path.is_symlink():
            raise ValueError(f"fixture artifact must not be a symlink: {relative}")
        files.append(
            ForgeArtifactFile(
                path=relative,
                media_type=_media_type(relative),
                digest=_file_digest(path),
            )
        )
    return files


def _toolbom_entry(plan: ServerPlan, tool: ToolDef, server_path: Path) -> ForgeToolBOMEntry:
    hints = (
        tool.read_only_hint,
        tool.destructive_hint,
        tool.idempotent_hint,
        tool.open_world_hint,
    )
    if any(value is None for value in hints):
        raise ValueError(f"tool {tool.name!r} requires explicit SafeForge annotation hints")
    implementation_digest, observed, destinations, dynamic_egress = _observe_tool_code(
        server_path, tool.name
    )
    declared_destinations = {_normalize_destination(item) for item in tool.egress_destinations}
    if "filesystem" in observed and "filesystem" not in tool.permissions:
        raise ValueError(
            f"tool {tool.name!r} uses filesystem capability without the filesystem permission"
        )
    if "network" in observed:
        undeclared = set(destinations) - declared_destinations
        if undeclared:
            raise ValueError(
                f"tool {tool.name!r} uses undeclared egress destinations: {sorted(undeclared)}"
            )
        if dynamic_egress and not tool.open_world_hint:
            raise ValueError(
                f"tool {tool.name!r} uses dynamic network egress but open_world_hint is false"
            )
        if not destinations and not tool.open_world_hint:
            raise ValueError(f"tool {tool.name!r} uses network capability without declared egress")
    credential_keys = [tool.auth_env_var] if tool.auth_env_var else []
    return ForgeToolBOMEntry(
        tool_id=f"{plan.slug}#{tool.name}",
        name=tool.name,
        description_digest=_digest_bytes(tool.description.encode()),
        input_schema_digest=_digest_json(_runtime_input_schema(tool)),
        output_schema_digest=_digest_json(_runtime_output_schema(tool)),
        implementation_digest=implementation_digest,
        observed_capabilities=observed,
        observed_egress_destinations=destinations,
        annotations=ForgeToolAnnotations(
            read_only=bool(tool.read_only_hint),
            destructive=bool(tool.destructive_hint),
            idempotent=bool(tool.idempotent_hint),
            open_world=bool(tool.open_world_hint),
        ),
        declared=ForgeDeclaredCapabilities(
            permissions=sorted(tool.permissions),
            auth_scopes=sorted(tool.auth_scopes),
            data_zones=sorted(tool.data_zones),
            egress_destinations=sorted(tool.egress_destinations),
            credential_keys=credential_keys,
        ),
    )


_NETWORK_MODULES = {
    "aiohttp",
    "asyncpg",
    "gql",
    "httpx",
    "motor",
    "redis",
    "requests",
    "websockets",
}
_FILESYSTEM_METHODS = {
    "chmod",
    "glob",
    "iterdir",
    "mkdir",
    "read_bytes",
    "read_text",
    "rename",
    "replace",
    "rglob",
    "rmdir",
    "touch",
    "unlink",
    "write_bytes",
    "write_text",
}


def _observe_tool_code(
    server_path: Path, tool_name: str
) -> tuple[Digest, list[Literal["filesystem", "network"]], list[str], bool]:
    tree = ast.parse(server_path.read_text(encoding="utf-8"))
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split(".")[0]] = alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                aliases[alias.asname or alias.name] = node.module.split(".")[0]

    function = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == tool_name
        ),
        None,
    )
    if function is None:
        raise ValueError(f"generated implementation for tool {tool_name!r} is missing")

    network_names = {name for name, module in aliases.items() if module in _NETWORK_MODULES}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if value is None or not any(
            isinstance(item, ast.Name) and item.id in network_names for item in ast.walk(value)
        ):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        network_names.update(target.id for target in targets if isinstance(target, ast.Name))

    uses_network = any(
        isinstance(node, ast.Name) and node.id in network_names for node in ast.walk(tree)
    )
    destinations = sorted(
        {
            host
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            for host in [_literal_destination(node.value)]
            if host is not None
        }
    )
    uses_filesystem = any(
        isinstance(node, ast.Call)
        and (
            isinstance(node.func, ast.Name)
            and node.func.id == "open"
            or isinstance(node.func, ast.Attribute)
            and node.func.attr in _FILESYSTEM_METHODS
        )
        for node in ast.walk(tree)
    )
    observed: list[Literal["filesystem", "network"]] = []
    if uses_filesystem:
        observed.append("filesystem")
    if uses_network:
        observed.append("network")
    return (
        _file_digest(server_path),
        observed,
        destinations if uses_network else [],
        uses_network and not destinations,
    )


def _literal_destination(value: str) -> str | None:
    if not value.startswith(("http://", "https://", "ws://", "wss://")):
        return None
    from urllib.parse import urlsplit

    return urlsplit(value).hostname


_JSON_TYPES = {
    "str": "string",
    "string": "string",
    "int": "integer",
    "integer": "integer",
    "float": "number",
    "number": "number",
    "bool": "boolean",
    "boolean": "boolean",
}


def _runtime_input_schema(tool: ToolDef) -> dict[str, object]:
    """Derive the exact FastMCP schema shape for the supported scalar plan types."""
    properties: dict[str, object] = {}
    required: list[str] = []
    for parameter in tool.params:
        json_type = _JSON_TYPES.get(parameter.type.lower())
        if json_type is None:
            raise ValueError(
                f"tool {tool.name!r} parameter {parameter.name!r} "
                "has unsupported runtime schema type"
            )
        properties[parameter.name] = {"type": json_type}
        required.append(parameter.name)
    return {
        "additionalProperties": False,
        "properties": properties,
        "required": required,
        "type": "object",
    }


def _runtime_output_schema(tool: ToolDef) -> dict[str, object]:
    if tool.return_type.lower() in {"dict", "object"}:
        return {"additionalProperties": True, "type": "object"}
    json_type = _JSON_TYPES.get(tool.return_type.lower())
    if json_type is None:
        raise ValueError(f"tool {tool.name!r} has unsupported runtime output schema type")
    return {"type": json_type}


def _normalize_destination(value: str) -> str:
    return _literal_destination(value) or value.lower().strip(".")


def _file_digest(path: Path) -> Digest:
    return _digest_bytes(path.read_bytes())


def _package_identities(path: Path) -> list[str]:
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    dependencies = payload.get("project", {}).get("dependencies")
    if not isinstance(dependencies, list) or not all(
        isinstance(item, str) for item in dependencies
    ):
        raise ValueError("generated pyproject.toml must declare a string dependency list")
    return sorted(dependencies)


def _launch_config(path: Path, server_id: str) -> ForgeLaunchConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    servers = payload.get("mcpServers")
    if not isinstance(servers, dict) or set(servers) != {server_id}:
        raise ValueError("generated config must contain exactly the receipt server")
    server = servers[server_id]
    if not isinstance(server, dict):
        raise ValueError("generated server launch config must be an object")
    command = server.get("command")
    args = server.get("args", [])
    url = server.get("url")
    env = server.get("env", {})
    if command is not None and not isinstance(command, str):
        raise ValueError("generated launch command must be a string")
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise ValueError("generated launch args must be strings")
    if url is not None and not isinstance(url, str):
        raise ValueError("generated launch URL must be a string")
    if not isinstance(env, dict) or not all(isinstance(key, str) for key in env):
        raise ValueError("generated launch env must be an object with string keys")
    return ForgeLaunchConfig(command=command, args=args, url=url, env_keys=sorted(env))


def _digest_json(value: object) -> Digest:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return _digest_bytes(encoded)


def _digest_bytes(value: bytes) -> Digest:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _media_type(path: str) -> str:
    if path.endswith(".json"):
        return "application/json"
    if path.endswith(".toml"):
        return "application/toml"
    if path.endswith(".md"):
        return "text/markdown"
    return "text/x-python" if path.endswith(".py") else "text/plain"


def forge_receipt_json_schema() -> dict[str, object]:
    """Return the canonical generated JSON Schema for ForgeReceiptV0."""
    return ForgeReceiptV0.model_json_schema()

"""Local environment diagnostics for mcpforge."""

import os
import platform
import shutil
import subprocess
import sys
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from mcpforge.api_client import DEFAULT_MODEL
from mcpforge.providers import DEFAULT_PROVIDER, list_provider_capabilities


def _command_version(command: str, *args: str) -> dict[str, Any]:
    path = shutil.which(command)
    if not path:
        return {"name": command, "ok": False, "path": "", "version": "", "detail": "not found"}
    try:
        result = subprocess.run(
            [command, *args],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"name": command, "ok": False, "path": path, "version": "", "detail": str(exc)}
    output = (result.stdout or result.stderr).strip().splitlines()
    return {
        "name": command,
        "ok": result.returncode == 0,
        "path": path,
        "version": output[0] if output else "",
        "detail": "" if result.returncode == 0 else (result.stderr or result.stdout).strip(),
    }


def _package_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return ""


def _workspace_writable(path: Path) -> dict[str, Any]:
    root = path.resolve()
    try:
        with tempfile.NamedTemporaryFile(prefix=".mcpforge-doctor-", dir=root, delete=True):
            pass
    except OSError as exc:
        return {"ok": False, "path": str(root), "detail": str(exc)}
    return {"ok": True, "path": str(root), "detail": ""}


def run_doctor(workspace: Path | None = None) -> dict[str, Any]:
    """Return mcpforge prerequisite and configuration diagnostics."""
    workspace_path = workspace or Path.cwd()
    commands = [
        _command_version("uv", "--version"),
        _command_version("ruff", "--version"),
        _command_version("pytest", "--version"),
        _command_version("node", "--version"),
        _command_version("npm", "--version"),
    ]
    checks = {
        "python": {
            "ok": sys.version_info >= (3, 12),
            "version": platform.python_version(),
            "detail": "requires Python 3.12+",
        },
        "commands": commands,
        "packages": {
            "fastmcp": _package_version("fastmcp"),
            "mcpforge": _package_version("mcpforge"),
        },
        "anthropic_api_key": {
            "ok": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "detail": "set" if os.environ.get("ANTHROPIC_API_KEY") else "not set",
        },
        "workspace": _workspace_writable(workspace_path),
        "provider": {
            "default_provider": DEFAULT_PROVIDER,
            "default_model": DEFAULT_MODEL,
            "capabilities": list_provider_capabilities(),
        },
    }
    required_command_names = {"uv", "ruff", "pytest"}
    required_commands_ok = all(
        command["ok"] for command in commands if command["name"] in required_command_names
    )
    checks["ok"] = bool(
        checks["python"]["ok"] and required_commands_ok and checks["workspace"]["ok"]
    )
    return checks

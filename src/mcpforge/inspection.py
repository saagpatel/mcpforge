"""Read-only inspection helpers for generated mcpforge servers."""

import re
import tokenize
from ast import literal_eval
from io import StringIO
from pathlib import Path
from typing import Any

from mcpforge.utils import read_optional_json_object


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except OSError:
        return ""


def _match_names(pattern: str, text: str) -> list[str]:
    return sorted(set(re.findall(pattern, text, flags=re.MULTILINE)))


def _tool_name(arguments: str, function: str) -> str:
    """Read a literal name keyword from just this decorator's argument list."""
    depth = 0
    argument: list[tokenize.TokenInfo] = []
    try:
        for token in tokenize.generate_tokens(StringIO(arguments).readline):
            if depth == 1:
                if token.type == tokenize.OP and token.string in {",", ")"}:
                    match argument:
                        case [(_, "name", *_), (_, "=", *_), (tokenize.STRING, literal, *_)]:
                            value = literal_eval(literal)
                            if isinstance(value, str):
                                return value
                    argument.clear()
                elif token.type not in {tokenize.NL, tokenize.COMMENT}:
                    argument.append(token)
            if token.type == tokenize.OP:
                if token.string in {"(", "[", "{"}:
                    depth += 1
                elif token.string in {")", "]", "}"}:
                    depth -= 1
    except (SyntaxError, tokenize.TokenError, ValueError):
        pass
    return function


def _python_tool_names(code: str) -> list[str]:
    # A called decorator may continue over indented lines before its closing parenthesis.
    pattern = (
        r"^@mcp\.tool[ \t]*(\((?:.*\n(?=[ \t)\n]))*.*\))?[ \t]*(?:#.*)?\s*\n"
        r"(?:async\s+)?def\s+([a-zA-Z_][a-zA-Z0-9_]*)"
    )
    matches = re.findall(pattern, code, re.MULTILINE)
    return sorted({_tool_name(args, function) if args else function for args, function in matches})


def _env_vars_from_text(text: str) -> list[str]:
    patterns = [
        r"os\.environ\.get\([\"']([A-Z_][A-Z0-9_]*)[\"']",
        r"os\.environ\[[\"']([A-Z_][A-Z0-9_]*)[\"']\]",
        r"process\.env\.([A-Z_][A-Z0-9_]*)",
        r"process\.env\[[\"']([A-Z_][A-Z0-9_]*)[\"']\]",
    ]
    found: set[str] = set()
    for pattern in patterns:
        found.update(re.findall(pattern, text))
    return sorted(found)


def _env_vars_from_env_example(path: Path) -> list[str]:
    text = _read_text(path)
    vars_: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if re.match(r"^[A-Z_][A-Z0-9_]*$", key):
            vars_.append(key)
    return sorted(set(vars_))


def inspect_server(path: Path) -> dict[str, Any]:
    """Return a read-only summary of a generated server directory."""
    root = path.resolve()
    config = read_optional_json_object(root / "config.json", validate_mcp_servers=True)
    fastmcp_config = read_optional_json_object(root / "fastmcp.json")
    server_py = root / "server.py"
    server_ts = root / "src" / "server.ts"
    package_json = root / "package.json"
    pyproject = root / "pyproject.toml"
    language = "unknown"
    code = ""

    if server_py.exists():
        language = "python"
        code = _read_text(server_py)
        required_files = [
            "server.py",
            "test_server.py",
            "pyproject.toml",
            "README.md",
            "config.json",
        ]
        test_path = root / "test_server.py"
    elif server_ts.exists():
        language = "typescript"
        code = _read_text(server_ts)
        required_files = [
            "src/server.ts",
            "src/server.test.ts",
            "package.json",
            "tsconfig.json",
            "config.json",
        ]
        test_path = root / "src" / "server.test.ts"
    else:
        required_files = ["server.py or src/server.ts", "config.json"]
        test_path = root / "test_server.py"

    missing_files = [
        rel
        for rel in required_files
        if rel == "server.py or src/server.ts" or not (root / rel).exists()
    ]
    if server_py.exists() or server_ts.exists():
        missing_files = [rel for rel in missing_files if rel != "server.py or src/server.ts"]

    if language == "python":
        tools = _python_tool_names(code)
        resources = _match_names(
            r"^@mcp\.resource\([^\n]*\)\s*\n(?:async\s+)?def\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            code,
        )
        prompts = _match_names(
            r"^@mcp\.prompt\s*\n(?:async\s+)?def\s+([a-zA-Z_][a-zA-Z0-9_]*)", code
        )
    elif language == "typescript":
        tools = _match_names(r"server\.tool\(\s*[\"']([^\"']+)[\"']", code)
        resources = _match_names(r"server\.resource\(\s*[\"']([^\"']+)[\"']", code)
        prompts = _match_names(r"server\.prompt\(\s*[\"']([^\"']+)[\"']", code)
    else:
        tools = []
        resources = []
        prompts = []

    server_names = config.get("mcpServers", {})
    name = (
        next(iter(server_names.keys()), root.name) if isinstance(server_names, dict) else root.name
    )
    env_vars = _env_vars_from_env_example(root / ".env.example") or _env_vars_from_text(code)
    readme = _read_text(root / "README.md")
    deployment = fastmcp_config.get("deployment", {})
    has_http_config = bool(
        isinstance(deployment, dict)
        and deployment.get("transport") in {"http", "streamable-http", "sse"}
        and deployment.get("path")
    )
    has_security_notes = "## Security Notes" in readme
    has_remote_checklist = "## Remote MCP Readiness" in readme
    has_auth_boundary = bool(
        "MCPFORGE_SERVER_API_KEY" in env_vars
        or "JWT_JWKS_URI" in env_vars
        or "deployment boundary" in readme
        or "gateway" in readme
    )
    remote_config_complete = bool(
        language == "python"
        and fastmcp_config
        and has_http_config
        and has_security_notes
        and has_remote_checklist
    )

    return {
        "path": str(root),
        "exists": root.exists(),
        "name": name,
        "language": language,
        "tools": {"count": len(tools), "names": tools},
        "resources": {"count": len(resources), "names": resources},
        "prompts": {"count": len(prompts), "names": prompts},
        "tests": {
            "present": test_path.exists(),
            "path": str(test_path) if test_path.exists() else "",
        },
        "env_vars": env_vars,
        "config": {
            "has_config_json": bool(config),
            "has_fastmcp_json": bool(fastmcp_config),
            "has_pyproject": pyproject.exists(),
            "has_package_json": package_json.exists(),
        },
        "remote_mcp": {
            "ready": remote_config_complete,
            "meaning": (
                "configuration completeness only; deployment and operational readiness "
                "are not verified"
            ),
            "has_http_config": has_http_config,
            "has_security_notes": has_security_notes,
            "has_remote_checklist": has_remote_checklist,
            "has_auth_boundary": has_auth_boundary,
        },
        "missing_files": missing_files,
        "validation_ready": bool(root.exists() and language != "unknown" and not missing_files),
    }

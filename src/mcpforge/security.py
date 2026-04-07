"""Security scanner: AST-based analysis of generated code for dangerous patterns."""

import ast

# Imports considered safe for generated MCP servers.
ALLOWED_IMPORTS: frozenset[str] = frozenset({
    "__future__",
    "abc",
    "asyncio",
    "base64",
    "collections",
    "contextlib",
    "copy",
    "dataclasses",
    "datetime",
    "decimal",
    "enum",
    "functools",
    "hashlib",
    "hmac",
    "io",
    "itertools",
    "json",
    "logging",
    "math",
    "os",
    "pathlib",
    "re",
    "secrets",
    "string",
    "textwrap",
    "typing",
    "typing_extensions",
    "uuid",
    # Common third-party packages used by MCP servers
    "aiohttp",
    "aiosqlite",
    "asyncpg",
    "fastmcp",
    "gql",
    "httpx",
    "jose",
    "motor",
    "pydantic",
    "redis",
    "requests",
    "websockets",
})

# Built-in function calls that are never safe in generated code.
DANGEROUS_CALLS: frozenset[str] = frozenset({
    "eval",
    "exec",
    "compile",
    "__import__",
    "globals",
    "locals",
    "breakpoint",
})

# Module.function patterns that are dangerous.
DANGEROUS_ATTRIBUTES: frozenset[str] = frozenset({
    "os.system",
    "os.popen",
    "os.exec",
    "os.execl",
    "os.execle",
    "os.execlp",
    "os.execlpe",
    "os.execv",
    "os.execve",
    "os.execvp",
    "os.execvpe",
    "os.spawn",
    "os.spawnl",
    "os.spawnle",
    "os.spawnlp",
    "os.spawnlpe",
    "os.spawnv",
    "os.spawnve",
    "os.spawnvp",
    "os.spawnvpe",
    "subprocess.run",
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
    "subprocess.Popen",
    "shutil.rmtree",
    "shutil.move",
})


def check_security(code: str) -> list[str]:
    """Scan Python AST for dangerous patterns in generated code.

    Returns a list of warning/error strings. Entries prefixed with
    'DANGEROUS:' indicate hard blockers (should prevent execution).
    Entries prefixed with 'WARNING:' are informational (unknown imports).
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []  # Syntax errors are caught by the syntax checker

    findings: list[str] = []

    for node in ast.walk(tree):
        # Check imports against allowlist
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_module = alias.name.split(".")[0]
                if top_module not in ALLOWED_IMPORTS:
                    findings.append(
                        f"WARNING: unknown import '{alias.name}' at line {node.lineno} "
                        f"— review before execution"
                    )

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top_module = node.module.split(".")[0]
                if top_module not in ALLOWED_IMPORTS:
                    findings.append(
                        f"WARNING: unknown import from '{node.module}' at line {node.lineno} "
                        f"— review before execution"
                    )

        # Check function calls against denylist
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in DANGEROUS_CALLS:
                    findings.append(
                        f"DANGEROUS: call to '{node.func.id}()' at line {node.lineno}"
                    )

            elif isinstance(node.func, ast.Attribute):
                # Build dotted name for attribute access (e.g. os.system)
                attr_chain = _resolve_attr_chain(node.func)
                if attr_chain and attr_chain in DANGEROUS_ATTRIBUTES:
                    findings.append(
                        f"DANGEROUS: call to '{attr_chain}()' at line {node.lineno}"
                    )

    return findings


def _resolve_attr_chain(node: ast.Attribute) -> str | None:
    """Resolve a dotted attribute chain like os.system or subprocess.run."""
    parts: list[str] = [node.attr]
    current = node.value
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    return None

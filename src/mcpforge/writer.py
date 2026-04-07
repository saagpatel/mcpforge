"""Writer: renders Jinja2 templates and writes the generated server to disk."""

import importlib.resources
import os
import re
from pathlib import Path

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from mcpforge.models import ServerPlan

_JINJA_SYNTAX_RE = re.compile(r"\{\{.*?\}\}|\{%.*?%\}")


def _validate_template_context(plan: ServerPlan) -> None:
    """Reject plan fields containing Jinja2 template syntax to prevent SSTI."""
    for field_name in ("name", "description"):
        value = getattr(plan, field_name)
        if _JINJA_SYNTAX_RE.search(value):
            raise ValueError(
                f"Plan {field_name} contains Jinja2 template syntax — "
                f"this is not allowed: {value!r}"
            )


def _validate_rel_path(rel_path: str, output_dir: Path) -> Path:
    """Validate a relative path from LLM output stays within output_dir.

    Rejects null bytes, absolute paths, '..' components, and dotfiles/hidden dirs.
    Returns the resolved destination path.
    """
    if "\x00" in rel_path:
        raise ValueError(f"Unsafe path rejected (null byte): {rel_path!r}")
    if os.path.isabs(rel_path):
        raise ValueError(f"Unsafe path rejected (absolute): {rel_path!r}")
    parts = rel_path.replace("\\", "/").split("/")
    for part in parts:
        if part == "..":
            raise ValueError(f"Unsafe path rejected (directory traversal): {rel_path!r}")
        if part.startswith(".") and part not in (".", ""):
            raise ValueError(f"Unsafe path rejected (hidden file/directory): {rel_path!r}")
    resolved_output = output_dir.resolve()
    dest = (resolved_output / rel_path).resolve()
    if not dest.is_relative_to(resolved_output):
        raise ValueError(f"Unsafe path rejected (escapes output directory): {rel_path!r}")
    return dest


def _load_template(name: str) -> str:
    """Load a Jinja2 template from the mcpforge templates directory."""
    return (
        importlib.resources.files("mcpforge")
        .joinpath("templates", name)
        .read_text(encoding="utf-8")
    )


def write_server(
    plan: ServerPlan,
    server_code: str,
    test_code: str,
    output_dir: Path,
    force: bool = False,
) -> Path:
    """Write a generated server to the output directory.

    Creates the directory if it doesn't exist. Raises FileExistsError if the
    directory already exists and is non-empty unless force=True.

    Returns:
        The resolved output directory path.
    """
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        raise FileExistsError(
            f"{output_dir} already exists and is not empty. Use force=True to overwrite."
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    _validate_template_context(plan)
    env = SandboxedEnvironment(loader=BaseLoader(), autoescape=False)
    context = {"plan": plan}

    (output_dir / "server.py").write_text(server_code, encoding="utf-8")
    (output_dir / "test_server.py").write_text(test_code, encoding="utf-8")

    for tmpl_name, out_name in [
        ("pyproject.toml.j2", "pyproject.toml"),
        ("README.md.j2", "README.md"),
        ("config.json.j2", "config.json"),
    ]:
        template_src = _load_template(tmpl_name)
        rendered = env.from_string(template_src).render(**context)
        (output_dir / out_name).write_text(rendered, encoding="utf-8")

    return output_dir


def write_server_multi(
    plan: ServerPlan,
    files: dict[str, str],
    test_code: str,
    output_dir: Path,
    force: bool = False,
) -> Path:
    """Write a multi-file generated server to the output directory.

    `files` maps relative paths (e.g. 'server.py', 'tools/crud.py') to content.
    `test_code` is written as test_server.py in the output directory root.
    """
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        raise FileExistsError(
            f"{output_dir} already exists and is not empty. Use force=True to overwrite."
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write generated files (validate paths to prevent traversal)
    for rel_path, content in files.items():
        dest = _validate_rel_path(rel_path, output_dir)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")

    # Write test file
    (output_dir / "test_server.py").write_text(test_code, encoding="utf-8")

    # Render standard scaffolding templates
    _validate_template_context(plan)
    env = SandboxedEnvironment(loader=BaseLoader(), autoescape=False)
    context = {"plan": plan}
    for tmpl_name, out_name in [
        ("pyproject.toml.j2", "pyproject.toml"),
        ("README.md.j2", "README.md"),
        ("config.json.j2", "config.json"),
    ]:
        template_src = _load_template(tmpl_name)
        rendered = env.from_string(template_src).render(**context)
        (output_dir / out_name).write_text(rendered, encoding="utf-8")

    return output_dir


def write_server_ts(
    plan: ServerPlan,
    server_code: str,
    test_code: str,
    output_dir: Path,
    force: bool = False,
) -> Path:
    """Write a generated TypeScript server to the output directory.

    Creates the directory if it doesn't exist. Raises FileExistsError if the
    directory already exists and is non-empty unless force=True.

    Returns:
        The resolved output directory path.
    """
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        raise FileExistsError(
            f"{output_dir} already exists and is not empty. Use force=True to overwrite."
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    _validate_template_context(plan)
    env = SandboxedEnvironment(loader=BaseLoader(), autoescape=False)
    context = {"plan": plan}

    src_dir = output_dir / "src"
    src_dir.mkdir(exist_ok=True)

    (src_dir / "server.ts").write_text(server_code, encoding="utf-8")
    (src_dir / "server.test.ts").write_text(test_code, encoding="utf-8")

    for tmpl_name, out_name in [
        ("ts/package.json.j2", "package.json"),
        ("ts/tsconfig.json.j2", "tsconfig.json"),
        ("ts/gitignore.j2", ".gitignore"),
    ]:
        template_src = _load_template(tmpl_name)
        rendered = env.from_string(template_src).render(**context)
        (output_dir / out_name).write_text(rendered, encoding="utf-8")

    return output_dir

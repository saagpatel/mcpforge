"""Writer: renders Jinja2 templates and writes the generated server to disk."""

import importlib.resources
from pathlib import Path

from jinja2 import BaseLoader, Environment

from mcpforge.models import ServerPlan


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

    env = Environment(loader=BaseLoader(), autoescape=False)
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

    env = Environment(loader=BaseLoader(), autoescape=False)
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

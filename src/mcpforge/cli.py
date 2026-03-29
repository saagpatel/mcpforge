"""Click CLI entrypoint for mcpforge."""

import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from mcpforge import __version__
from mcpforge.api_client import AnthropicClient
from mcpforge.generator import generate_server
from mcpforge.generator_ts import generate_server_ts, generate_tests_ts
from mcpforge.models import ServerPlan, ValidationResult
from mcpforge.openapi import load_spec, parse_openapi
from mcpforge.planner import extract_plan, refine_plan
from mcpforge.self_heal import attempt_fix
from mcpforge.template_hints import TEMPLATE_HINTS
from mcpforge.test_generator import generate_tests
from mcpforge.updater import update_server
from mcpforge.validator import uv_sync, validate_server
from mcpforge.validator_ts import npm_install, validate_server_ts
from mcpforge.writer import write_server, write_server_ts

console = Console()


def _display_plan(plan: ServerPlan) -> None:
    """Display a ServerPlan as a Rich table."""
    table = Table(title=f"[bold]{plan.name}[/bold] ({plan.slug})", show_header=True)
    table.add_column("Tool", style="cyan")
    table.add_column("Params")
    table.add_column("Returns", style="green")
    for tool in plan.tools:
        params = ", ".join(
            f"{p.name}: {p.type}" + ("?" if not p.required else "") for p in tool.params
        )
        table.add_row(tool.name, params or "—", tool.return_type)
    console.print(table)


def _display_results(
    plan: ServerPlan,
    result: ValidationResult,
    output_path: Path,
    heal_attempted: bool,
) -> None:
    """Display final validation results as a Rich panel."""
    status = "[green]VALID[/green]" if result.is_valid else "[red]INVALID[/red]"
    lines = [
        f"Status: {status}",
        f"Output: {output_path}",
        f"Syntax: {'✓' if result.syntax_ok else '✗'}",
        f"Lint: {'✓' if not result.lint_errors else f'✗ ({len(result.lint_errors)} errors)'}",
        f"Import: {'✓' if result.import_ok else '✗'}",
        f"Tests: {result.tests_run} run, {result.tests_failed} failed",
    ]
    if heal_attempted:
        lines.append("[yellow]Self-heal was attempted.[/yellow]")
    if result.errors:
        lines.append("")
        lines.append("[red]Errors:[/red]")
        for err in result.errors[:5]:
            lines.append(f"  {err}")
    console.print(Panel("\n".join(lines), title="mcpforge result"))


async def _run_generate(
    description: str,
    output: str | None,
    model: str,
    transport: str,
    dry_run: bool,
    yes: bool,
    force: bool,
    template_hint: str = "",
    openapi_path: str | None = None,
    language: str = "python",
    interactive: bool = False,
) -> None:
    """Async orchestration for the generate command."""
    client = AnthropicClient(model=model)

    # Stage 1: Plan
    if openapi_path:
        plan = parse_openapi(load_spec(Path(openapi_path)))
    else:
        with Progress(
            SpinnerColumn(), TextColumn("{task.description}"), console=console
        ) as progress:
            task = progress.add_task("Planning server structure...", total=None)
            plan = await extract_plan(description, client, transport)
            progress.remove_task(task)

    _display_plan(plan)

    # Interactive refinement loop
    if interactive:
        while True:
            feedback = click.prompt("Changes (Enter to proceed)", default="", show_default=False)
            if not feedback.strip():
                break
            with Progress(
                SpinnerColumn(), TextColumn("{task.description}"), console=console
            ) as progress:
                task = progress.add_task("Refining plan...", total=None)
                plan = await refine_plan(plan, feedback, client)
                progress.remove_task(task)
            _display_plan(plan)

    if dry_run:
        return

    if not yes:
        click.confirm("Generate server?", abort=True)

    output_path = Path(output) if output else Path(plan.slug)

    # Stage 2: Generate code
    if language == "typescript":
        with Progress(
            SpinnerColumn(), TextColumn("{task.description}"), console=console
        ) as progress:
            task = progress.add_task("Generating TypeScript server code...", total=None)
            server_code = await generate_server_ts(plan, client)
            progress.update(task, description="Generating TypeScript test suite...")
            test_code = await generate_tests_ts(plan, server_code, client)
            progress.remove_task(task)

        # Stage 3: Write files
        write_server_ts(plan, server_code, test_code, output_path, force=force)
        console.print(f"[dim]Written to {output_path}[/dim]")

        # Stage 4: Install + Validate (no self-heal for TS)
        with Progress(
            SpinnerColumn(), TextColumn("{task.description}"), console=console
        ) as progress:
            task = progress.add_task("Installing dependencies (npm install)...", total=None)
            await npm_install(output_path)
            progress.update(task, description="Validating TypeScript server...")
            result = await validate_server_ts(output_path)
            progress.remove_task(task)

        _display_results(plan, result, output_path, heal_attempted=False)
        if not result.is_valid:
            raise SystemExit(1)

    else:
        # Python path
        with Progress(
            SpinnerColumn(), TextColumn("{task.description}"), console=console
        ) as progress:
            task = progress.add_task("Generating server code...", total=None)
            server_code = await generate_server(plan, client, template_hint=template_hint)
            progress.update(task, description="Generating test suite...")
            test_code = await generate_tests(plan, server_code, client)
            progress.remove_task(task)

        # Stage 3: Write files
        write_server(plan, server_code, test_code, output_path, force=force)
        console.print(f"[dim]Written to {output_path}[/dim]")

        # Stage 4: Sync + Validate
        with Progress(
            SpinnerColumn(), TextColumn("{task.description}"), console=console
        ) as progress:
            task = progress.add_task("Installing dependencies (uv sync)...", total=None)
            await uv_sync(output_path)
            progress.update(task, description="Validating server...")
            result = await validate_server(output_path)
            progress.remove_task(task)

        # Stage 5: Self-heal (1 retry if invalid)
        heal_attempted = False
        if not result.is_valid:
            heal_attempted = True
            with Progress(
                SpinnerColumn(), TextColumn("{task.description}"), console=console
            ) as progress:
                task = progress.add_task("Attempting self-heal...", total=None)
                fixed = await attempt_fix(server_code, result.errors, client)
                if fixed:
                    (output_path / "server.py").write_text(fixed, encoding="utf-8")
                    progress.update(task, description="Re-validating after self-heal...")
                    result = await validate_server(output_path)
                progress.remove_task(task)

        # Stage 6: Summary
        _display_results(plan, result, output_path, heal_attempted)
        if not result.is_valid:
            raise SystemExit(1)


async def _run_update(
    path: str,
    request: str,
    model: str,
    yes: bool,
) -> None:
    """Async orchestration for the update command."""
    output_dir = Path(path)
    client = AnthropicClient(model=model)

    console.print(Panel(request, title="Update request"))

    if not yes:
        click.confirm("Apply update?", abort=True)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        task = progress.add_task("Applying update...", total=None)
        server_code, test_code = await update_server(output_dir, request, client)
        progress.remove_task(task)

    (output_dir / "server.py").write_text(server_code, encoding="utf-8")
    (output_dir / "test_server.py").write_text(test_code, encoding="utf-8")
    console.print(f"[dim]Updated {output_dir / 'server.py'}[/dim]")

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        task = progress.add_task("Installing dependencies (uv sync)...", total=None)
        await uv_sync(output_dir)
        progress.update(task, description="Validating server...")
        result = await validate_server(output_dir)
        progress.remove_task(task)

    # Self-heal (1 retry if invalid)
    heal_attempted = False
    if not result.is_valid:
        heal_attempted = True
        with Progress(
            SpinnerColumn(), TextColumn("{task.description}"), console=console
        ) as progress:
            task = progress.add_task("Attempting self-heal...", total=None)
            fixed = await attempt_fix(server_code, result.errors, client)
            if fixed:
                (output_dir / "server.py").write_text(fixed, encoding="utf-8")
                progress.update(task, description="Re-validating after self-heal...")
                result = await validate_server(output_dir)
            progress.remove_task(task)

    # Reuse _display_results — build a minimal plan for display
    dummy_plan = ServerPlan(
        name=output_dir.name,
        slug=output_dir.name,
        description="",
        tools=[],
    )
    _display_results(dummy_plan, result, output_dir, heal_attempted)

    if not result.is_valid:
        raise SystemExit(1)


async def _validate_command(path: str) -> None:
    """Async logic for the validate command."""
    output_dir = Path(path)
    server_py = output_dir / "server.py"
    if not server_py.exists():
        console.print(f"[red]Error:[/red] No server.py found in {output_dir}")
        raise SystemExit(1)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        task = progress.add_task("Validating server...", total=None)
        result = await validate_server(output_dir)
        progress.remove_task(task)

    table = Table(title="Validation Results")
    table.add_column("Check", style="cyan")
    table.add_column("Result")
    table.add_row("Syntax", "✓ OK" if result.syntax_ok else "[red]✗ FAIL[/red]")
    table.add_row(
        "Lint",
        "✓ OK" if not result.lint_errors else f"[red]✗ {len(result.lint_errors)} errors[/red]",
    )
    table.add_row("Import", "✓ OK" if result.import_ok else "[red]✗ FAIL[/red]")
    table.add_row(
        "Tests",
        f"{result.tests_run} run, {result.tests_failed} failed",
    )
    console.print(table)

    if result.lint_errors:
        for err in result.lint_errors:
            console.print(f"  [yellow]{err}[/yellow]")

    if not result.is_valid:
        raise SystemExit(1)


@click.group()
@click.version_option(version=__version__, prog_name="mcpforge")
def cli() -> None:
    """mcpforge — Generate FastMCP 3.x MCP servers from plain-English descriptions."""


@cli.command()
@click.argument("description")
@click.option(
    "--output",
    "-o",
    default=None,
    metavar="PATH",
    help="Output directory (default: ./<slug>)",
)
@click.option(
    "--model",
    "-m",
    default="claude-sonnet-4-20250514",
    show_default=True,
    help="Override the LLM model used for generation.",
)
@click.option(
    "--transport",
    "-t",
    default="streamable-http",
    show_default=True,
    type=click.Choice(["streamable-http", "stdio", "sse"], case_sensitive=False),
    help="MCP transport type for the generated server.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Extract and display the server plan without generating code.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Skip confirmation prompts.",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    default=False,
    help="Overwrite existing output directory.",
)
@click.option(
    "--template",
    "-T",
    default=None,
    type=click.Choice(list(TEMPLATE_HINTS.keys()), case_sensitive=False),
    help="Apply a template hint to guide code generation style.",
)
@click.option(
    "--from-openapi",
    "openapi_path",
    default=None,
    metavar="FILE",
    help="Generate from an OpenAPI 3.x spec (JSON or YAML). Skips the planning stage.",
)
@click.option(
    "--language",
    "-l",
    default="python",
    show_default=True,
    type=click.Choice(["python", "typescript"], case_sensitive=False),
    help="Target language for generated server.",
)
@click.option(
    "--interactive",
    "-i",
    is_flag=True,
    default=False,
    help="Interactively refine the plan before generating.",
)
def generate(
    description: str,
    output: str | None,
    model: str,
    transport: str,
    dry_run: bool,
    yes: bool,
    force: bool,
    template: str | None,
    openapi_path: str | None,
    language: str,
    interactive: bool,
) -> None:
    """Generate a complete MCP server from a plain-English DESCRIPTION."""
    try:
        template_hint = TEMPLATE_HINTS.get(template or "", "")
        asyncio.run(
            _run_generate(
                description,
                output,
                model,
                transport,
                dry_run,
                yes,
                force,
                template_hint=template_hint,
                openapi_path=openapi_path,
                language=language,
                interactive=interactive,
            )
        )
    except click.exceptions.Abort:
        console.print("[yellow]Aborted.[/yellow]")
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise SystemExit(1)
    except FileExistsError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise SystemExit(1)


@cli.command()
@click.argument("path")
@click.argument("request")
@click.option(
    "--model",
    "-m",
    default="claude-sonnet-4-20250514",
    show_default=True,
    help="Override the LLM model used for generation.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Skip confirmation prompts.",
)
def update(path: str, request: str, model: str, yes: bool) -> None:
    """Apply a modification REQUEST to an existing MCP server at PATH."""
    try:
        asyncio.run(_run_update(path, request, model, yes))
    except click.exceptions.Abort:
        console.print("[yellow]Aborted.[/yellow]")
    except FileNotFoundError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise SystemExit(1)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise SystemExit(1)


@cli.command()
@click.argument("path")
def validate(path: str) -> None:
    """Validate an existing MCP server at PATH."""
    asyncio.run(_validate_command(path))


@cli.command("version")
def version_cmd() -> None:
    """Print the mcpforge version."""
    console.print(f"mcpforge {__version__}")

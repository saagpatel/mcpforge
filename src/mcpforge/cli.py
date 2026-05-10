"""Click CLI entrypoint for mcpforge."""

import asyncio
import importlib.resources
import json
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from mcpforge import __version__
from mcpforge.api_client import DEFAULT_MODEL, AnthropicClient
from mcpforge.discovery import find_servers
from mcpforge.doctor import run_doctor
from mcpforge.generator import generate_server, generate_server_multi
from mcpforge.generator_ts import generate_server_ts, generate_tests_ts
from mcpforge.inspection import inspect_server
from mcpforge.models import ServerPlan, ToolDef, ValidationResult
from mcpforge.openapi import load_spec, parse_openapi
from mcpforge.planner import extract_plan, refine_plan
from mcpforge.profiles import apply_generation_profiles
from mcpforge.prompts import load_prompt
from mcpforge.providers import DEFAULT_PROVIDER, create_provider_client
from mcpforge.self_heal import attempt_fix
from mcpforge.template_hints import TEMPLATE_HINTS
from mcpforge.test_generator import generate_tests
from mcpforge.updater import update_server
from mcpforge.utils import strip_code_fences
from mcpforge.validator import check_plan_conformance, uv_sync, validate_server
from mcpforge.validator_ts import validate_server_ts
from mcpforge.writer import write_server, write_server_multi, write_server_ts

console = Console()


def _create_cli_client(provider: str, model: str):
    """Create a generation client while preserving existing Anthropic test seams."""
    if provider.lower() == "anthropic":
        return AnthropicClient(model=model)
    return create_provider_client(provider, model=model)


def _print_json(data: Any) -> None:
    """Print stable JSON for machine-readable CLI output."""
    click.echo(json.dumps(data, indent=2, sort_keys=True))


def _validation_result_dict(result: ValidationResult) -> dict[str, Any]:
    """Serialize validation state for CLI and MCP output."""
    return {
        "valid": _validation_passed(result),
        "structurally_valid": result.is_valid,
        "tests_ok": result.tests_ok,
        "syntax_ok": result.syntax_ok,
        "import_ok": result.import_ok,
        "lint_errors": result.lint_errors,
        "tests_run": result.tests_run,
        "tests_failed": result.tests_failed,
        "errors": result.errors,
    }


def _load_init_template(name: str) -> str:
    """Load an init template from the mcpforge templates directory."""
    return (
        importlib.resources.files("mcpforge")
        .joinpath("templates", name)
        .read_text(encoding="utf-8")
    )


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
    status = "[green]VALID[/green]" if _validation_passed(result) else "[red]INVALID[/red]"
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


def _validation_passed(result: ValidationResult) -> bool:
    """Return True when structural checks and executed tests are healthy."""
    return result.is_valid and result.tests_ok


async def _run_generate(
    description: str,
    output: str | None,
    model: str,
    provider: str,
    transport: str,
    dry_run: bool,
    yes: bool,
    force: bool,
    template_hint: str = "",
    openapi_path: str | None = None,
    language: str = "python",
    interactive: bool = False,
    stream: bool = False,
    multi_file: bool = False,
    no_execute: bool = False,
    strict: bool = False,
    openapi_include_tags: tuple[str, ...] = (),
    openapi_exclude_tags: tuple[str, ...] = (),
    openapi_operations: tuple[str, ...] = (),
    openapi_limit: int | None = None,
    auth_profile: str = "none",
    middleware_profiles: tuple[str, ...] = (),
) -> None:
    """Async orchestration for the generate command."""
    client = None

    # Stage 1: Plan
    if openapi_path:
        plan = parse_openapi(
            load_spec(Path(openapi_path)),
            include_tags=set(openapi_include_tags) or None,
            exclude_tags=set(openapi_exclude_tags) or None,
            operations=set(openapi_operations) or None,
            operation_limit=openapi_limit,
        )
    else:
        client = _create_cli_client(provider, model)
        with Progress(
            SpinnerColumn(), TextColumn("{task.description}"), console=console
        ) as progress:
            task = progress.add_task("Planning server structure...", total=None)
            plan = await extract_plan(description, client, transport)
            progress.remove_task(task)

    if language == "typescript" and (auth_profile != "none" or middleware_profiles):
        raise ValueError("Auth and middleware generation profiles are Python-only for now.")
    if language == "python":
        plan = apply_generation_profiles(
            plan,
            auth_profile=auth_profile,
            middleware_profiles=middleware_profiles,
        )

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

    if client is None:
        client = _create_cli_client(provider, model)

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
            task = progress.add_task("Validating TypeScript server...", total=None)
            result = await validate_server_ts(output_path)
            progress.remove_task(task)

        _display_results(plan, result, output_path, heal_attempted=False)
        if not _validation_passed(result):
            raise SystemExit(1)

    else:
        # Python path
        if multi_file:
            with Progress(
                SpinnerColumn(), TextColumn("{task.description}"), console=console
            ) as progress:
                task = progress.add_task("Generating multi-file server code...", total=None)
                files = await generate_server_multi(plan, client, template_hint=template_hint)
                progress.update(task, description="Generating test suite...")
                test_code = await generate_tests(plan, files.get("server.py", ""), client)
                progress.remove_task(task)

            write_server_multi(plan, files, test_code, output_path, force=force)
            console.print(f"[dim]Written to {output_path} ({len(files)} files)[/dim]")

            # Plan-to-code conformance check
            main_code = files.get("server.py", "")
            conformance_warnings = check_plan_conformance(main_code, plan)
            for warning in conformance_warnings:
                console.print(f"[yellow]Warning:[/yellow] {warning}")

            with Progress(
                SpinnerColumn(), TextColumn("{task.description}"), console=console
            ) as progress:
                task = progress.add_task("Installing dependencies (uv sync)...", total=None)
                if not no_execute:
                    sync_err = await uv_sync(output_path, plan=plan)
                    if sync_err:
                        console.print(f"[yellow]Warning:[/yellow] {sync_err}")
                progress.update(task, description="Validating server...")
                result = await validate_server(
                    output_path, skip_execution=no_execute, strict=strict
                )
                progress.remove_task(task)

            heal_attempted = False
            if not result.is_valid and not no_execute:
                heal_attempted = True
                main_code = files.get("server.py", "")
                with Progress(
                    SpinnerColumn(), TextColumn("{task.description}"), console=console
                ) as progress:
                    task = progress.add_task("Attempting self-heal...", total=None)
                    fixed = await attempt_fix(main_code, result.errors, client)
                    if fixed:
                        (output_path / "server.py").write_text(fixed, encoding="utf-8")
                        progress.update(task, description="Re-validating after self-heal...")
                        result = await validate_server(
                            output_path, skip_execution=no_execute, strict=strict
                        )
                    progress.remove_task(task)

            _display_results(plan, result, output_path, heal_attempted)
            if not _validation_passed(result) and not no_execute:
                raise SystemExit(1)
            return

        if stream:
            # Streaming generation for Python
            buf: list[str] = []
            live_text = Text()
            sys_prompt = load_prompt("generator")
            if template_hint:
                sys_prompt = f"{sys_prompt}\n\n## Template Guidance\n\n{template_hint}"
            user_msg = plan.model_dump_json(indent=2)
            with Live(live_text, console=console, refresh_per_second=10):
                async for chunk in client.generate_stream(
                    sys_prompt, user_msg, max_tokens=16384, temperature=0.2
                ):
                    buf.append(chunk)
                    live_text.plain = f"Generating server... {sum(len(c) for c in buf):,} chars"
            server_code = strip_code_fences("".join(buf))
            with Progress(
                SpinnerColumn(), TextColumn("{task.description}"), console=console
            ) as progress:
                task = progress.add_task("Generating test suite...", total=None)
                test_code = await generate_tests(plan, server_code, client)
                progress.remove_task(task)
        else:
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

        # Plan-to-code conformance check
        conformance_warnings = check_plan_conformance(server_code, plan)
        for warning in conformance_warnings:
            console.print(f"[yellow]Warning:[/yellow] {warning}")

        # Stage 4: Sync + Validate
        with Progress(
            SpinnerColumn(), TextColumn("{task.description}"), console=console
        ) as progress:
            task = progress.add_task("Installing dependencies (uv sync)...", total=None)
            if not no_execute:
                sync_err = await uv_sync(output_path, plan=plan)
                if sync_err:
                    console.print(f"[yellow]Warning:[/yellow] {sync_err}")
            progress.update(task, description="Validating server...")
            result = await validate_server(output_path, skip_execution=no_execute, strict=strict)
            progress.remove_task(task)

        # Stage 5: Self-heal (1 retry if invalid)
        heal_attempted = False
        if not result.is_valid and not no_execute:
            heal_attempted = True
            with Progress(
                SpinnerColumn(), TextColumn("{task.description}"), console=console
            ) as progress:
                task = progress.add_task("Attempting self-heal...", total=None)
                fixed = await attempt_fix(server_code, result.errors, client)
                if fixed:
                    (output_path / "server.py").write_text(fixed, encoding="utf-8")
                    progress.update(task, description="Re-validating after self-heal...")
                    result = await validate_server(
                        output_path, skip_execution=no_execute, strict=strict
                    )
                progress.remove_task(task)

        # Stage 6: Summary
        _display_results(plan, result, output_path, heal_attempted)
        if not _validation_passed(result) and not no_execute:
            raise SystemExit(1)


async def _run_update(
    path: str,
    request: str,
    model: str,
    provider: str,
    yes: bool,
) -> None:
    """Async orchestration for the update command."""
    output_dir = Path(path)
    client = _create_cli_client(provider, model)

    console.print(Panel(request, title="Update request"))

    if not yes:
        click.confirm("Apply update?", abort=True)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        task = progress.add_task("Applying update...", total=None)
        server_code, test_code = await update_server(output_dir, request, client)
        progress.remove_task(task)

    # Backup existing files before overwriting
    server_py = output_dir / "server.py"
    test_py = output_dir / "test_server.py"
    if server_py.exists():
        bak = server_py.read_text(encoding="utf-8")
        (output_dir / "server.py.bak").write_text(bak, encoding="utf-8")
    if test_py.exists():
        bak = test_py.read_text(encoding="utf-8")
        (output_dir / "test_server.py.bak").write_text(bak, encoding="utf-8")
    console.print("[dim]Backed up existing files (.bak)[/dim]")

    (output_dir / "server.py").write_text(server_code, encoding="utf-8")
    (output_dir / "test_server.py").write_text(test_code, encoding="utf-8")
    console.print(f"[dim]Updated {output_dir / 'server.py'}[/dim]")

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        task = progress.add_task("Installing dependencies (uv sync)...", total=None)
        sync_err = await uv_sync(output_dir)
        if sync_err:
            console.print(f"[yellow]Warning:[/yellow] {sync_err}")
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

    if not _validation_passed(result):
        raise SystemExit(1)


async def _validate_command(path: str, json_output: bool = False) -> None:
    """Async logic for the validate command."""
    output_dir = Path(path)
    server_py = output_dir / "server.py"
    server_ts = output_dir / "src" / "server.ts"
    if not server_py.exists() and not server_ts.exists():
        if json_output:
            _print_json(
                {
                    "path": str(output_dir.resolve()),
                    "valid": False,
                    "error": "No server.py or src/server.ts found",
                }
            )
        else:
            console.print(f"[red]Error:[/red] No server.py or src/server.ts found in {output_dir}")
        raise SystemExit(1)

    if json_output:
        if server_ts.exists() and not server_py.exists():
            result = await validate_server_ts(output_dir)
        else:
            await uv_sync(output_dir)
            result = await validate_server(output_dir)
        payload = {"path": str(output_dir.resolve()), **_validation_result_dict(result)}
        _print_json(payload)
        if not _validation_passed(result):
            raise SystemExit(1)
        return

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        if server_ts.exists() and not server_py.exists():
            task = progress.add_task("Validating TypeScript server...", total=None)
            result = await validate_server_ts(output_dir)
        else:
            task = progress.add_task("Installing dependencies (uv sync)...", total=None)
            sync_err = await uv_sync(output_dir)
            if sync_err:
                console.print(f"[yellow]Warning:[/yellow] {sync_err}")
            progress.update(task, description="Validating server...")
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

    if not _validation_passed(result):
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
    default=DEFAULT_MODEL,
    show_default=True,
    help="Override the LLM model used for generation.",
)
@click.option(
    "--provider",
    default=DEFAULT_PROVIDER,
    show_default=True,
    type=click.Choice(["anthropic", "openai"], case_sensitive=False),
    help="Generation provider. OpenAI is gated until structured-output smokes land.",
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
    "--openapi-include-tag",
    "openapi_include_tags",
    multiple=True,
    help="Only include OpenAPI operations with this tag. Repeatable.",
)
@click.option(
    "--openapi-exclude-tag",
    "openapi_exclude_tags",
    multiple=True,
    help="Exclude OpenAPI operations with this tag. Repeatable.",
)
@click.option(
    "--openapi-operation",
    "openapi_operations",
    multiple=True,
    help="Only include this OpenAPI operationId. Repeatable.",
)
@click.option(
    "--openapi-limit",
    type=int,
    default=None,
    help="Maximum number of OpenAPI operations to convert.",
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
@click.option(
    "--stream",
    is_flag=True,
    default=False,
    help="Stream code generation output in real-time.",
)
@click.option(
    "--multi-file",
    "multi_file",
    is_flag=True,
    default=False,
    help="Generate server split across multiple files (Python only).",
)
@click.option(
    "--no-execute",
    "no_execute",
    is_flag=True,
    default=False,
    help="Skip import check and test execution (write files only).",
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Treat lint errors as validation failures (halt on lint issues).",
)
@click.option(
    "--auth-profile",
    default="none",
    show_default=True,
    type=click.Choice(["none", "api-key", "jwt"], case_sensitive=False),
    help="Add optional Python auth profile metadata and env docs.",
)
@click.option(
    "--middleware-profile",
    "middleware_profiles",
    multiple=True,
    type=click.Choice(["logging", "timing", "rate-limit"], case_sensitive=False),
    help="Add optional Python middleware profile. Repeatable.",
)
def generate(
    description: str,
    output: str | None,
    model: str,
    provider: str,
    transport: str,
    dry_run: bool,
    yes: bool,
    force: bool,
    template: str | None,
    openapi_path: str | None,
    openapi_include_tags: tuple[str, ...],
    openapi_exclude_tags: tuple[str, ...],
    openapi_operations: tuple[str, ...],
    openapi_limit: int | None,
    language: str,
    interactive: bool,
    stream: bool,
    multi_file: bool,
    no_execute: bool,
    strict: bool,
    auth_profile: str,
    middleware_profiles: tuple[str, ...],
) -> None:
    """Generate a complete MCP server from a plain-English DESCRIPTION."""
    try:
        template_hint = TEMPLATE_HINTS.get(template or "", "")
        asyncio.run(
            _run_generate(
                description,
                output,
                model,
                provider,
                transport,
                dry_run,
                yes,
                force,
                template_hint=template_hint,
                openapi_path=openapi_path,
                language=language,
                interactive=interactive,
                stream=stream,
                multi_file=multi_file,
                no_execute=no_execute,
                strict=strict,
                openapi_include_tags=openapi_include_tags,
                openapi_exclude_tags=openapi_exclude_tags,
                openapi_operations=openapi_operations,
                openapi_limit=openapi_limit,
                auth_profile=auth_profile,
                middleware_profiles=middleware_profiles,
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
    default=DEFAULT_MODEL,
    show_default=True,
    help="Override the LLM model used for generation.",
)
@click.option(
    "--provider",
    default=DEFAULT_PROVIDER,
    show_default=True,
    type=click.Choice(["anthropic", "openai"], case_sensitive=False),
    help="Generation provider. OpenAI is gated until structured-output smokes land.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Skip confirmation prompts.",
)
def update(path: str, request: str, model: str, provider: str, yes: bool) -> None:
    """Apply a modification REQUEST to an existing MCP server at PATH."""
    try:
        asyncio.run(_run_update(path, request, model, provider, yes))
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
@click.option("--json", "json_output", is_flag=True, help="Print machine-readable JSON.")
def validate(path: str, json_output: bool) -> None:
    """Validate an existing MCP server at PATH."""
    asyncio.run(_validate_command(path, json_output=json_output))


@cli.command("version")
@click.option("--json", "json_output", is_flag=True, help="Print machine-readable JSON.")
def version_cmd(json_output: bool) -> None:
    """Print the mcpforge version."""
    if json_output:
        _print_json({"version": __version__})
        return
    console.print(f"mcpforge {__version__}")


@cli.command("list")
@click.argument("path", default=".", required=False)
@click.option(
    "--recursive",
    "-r",
    is_flag=True,
    default=False,
    help="Search subdirectories recursively.",
)
@click.option("--json", "json_output", is_flag=True, help="Print machine-readable JSON.")
def list_servers(path: str, recursive: bool, json_output: bool) -> None:
    """List mcpforge-generated servers found at PATH (default: current directory)."""
    root = Path(path).resolve()
    servers = find_servers(root, recursive=recursive)
    if json_output:
        _print_json(
            {
                "root": str(root),
                "servers": [
                    {
                        "path": str(server.path),
                        "name": server.name,
                        "language": server.language,
                        "tool_count": server.tool_count,
                        "has_tests": server.has_tests,
                    }
                    for server in servers
                ],
            }
        )
        return
    if not servers:
        console.print("[dim]No mcpforge servers found.[/dim]")
        return
    table = Table(title=f"mcpforge servers in {root}")
    table.add_column("Name", style="cyan")
    table.add_column("Language")
    table.add_column("Tools", justify="right")
    table.add_column("Tests")
    table.add_column("Path", style="dim")
    for server in servers:
        table.add_row(
            server.name,
            server.language,
            str(server.tool_count),
            "✓" if server.has_tests else "—",
            str(server.path),
        )
    console.print(table)


@cli.command("inspect")
@click.argument("path")
@click.option("--json", "json_output", is_flag=True, help="Print machine-readable JSON.")
def inspect_cmd(path: str, json_output: bool) -> None:
    """Inspect a generated MCP server without running it."""
    info = inspect_server(Path(path))
    if json_output:
        _print_json(info)
        return

    table = Table(title=f"mcpforge inspect: {info['name']}")
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("Path", info["path"])
    table.add_row("Language", info["language"])
    table.add_row(
        "Tools", f"{info['tools']['count']} ({', '.join(info['tools']['names']) or 'none'})"
    )
    table.add_row(
        "Resources",
        f"{info['resources']['count']} ({', '.join(info['resources']['names']) or 'none'})",
    )
    table.add_row(
        "Prompts", f"{info['prompts']['count']} ({', '.join(info['prompts']['names']) or 'none'})"
    )
    table.add_row("Tests", "present" if info["tests"]["present"] else "missing")
    table.add_row("Env Vars", ", ".join(info["env_vars"]) or "none")
    table.add_row("Remote MCP Ready", "yes" if info["remote_mcp"]["ready"] else "no")
    table.add_row("Validation Ready", "yes" if info["validation_ready"] else "no")
    if info["missing_files"]:
        table.add_row("Missing", ", ".join(info["missing_files"]))
    console.print(table)


@cli.command("doctor")
@click.option("--path", "workspace", default=".", help="Workspace path to check for writability.")
@click.option("--json", "json_output", is_flag=True, help="Print machine-readable JSON.")
def doctor_cmd(workspace: str, json_output: bool) -> None:
    """Check local mcpforge prerequisites and provider readiness."""
    report = run_doctor(Path(workspace))
    if json_output:
        _print_json(report)
        return

    table = Table(title="mcpforge doctor")
    table.add_column("Check", style="cyan")
    table.add_column("Result")
    table.add_row(
        "Python", f"{'OK' if report['python']['ok'] else 'FAIL'} {report['python']['version']}"
    )
    for command in report["commands"]:
        table.add_row(command["name"], "OK" if command["ok"] else "missing")
    table.add_row("FastMCP", report["packages"]["fastmcp"] or "not installed")
    table.add_row("Anthropic key", "set" if report["anthropic_api_key"]["ok"] else "not set")
    table.add_row("OpenAI key", "set" if report["openai_api_key"]["ok"] else "not set")
    table.add_row("Workspace writable", "yes" if report["workspace"]["ok"] else "no")
    table.add_row("Default provider", report["provider"]["default_provider"])
    table.add_row("Default model", report["provider"]["default_model"])
    console.print(table)
    if not report["ok"]:
        raise SystemExit(1)


@cli.command()
@click.argument("name")
@click.option(
    "--output",
    "-o",
    default=None,
    metavar="PATH",
    help="Output directory (default: ./<slug>)",
)
@click.option(
    "--transport",
    "-t",
    default="streamable-http",
    show_default=True,
    type=click.Choice(["streamable-http", "stdio", "sse"], case_sensitive=False),
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    default=False,
    help="Overwrite existing output directory.",
)
@click.option(
    "--auth-profile",
    default="none",
    show_default=True,
    type=click.Choice(["none", "api-key", "jwt"], case_sensitive=False),
    help="Add optional Python auth profile metadata and env docs.",
)
@click.option(
    "--middleware-profile",
    "middleware_profiles",
    multiple=True,
    type=click.Choice(["logging", "timing", "rate-limit"], case_sensitive=False),
    help="Add optional Python middleware profile. Repeatable.",
)
def init(
    name: str,
    output: str | None,
    transport: str,
    force: bool,
    auth_profile: str,
    middleware_profiles: tuple[str, ...],
) -> None:
    """Scaffold a minimal FastMCP server named NAME without LLM generation."""
    from jinja2 import BaseLoader
    from jinja2.sandbox import SandboxedEnvironment

    # Build a minimal plan for template rendering
    plan = ServerPlan(
        name=name,
        description=f"A FastMCP server named {name}",
        tools=[ToolDef(name="echo", description="Echo a message", params=[])],
        transport=transport,
    )
    plan = apply_generation_profiles(
        plan,
        auth_profile=auth_profile,
        middleware_profiles=middleware_profiles,
    )
    output_path = Path(output) if output else Path(plan.slug)

    env = SandboxedEnvironment(loader=BaseLoader(), autoescape=False)
    context = {"plan": plan}

    server_tmpl = _load_init_template("init_server.py.j2")
    test_tmpl = _load_init_template("init_test.py.j2")
    server_code = env.from_string(server_tmpl).render(**context)
    test_code = env.from_string(test_tmpl).render(**context)

    try:
        write_server(plan, server_code, test_code, output_path, force=force)
    except FileExistsError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise SystemExit(1)

    console.print(f"[green]✓[/green] Scaffolded [bold]{name}[/bold] at {output_path}")
    console.print(f"[dim]cd {output_path} && uv sync && uv run pytest[/dim]")

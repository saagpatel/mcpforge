"""Click CLI entrypoint for mcpforge."""

import click
from rich.console import Console

from mcpforge import __version__

console = Console()


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
def generate(
    description: str,
    output: str | None,
    model: str,
    transport: str,
    dry_run: bool,
    yes: bool,
) -> None:
    """Generate a complete MCP server from a plain-English DESCRIPTION."""
    console.print(
        "[yellow]mcpforge generate[/yellow] is not yet implemented (Phase 1).",
        highlight=False,
    )


@cli.command()
@click.argument("path")
def validate(path: str) -> None:
    """Validate an existing MCP server at PATH."""
    console.print(
        "[yellow]mcpforge validate[/yellow] is not yet implemented (Phase 1).",
        highlight=False,
    )


@cli.command("version")
def version_cmd() -> None:
    """Print the mcpforge version."""
    console.print(f"mcpforge {__version__}")

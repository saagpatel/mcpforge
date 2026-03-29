"""Prompt loading utilities for mcpforge."""

from importlib.resources import files


def load_prompt(name: str) -> str:
    """Load a prompt file by name (without .md extension).

    Reads from the prompts/ directory within the installed package using
    importlib.resources, which works correctly from both source tree and
    installed wheel.

    Args:
        name: Prompt name without extension, e.g. "planner", "generator", "test_gen".

    Returns:
        The full text content of the prompt file.

    Raises:
        FileNotFoundError: If no prompt file with that name exists.
    """
    prompt_file = files("mcpforge.prompts").joinpath(f"{name}.md")
    return prompt_file.read_text(encoding="utf-8")

"""Writer: scaffolds the output directory with all generated files.

Phase 1 implementation.
"""

from pathlib import Path

from mcpforge.models import ServerPlan


def write_server(
    plan: ServerPlan,
    server_code: str,
    test_code: str,
    output_dir: Path,
) -> Path:
    """Write all generated files to the output directory.

    Creates:
        - server.py (generated server code)
        - test_server.py (generated test suite)
        - pyproject.toml (from Jinja2 template)
        - README.md (from Jinja2 template)
        - config.json (MCP client configuration, from Jinja2 template)

    Args:
        plan: The ServerPlan used to generate the server.
        server_code: Generated server.py source code.
        test_code: Generated test_server.py source code.
        output_dir: Target directory (created if it does not exist).

    Returns:
        Path to the output directory.
    """
    raise NotImplementedError("writer.write_server is implemented in Phase 1")

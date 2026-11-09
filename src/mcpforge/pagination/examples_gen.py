"""Deterministic, self-contained FastMCP pagination example projects."""

from __future__ import annotations

import json
import re
from pathlib import Path

from mcpforge.pagination.datasets import load_datasets
from mcpforge.pagination.docs_gen import render_pattern_doc
from mcpforge.pagination.patterns import DEFINITIONS

EXAMPLES_DIR = Path(__file__).parents[3] / "examples" / "pagination"
_SOURCE = Path(__file__).parents[1]

# Keep protocol integration separate from the unmodified vendored adapters.
_SERVER = '''"""Bundled synthetic records; no provider, credentials, or network required."""

import json
import secrets
from importlib.resources import files

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from mcp import McpError, types

from ._vendor.contracts import FailureContract, ToolOutcome, resolve_outcome
from ._vendor.pagination import CursorCodec, InvalidCursorError, PaginationError
from ._vendor.pagination.harness import MutatingUpstream

DATASET = json.loads(files(__package__).joinpath("dataset.json").read_text())
PATTERN = DATASET["pattern"]
PAGE_SIZE = DATASET["page_size"]
CONTRACT = FailureContract(retryable=True, partial_result_allowed=True)
# Process-lifetime keys intentionally invalidate cursors on server restart.
TOOL_CODEC = CursorCodec(secrets.token_bytes(32))
RESOURCE_CODEC = CursorCodec(secrets.token_bytes(32))
SOURCE = MutatingUpstream(DATASET["items"], DATASET["mutations"])


def invalid_params(exc: InvalidCursorError) -> McpError:
    return McpError(types.ErrorData(**exc.to_jsonrpc_error()))


class RecordServer(FastMCP):
    async def _list_resources_mcp(self, request: types.ListResourcesRequest):
        """Use native list pagination, authenticating its cursor with our codec."""
        cursor = request.params.cursor if request.params else None
        native = None
        if cursor is not None:
            try:
                state = RESOURCE_CODEC.decode(cursor)
                if (
                    set(state) != {"method", "pattern", "cursor"}
                    or state["method"] != "resources/list"
                    or state["pattern"] != PATTERN
                    or not isinstance(state["cursor"], str)
                    or not state["cursor"]
                ):
                    raise InvalidCursorError("invalid resource cursor state")
                native = state["cursor"]
            except InvalidCursorError as exc:
                raise invalid_params(exc) from exc
        native_request = types.ListResourcesRequest(
            method="resources/list", params=types.PaginatedRequestParams(cursor=native)
        )
        result = await super()._list_resources_mcp(native_request)
        if result.nextCursor is not None:
            result.nextCursor = RESOURCE_CODEC.encode(
                {"method": "resources/list", "pattern": PATTERN, "cursor": result.nextCursor}
            )
        return result


mcp = RecordServer("Pagination __PATTERN__", list_page_size=PAGE_SIZE)


def page_result(envelope: dict) -> ToolResult:
    """Partial data is normal; only a failed outcome signals a tool error."""
    return ToolResult(
        structured_content=envelope, is_error=envelope["outcome"]["status"] == "failed"
    )


@mcp.tool
def list_records(cursor: str | None = None) -> ToolResult:
    """Read one upstream page. Absence of nextCursor establishes exhaustion."""
    adapter = SOURCE.adapter(PATTERN, PAGE_SIZE, codec=TOOL_CODEC, resume_cursor=cursor)
    try:
        page = adapter.fetch_page(adapter.initial_state)
        envelope = page.to_mcp(adapter)
        # Complete describes this page read; traversal ends only without nextCursor.
        envelope["outcome"] = ToolOutcome(status="complete", failure=None).model_dump()
    except PaginationError as exc:
        outcome = resolve_outcome(CONTRACT, exc.kind, False, str(exc))
        envelope = {"items": [], "outcome": outcome.model_dump()}
    return page_result(envelope)


# The SDK turns tool exceptions into isError results. Validate cursors outside
# that wrapper so invalid client params retain their JSON-RPC -32602 code.
_call_tool = mcp._mcp_server.request_handlers[types.CallToolRequest]


async def checked_call_tool(request: types.CallToolRequest):
    if request.params.name == "list_records":
        cursor = (request.params.arguments or {}).get("cursor")
        if cursor is not None:
            try:
                SOURCE.adapter(PATTERN, PAGE_SIZE, codec=TOOL_CODEC, resume_cursor=cursor)
            except InvalidCursorError as exc:
                raise invalid_params(exc) from exc
    return await _call_tool(request)


mcp._mcp_server.request_handlers[types.CallToolRequest] = checked_call_tool


def register_record(item):
    def read_record() -> str:
        return json.dumps(item, sort_keys=True)

    mcp.resource(f"record://records/{item['id']}", name=f"record_{item['id']}")(read_record)


for _record in DATASET["items"]:
    register_record(_record)


def main():
    mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
'''

_TEST = '''"""Exercise the installed example through MCP (install pytest separately)."""

import asyncio

from fastmcp import Client
from __PACKAGE__.server import DATASET, mcp


def test_pages():
    async def run():
        async with Client(mcp) as client:
            items = []
            arguments = {}
            for _ in range(len(DATASET["items"]) + 1):
                result = await client.call_tool("list_records", arguments)
                page = result.structured_content
                items.extend(page["items"])
                if "nextCursor" not in page:
                    break
                arguments = {"cursor": page["nextCursor"]}
            else:
                raise AssertionError("pagination did not terminate")
            assert items == DATASET["items"]
            assert len({item["id"] for item in items}) == len(items)

    asyncio.run(run())
'''


def _vendor_imports(source: str, relative: Path) -> str:
    """Relocate internal imports without depending on the forge installation."""
    current = relative.parts[:-1]

    def replace(match: re.Match) -> str:
        target = match[1].split(".")
        shared = 0
        while shared < min(len(current), len(target)) and current[shared] == target[shared]:
            shared += 1
        prefix = "." * (len(current) - shared + 1)
        return "from " + prefix + ".".join(target[shared:]) + " import"

    return re.sub(r"from mcpforge\.([\w.]+) import", replace, source)


def render_example(pattern: str) -> dict[str, str]:
    """Return all project sources, keyed by project-relative POSIX path."""
    definition = next((item for item in DEFINITIONS if item.pattern == pattern), None)
    if definition is None:
        raise ValueError(f"unsupported pagination pattern: {pattern}")
    package = f"pagination_{pattern}"
    dataset = next(d for d in load_datasets() if d.id.endswith(f"-{pattern}-stable"))
    result = {
        "pyproject.toml": f'''[project]
name = "pagination-{pattern.replace("_", "-")}-server"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["fastmcp>=3.4.10,<4"]

[project.scripts]
pagination-{pattern.replace("_", "-")}-server = "{package}.server:main"

[build-system]
requires = ["uv_build>=0.13.0,<0.14.0"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "{package}"
''',
        f"src/{package}/__init__.py": '"""Self-contained pagination example."""\n',
        f"src/{package}/server.py": _SERVER.replace("__PATTERN__", pattern),
        f"src/{package}/dataset.json": json.dumps(dataset.model_dump(mode="json"), indent=2) + "\n",
        f"src/{package}/_vendor/__init__.py": '"""Vendored forge contract runtime."""\n',
        "tests/test_server.py": _TEST.replace("__PACKAGE__", package),
        "README.md": f"""# {pattern} pagination server

Install with `uv pip install .`, then run `pagination-{pattern.replace("_", "-")}-server`
over stdio. For the bundled test, install pytest and run `pytest tests`.
Only FastMCP is a direct runtime dependency; adapters and contracts are vendored.
The bundled stable dataset uses page size {dataset.page_size}.

`list_records` returns one upstream page with `items`, optional `nextCursor`, and
`outcome`. A complete outcome describes that page read; only absence of
`nextCursor` establishes traversal exhaustion. Failed outcomes set `isError`;
incomplete outcomes carry partial data as a normal result.

The same records are readable MCP resources. `resources/list` uses FastMCP's
native list pagination with its cursor wrapped in the vendored HMAC codec.
Both interfaces reject invalid cursors with JSON-RPC code -32602. Keys last for
one server process; cursors are opaque, authenticated, and not encrypted.
Tool and resource cursors cannot be interchanged. This example covers
`resources/list`, not all MCP list methods or a live upstream.

{render_pattern_doc(definition)}""",
    }
    runtime_files = [
        "contracts/__init__.py",
        "contracts/outcome.py",
        "pagination/__init__.py",
        "pagination/adapter.py",
        "pagination/cursor_codec.py",
        "pagination/harness.py",
        "pagination/traverse.py",
        "pagination/patterns/__init__.py",
        "pagination/patterns/cursor.py",
        "pagination/patterns/offset.py",
        "pagination/patterns/page_token.py",
    ]
    for name in runtime_files:
        source = (_SOURCE / name).read_text(encoding="utf-8")
        # ToolDef is only used for type checking by default_contract, which the
        # example does not invoke. Keep this vendor independent of forge models.
        if name == "contracts/outcome.py":
            source = source.replace("TYPE_CHECKING, ", "")
            source = source.replace(
                "if TYPE_CHECKING:\n    from mcpforge.models import ToolDef\n\n", ""
            )
            source = source.replace('tool: "ToolDef"', "tool")
        result[f"src/{package}/_vendor/{name}"] = _vendor_imports(source, Path(name))
    return result


def generate_example(pattern: str, output_dir: str | Path) -> Path:
    """Emit a project without deleting unrelated existing output files."""
    rendered = render_example(pattern)
    output = Path(output_dir)
    for name, content in rendered.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
    return output


def generate_examples(output_dir: str | Path = EXAMPLES_DIR) -> list[Path]:
    return [
        generate_example(d.pattern, Path(output_dir) / f"{d.pattern}-server") for d in DEFINITIONS
    ]

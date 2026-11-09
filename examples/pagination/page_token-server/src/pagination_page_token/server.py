"""Bundled synthetic records; no provider, credentials, or network required."""

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


mcp = RecordServer("Pagination page_token", list_page_size=PAGE_SIZE)


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


# Validate cursors outside the SDK wrapper so invalid client params retain
# JSON-RPC -32602 instead of becoming ordinary tool execution failures.
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

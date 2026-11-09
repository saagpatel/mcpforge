"""Exercise the installed example through MCP (install pytest separately)."""

import asyncio

from fastmcp import Client
from pagination_offset.server import DATASET, mcp


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

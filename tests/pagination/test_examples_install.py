"""Install each example in a fresh venv, then inspect real stdio JSON-RPC.

Installation is offline, using the uv cache populated by make setup. Only when
CI is set may a cold-cache install retry with network access. Local cache misses
fail. No editable forge package or repository PYTHONPATH reaches the servers.
The cache needs resolver metadata as well as wheels; a fresh locked sync can
cache only wheels. Such a local cache must be primed before running this test.
"""

import json
import os
import subprocess
import sys
import tomllib
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

import anyio
import pytest
from mcp import ClientSession, McpError, StdioServerParameters, types
from mcp.client.stdio import stdio_client

from mcpforge.pagination.examples_gen import EXAMPLES_DIR

pytestmark = pytest.mark.examples_install
PATTERNS = ("cursor", "offset", "page_token")


def run_uv(*arguments):
    return subprocess.run(
        ["uv", *map(str, arguments)], capture_output=True, text=True, timeout=120, check=False
    )


@pytest.fixture(params=PATTERNS)
def installed_example(request, tmp_path):
    example = EXAMPLES_DIR / f"{request.param}-server"
    environment = tmp_path / "venv"
    created = run_uv("venv", "--python", sys.executable, environment)
    assert created.returncode == 0, created.stderr
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    # Match the locked runtime that setup cached, rather than resolving newer,
    # uncached transitive releases from existing package-index metadata.
    lock = tomllib.loads((Path(__file__).parents[2] / "uv.lock").read_text())
    constraints = tmp_path / "constraints.txt"
    constraints.write_text(
        "\n".join(
            f"{p['name']}=={p['version']}" for p in lock["package"] if "registry" in p["source"]
        )
        + "\n"
    )
    arguments = ["pip", "install", "--constraint", constraints, "--python", python, example]
    installed = run_uv(*arguments, "--offline")
    if installed.returncode and os.environ.get("CI"):
        installed = run_uv(*arguments)
    assert installed.returncode == 0, installed.stderr
    package = f"pagination_{request.param}"
    probe = subprocess.run(
        [
            str(python),
            "-I",
            "-c",
            "import importlib.util; "
            "assert importlib.util.find_spec('mcpforge') is None; "
            f"import {package}.server as s; print(s.__file__)",
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert probe.returncode == 0, probe.stderr
    assert str(environment) in probe.stdout
    suffix = ".exe" if os.name == "nt" else ""
    executable = python.parent / f"pagination-{request.param.replace('_', '-')}-server{suffix}"
    return executable, package, python, tmp_path


@asynccontextmanager
async def recorded_session(command, args, cwd):
    """Record JSON-RPC envelopes before ClientSession parses result schemas."""
    responses = []
    params = StdioServerParameters(command=str(command), args=args, cwd=cwd)
    async with stdio_client(params) as (read, write):
        sender, receiver = anyio.create_memory_object_stream(16)

        async def forward():
            async with sender:
                async for message in read:
                    if not isinstance(message, Exception):
                        root = message.message.root
                        if isinstance(root, (types.JSONRPCResponse, types.JSONRPCError)):
                            responses.append(root.model_dump(by_alias=True, exclude_none=True))
                    await sender.send(message)

        async with anyio.create_task_group() as group:
            group.start_soon(forward)
            async with ClientSession(
                receiver, write, read_timeout_seconds=timedelta(seconds=20)
            ) as session:
                await session.initialize()
                yield session, responses
            group.cancel_scope.cancel()


def tamper(cursor):
    body, signature = cursor.split(".")
    return body + "." + ("A" if signature[0] != "A" else "B") + signature[1:]


def tool_response(responses):
    # ClientSession can issue tools/list after tools/call to check output schemas.
    return next(
        response["result"]
        for response in reversed(responses)
        if "content" in response.get("result", {})
    )


async def assert_invalid(session, responses, *, method, cursor):
    with pytest.raises(McpError) as raised:
        if method == "resources/list":
            await session.list_resources(cursor=cursor)
        else:
            await session.call_tool("list_records", {"cursor": cursor})
    assert raised.value.error.code == -32602
    assert responses[-1]["error"]["code"] == -32602
    assert "result" not in responses[-1]


async def test_installed_stdio_pagination_and_invalid_cursors(installed_example):
    executable, package, _, directory = installed_example
    dataset = json.loads(
        (EXAMPLES_DIR / f"{package.removeprefix('pagination_')}-server")
        .joinpath("src", package, "dataset.json")
        .read_text()
    )
    async with recorded_session(executable, [], directory) as (session, responses):
        items = []
        cursor = None
        tool_cursor = None
        for _ in range(len(dataset["items"]) + 1):
            result = await session.call_tool("list_records", {"cursor": cursor})
            wire = tool_response(responses)
            assert wire.get("isError", False) is False
            assert "structuredContent" in wire, wire
            page = wire["structuredContent"]
            assert result.structuredContent == page
            assert page["outcome"] == {"status": "complete", "failure": None}
            assert len(page["items"]) <= dataset["page_size"]
            items.extend(page["items"])
            if "nextCursor" not in page:
                break
            cursor = page["nextCursor"]
            tool_cursor = tool_cursor or cursor
        else:
            pytest.fail("tool pagination never terminated")
        assert items == dataset["items"]
        assert len({item["id"] for item in items}) == len(items)

        uris = []
        cursor = None
        resource_cursor = None
        for _ in range(len(dataset["items"]) + 1):
            await session.list_resources(cursor=cursor)
            page = responses[-1]["result"]
            assert len(page["resources"]) <= dataset["page_size"]
            uris.extend(resource["uri"] for resource in page["resources"])
            if "nextCursor" not in page:
                break
            cursor = page["nextCursor"]
            resource_cursor = resource_cursor or cursor
        else:
            pytest.fail("resource pagination never terminated")
        assert len(uris) == len(set(uris)) == len(items)
        assert set(uris) == {f"record://records/{item['id']}" for item in items}
        for uri in uris:
            result = await session.read_resource(uri)
            assert json.loads(result.contents[0].text) in items

        assert tool_cursor and resource_cursor
        for method, valid, other in (
            ("tools/call", tool_cursor, resource_cursor),
            ("resources/list", resource_cursor, tool_cursor),
        ):
            for invalid in (tamper(valid), "", "not-a-cursor", other):
                await assert_invalid(session, responses, method=method, cursor=invalid)

    # New process keys must not accept cursors issued by a previous process.
    async with recorded_session(executable, [], directory) as (session, responses):
        await assert_invalid(session, responses, method="tools/call", cursor=tool_cursor)
        await assert_invalid(session, responses, method="resources/list", cursor=resource_cursor)


async def test_installed_failed_and_incomplete_tool_signalling(installed_example):
    _, package, python, directory = installed_example
    # Exercise the real stdio handler using a faulted harness, without adding a
    # public fixture-control option to the example server.
    script = f"""
import {package}.server as s
from {package}._vendor.pagination import traverse
from {package}._vendor.pagination.harness import MutatingUpstream

s.SOURCE = MutatingUpstream([{{'id': 1, 'order': 1}}, {{'id': 1, 'order': 2}}])

@s.mcp.tool
def partial_records():
    source = MutatingUpstream(s.DATASET['items'])
    result = traverse(source.adapter(s.PATTERN, s.PAGE_SIZE), s.CONTRACT, 1)
    return s.page_result({{'items': result.items, 'outcome': result.outcome.model_dump()}})

s.main()
"""
    async with recorded_session(python, ["-I", "-c", script], directory) as (session, responses):
        failed = await session.call_tool("list_records", {})
        assert failed.isError
        wire = tool_response(responses)
        assert wire["isError"] is True
        envelope = wire["structuredContent"]
        assert envelope["items"] == []
        assert envelope["outcome"]["status"] == "failed"
        assert envelope["outcome"]["failure"]["kind"] == "page_shifted"
        incomplete = await session.call_tool("partial_records", {})
        assert not incomplete.isError
        wire = tool_response(responses)
        assert wire.get("isError", False) is False
        envelope = wire["structuredContent"]
        assert envelope["items"]
        assert envelope["outcome"]["status"] == "incomplete"
        assert envelope["outcome"]["failure"]["partial_result"] is True

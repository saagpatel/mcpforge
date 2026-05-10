"""Test generator: produces test_server.py source code from a ServerPlan and server code."""

import json
import logging
from pprint import pformat
from textwrap import indent

from mcpforge.api_client import AnthropicClient
from mcpforge.models import ServerPlan, ToolDef, ToolParam
from mcpforge.prompts import load_prompt
from mcpforge.utils import strip_code_fences

logger = logging.getLogger(__name__)


def _is_openapi_plan(plan: ServerPlan) -> bool:
    """Return True when the plan contains OpenAPI-derived HTTP operations."""
    return any(tool.method and tool.path for tool in plan.tools)


def _sample_value(param: ToolParam) -> object:
    """Return a deterministic sample value for a generated tool parameter."""
    param_type = param.type.lower()
    if param_type in {"int", "integer"}:
        return 1
    if param_type in {"float", "number"}:
        return 1.5
    if param_type in {"bool", "boolean"}:
        return True
    if param_type.startswith("list"):
        return [{"example": "value"}]
    if param_type.startswith("dict"):
        return {"example": "value"}
    return f"sample-{param.name}"


def _sample_args(tool: ToolDef) -> dict[str, object]:
    """Build call arguments for every required and optional OpenAPI tool parameter."""
    return {param.name: _sample_value(param) for param in tool.params}


def _expected_call(tool: ToolDef) -> dict[str, object]:
    """Build expected HTTP call assertions for a generated OpenAPI tool."""
    args = _sample_args(tool)
    query_params = {
        param.name: args[param.name] for param in tool.params if param.location == "query"
    }
    path_values = {
        param.name: args[param.name] for param in tool.params if param.location == "path"
    }
    body_param = next((param for param in tool.params if param.location == "body"), None)
    headers: dict[str, object] = {}
    query_auth: dict[str, object] = {}
    cookies: dict[str, object] = {}
    auth_value = "test-secret"
    if tool.auth in {"bearer", "oauth2"}:
        headers["Authorization"] = f"Bearer {auth_value}"
    elif tool.auth == "api_key":
        auth_name = tool.auth_parameter_name or "X-API-Key"
        if tool.auth_location == "query":
            query_auth[auth_name] = auth_value
        elif tool.auth_location == "cookie":
            cookies[auth_name] = auth_value
        else:
            headers[auth_name] = auth_value

    return {
        "args": args,
        "auth_env_var": tool.auth_env_var,
        "body": args[body_param.name] if body_param else None,
        "cookies": cookies,
        "headers": headers,
        "method": tool.method,
        "path": tool.path,
        "path_values": path_values,
        "query": {**query_params, **query_auth},
        "tool": tool.name,
    }


def _generate_openapi_tests(plan: ServerPlan) -> str:
    """Generate deterministic tests for OpenAPI/httpx-backed MCP tools."""
    expected_calls = [_expected_call(tool) for tool in plan.tools if tool.method and tool.path]
    env_vars = {
        env_var: ("30" if env_var == "REQUEST_TIMEOUT_SECONDS" else "test-secret")
        for env_var in plan.env_vars
    }
    env_vars.setdefault("BASE_URL", "https://api.example.test")
    env_vars.setdefault("REQUEST_TIMEOUT_SECONDS", "30")
    if plan.auth_profile and plan.auth_profile != "none":
        env_vars.setdefault("MCPFORGE_SERVER_API_KEY", "test-server-secret")

    expected_literal = indent(pformat(expected_calls, width=88), "    ").lstrip()
    env_literal = indent(pformat(env_vars, width=88), "    ").lstrip()

    return f'''"""Deterministic tests for the {plan.name} MCP server."""

import pytest
from fastmcp import Client

import server
from server import mcp


EXPECTED_CALLS = {expected_literal}

ENV_VARS = {env_literal}


class FakeResponse:
    """Small httpx.Response stand-in for generated OpenAPI tool tests."""

    def __init__(self, payload: dict | None = None, status_code: int = 200) -> None:
        self._payload = payload or {{"ok": True}}
        self.status_code = status_code
        self.text = str(self._payload)
        self.is_error = status_code >= 400

    def json(self) -> dict:
        """Return the configured fake payload."""
        return self._payload

    def raise_for_status(self) -> None:
        """Match httpx.Response's success behavior."""
        if self.is_error:
            raise RuntimeError(f"Upstream error {{self.status_code}}: {{self.text}}")


class FakeAsyncClient:
    """Capture generated HTTP requests without touching the network."""

    calls: list[dict] = []

    def __init__(self, *args, **kwargs) -> None:
        self.init_args = args
        self.init_kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def request(self, method: str, url: str, **kwargs) -> FakeResponse:
        self.calls.append({{"method": method.upper(), "url": url, "kwargs": kwargs}})
        return FakeResponse({{"ok": True, "url": str(url)}})

    async def get(self, url: str, **kwargs) -> FakeResponse:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> FakeResponse:
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs) -> FakeResponse:
        return await self.request("PUT", url, **kwargs)

    async def patch(self, url: str, **kwargs) -> FakeResponse:
        return await self.request("PATCH", url, **kwargs)

    async def delete(self, url: str, **kwargs) -> FakeResponse:
        return await self.request("DELETE", url, **kwargs)

    async def head(self, url: str, **kwargs) -> FakeResponse:
        return await self.request("HEAD", url, **kwargs)

    async def options(self, url: str, **kwargs) -> FakeResponse:
        return await self.request("OPTIONS", url, **kwargs)


@pytest.fixture(autouse=True)
def configure_openapi_test_environment(monkeypatch):
    """Configure generated OpenAPI tests without requiring real credentials."""
    FakeAsyncClient.calls.clear()
    for key, value in ENV_VARS.items():
        monkeypatch.setenv(key, value)
    if hasattr(server, "BASE_URL"):
        monkeypatch.setattr(server, "BASE_URL", ENV_VARS["BASE_URL"].rstrip("/"))
    if hasattr(server, "REQUEST_TIMEOUT_SECONDS"):
        monkeypatch.setattr(server, "REQUEST_TIMEOUT_SECONDS", 30.0)
    if hasattr(server, "httpx"):
        monkeypatch.setattr(server.httpx, "AsyncClient", FakeAsyncClient)
    if hasattr(server, "AsyncClient"):
        monkeypatch.setattr(server, "AsyncClient", FakeAsyncClient)
    yield


def _assert_contains_auth(headers: dict, expected_headers: dict) -> None:
    normalized = {{str(key).lower(): value for key, value in headers.items()}}
    for key, value in expected_headers.items():
        assert normalized.get(str(key).lower()) == value


def _assert_http_call(expected: dict) -> None:
    assert FakeAsyncClient.calls, "Expected generated tool to make an HTTP request"
    call = FakeAsyncClient.calls[-1]
    assert call["method"] == expected["method"]
    url = str(call["url"])
    assert "{{" not in url and "}}" not in url
    for value in expected["path_values"].values():
        assert str(value) in url
    kwargs = call["kwargs"]
    params = kwargs.get("params") or {{}}
    for key, value in expected["query"].items():
        assert params.get(key) == value
    if expected["headers"]:
        _assert_contains_auth(kwargs.get("headers") or {{}}, expected["headers"])
    if expected["cookies"]:
        cookies = kwargs.get("cookies") or {{}}
        for key, value in expected["cookies"].items():
            assert cookies.get(key) == value
    if expected["body"] is not None:
        assert kwargs.get("json") == expected["body"]


@pytest.mark.parametrize("expected", EXPECTED_CALLS, ids=[item["tool"] for item in EXPECTED_CALLS])
async def test_openapi_tool_http_wiring(expected: dict) -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(expected["tool"], expected["args"])

    assert result.data["ok"] is True
    _assert_http_call(expected)


@pytest.mark.parametrize("expected", EXPECTED_CALLS, ids=[item["tool"] for item in EXPECTED_CALLS])
async def test_openapi_tool_requires_downstream_auth(expected: dict, monkeypatch) -> None:
    auth_env = expected.get("auth_env_var")
    if not auth_env:
        pytest.skip("tool has no downstream auth environment variable")
    monkeypatch.delenv(auth_env, raising=False)
    if hasattr(server, "httpx"):
        monkeypatch.setattr(server.httpx, "AsyncClient", FakeAsyncClient)

    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool(expected["tool"], expected["args"])
'''


async def generate_tests(plan: ServerPlan, server_code: str, client: AnthropicClient) -> str:
    """Generate pytest test suite for the generated server."""
    if _is_openapi_plan(plan):
        return _generate_openapi_tests(plan)

    system_prompt = load_prompt("test_gen")
    user_message = json.dumps(
        {"plan": json.loads(plan.model_dump_json()), "server_code": server_code},
        indent=2,
    )
    raw = await client.generate(
        system_prompt=system_prompt,
        user_message=user_message,
        max_tokens=16384,
        temperature=0.2,
    )
    return strip_code_fences(raw)

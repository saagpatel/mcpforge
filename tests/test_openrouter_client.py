"""Tests for the OpenRouter "bring any model" provider client."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from mcpforge.openrouter_client import (
    DEFAULT_OPENROUTER_MODEL,
    OPENROUTER_BASE_URL,
    OpenRouterClient,
)


class StructuredSmoke(BaseModel):
    """Tiny response model for structured-output smokes."""

    name: str
    count: int


def _client_with(completions: MagicMock) -> MagicMock:
    chat = MagicMock()
    chat.completions = completions
    openai_client = MagicMock()
    openai_client.chat = chat
    return openai_client


async def test_generate_json_uses_chat_parse_and_returns_model() -> None:
    parsed = StructuredSmoke(name="tickets", count=2)
    completions = MagicMock()
    completions.parse = AsyncMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))]
        )
    )

    with patch("mcpforge.openrouter_client.AsyncOpenAI", return_value=_client_with(completions)):
        client = OpenRouterClient(api_key="test-key", model="anthropic/claude-opus-4.8")
        result = await client.generate_json("system", "user", StructuredSmoke)

    assert result == parsed
    _, kwargs = completions.parse.call_args
    assert kwargs["model"] == "anthropic/claude-opus-4.8"
    assert kwargs["response_format"] is StructuredSmoke
    assert kwargs["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "user"},
    ]
    # Force schema-honoring providers so OpenRouter cannot silently fall back to json_object.
    assert kwargs["extra_body"] == {"provider": {"require_parameters": True}}
    # Structured output never carries a sampling param.
    assert "temperature" not in kwargs


async def test_generate_json_rejects_unparsed_response() -> None:
    completions = MagicMock()
    completions.parse = AsyncMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(parsed={"name": "tickets"}))]
        )
    )

    with patch("mcpforge.openrouter_client.AsyncOpenAI", return_value=_client_with(completions)):
        client = OpenRouterClient(api_key="test-key", model="some/cheap-model")
        with pytest.raises(ValueError, match="did not match StructuredSmoke schema"):
            await client.generate_json("system", "user", StructuredSmoke)


async def test_generate_uses_chat_create_for_plain_text() -> None:
    completions = MagicMock()
    completions.create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hello"))]
        )
    )

    with patch("mcpforge.openrouter_client.AsyncOpenAI", return_value=_client_with(completions)):
        client = OpenRouterClient(api_key="test-key")
        result = await client.generate("system", "user")

    assert result == "hello"
    _, kwargs = completions.create.call_args
    assert kwargs["model"] == DEFAULT_OPENROUTER_MODEL


async def test_generate_raises_on_empty_content() -> None:
    completions = MagicMock()
    completions.create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None))]
        )
    )

    with patch("mcpforge.openrouter_client.AsyncOpenAI", return_value=_client_with(completions)):
        client = OpenRouterClient(api_key="test-key")
        with pytest.raises(ValueError, match="empty response"):
            await client.generate("system", "user")


async def test_generate_stream_yields_content_deltas() -> None:
    chunks = ["Hello", ", ", "world"]

    async def _fake_stream():
        for chunk in chunks:
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=chunk))])

    completions = MagicMock()
    completions.create = AsyncMock(return_value=_fake_stream())

    with patch("mcpforge.openrouter_client.AsyncOpenAI", return_value=_client_with(completions)):
        client = OpenRouterClient(api_key="test-key")
        result = [chunk async for chunk in client.generate_stream("system", "user")]

    assert result == chunks
    _, kwargs = completions.create.call_args
    assert kwargs["stream"] is True


async def test_stream_skips_empty_deltas() -> None:
    async def _fake_stream():
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="a"))])
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None))])
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="b"))])

    completions = MagicMock()
    completions.create = AsyncMock(return_value=_fake_stream())

    with patch("mcpforge.openrouter_client.AsyncOpenAI", return_value=_client_with(completions)):
        client = OpenRouterClient(api_key="test-key")
        result = [chunk async for chunk in client.generate_stream("system", "user")]

    assert result == ["a", "b"]


async def test_stream_skips_usage_only_chunks() -> None:
    """OpenRouter can append a tail chunk with empty choices; it must not crash."""

    async def _fake_stream():
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="hi"))])
        yield SimpleNamespace(choices=[])  # usage-only tail chunk

    completions = MagicMock()
    completions.create = AsyncMock(return_value=_fake_stream())

    with patch("mcpforge.openrouter_client.AsyncOpenAI", return_value=_client_with(completions)):
        client = OpenRouterClient(api_key="test-key")
        result = [chunk async for chunk in client.generate_stream("system", "user")]

    assert result == ["hi"]


async def test_points_client_at_openrouter_base_url() -> None:
    completions = MagicMock()
    completions.create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]
        )
    )

    with patch(
        "mcpforge.openrouter_client.AsyncOpenAI", return_value=_client_with(completions)
    ) as mock_ctor:
        OpenRouterClient(api_key="test-key")

    _, kwargs = mock_ctor.call_args
    assert kwargs["base_url"] == OPENROUTER_BASE_URL
    assert kwargs["api_key"] == "test-key"


async def test_missing_api_key_raises(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OpenRouter API key is required"):
        OpenRouterClient()

"""Tests for the gated OpenAI provider client."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from mcpforge.openai_client import DEFAULT_OPENAI_MODEL, OpenAIClient


class StructuredSmoke(BaseModel):
    """Tiny response model for structured-output smokes."""

    name: str
    count: int


async def test_generate_json_uses_responses_parse_and_returns_pydantic_model() -> None:
    parsed = StructuredSmoke(name="tickets", count=2)
    responses = MagicMock()
    responses.parse = AsyncMock(return_value=SimpleNamespace(output_parsed=parsed))
    openai_client = MagicMock()
    openai_client.responses = responses

    with patch("mcpforge.openai_client.AsyncOpenAI", return_value=openai_client):
        client = OpenAIClient(api_key="test-key")
        result = await client.generate_json("system", "user", StructuredSmoke)

    assert result == parsed
    responses.parse.assert_awaited_once_with(
        model=DEFAULT_OPENAI_MODEL,
        input=[
            {"role": "system", "content": "system"},
            {"role": "user", "content": "user"},
        ],
        max_output_tokens=8192,
        text_format=StructuredSmoke,
    )


async def test_generate_json_rejects_unparsed_response() -> None:
    responses = MagicMock()
    responses.parse = AsyncMock(return_value=SimpleNamespace(output_parsed={"name": "tickets"}))
    openai_client = MagicMock()
    openai_client.responses = responses

    with patch("mcpforge.openai_client.AsyncOpenAI", return_value=openai_client):
        client = OpenAIClient(api_key="test-key")
        with pytest.raises(ValueError, match="did not match StructuredSmoke schema"):
            await client.generate_json("system", "user", StructuredSmoke)


async def test_generate_uses_responses_create_for_plain_text() -> None:
    responses = MagicMock()
    responses.create = AsyncMock(return_value=SimpleNamespace(output_text="hello"))
    openai_client = MagicMock()
    openai_client.responses = responses

    with patch("mcpforge.openai_client.AsyncOpenAI", return_value=openai_client):
        client = OpenAIClient(api_key="test-key", model="gpt-test")
        result = await client.generate("system", "user", max_tokens=64, temperature=0.1)

    assert result == "hello"
    responses.create.assert_awaited_once_with(
        model="gpt-test",
        instructions="system",
        input="user",
        max_output_tokens=64,
        temperature=0.1,
    )

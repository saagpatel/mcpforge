"""Tests for AnthropicClient.generate_stream()."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import httpx
import pytest
from pydantic import BaseModel

from mcpforge.api_client import AnthropicClient, _model_rejects_sampling


def _api_status_error(status_code: int) -> anthropic.APIStatusError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status_code, request=request)
    return anthropic.APIStatusError("provider error", response=response, body=None)


class StructuredSmoke(BaseModel):
    """Tiny response model for deterministic structured-output smoke tests."""

    name: str
    count: int


class TestGenerate:
    def test_init_requires_api_key(self, monkeypatch):
        """Constructing without an explicit or environment key fails clearly."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with (
            patch("mcpforge.api_client.anthropic.AsyncAnthropic") as mock_anthropic,
            pytest.raises(ValueError) as exc_info,
        ):
            AnthropicClient()

        assert str(exc_info.value) == (
            "Anthropic API key is required. "
            "Set the ANTHROPIC_API_KEY environment variable or pass api_key= explicitly."
        )
        mock_anthropic.assert_not_called()

    def test_repr_includes_model(self):
        """repr exposes the configured model without leaking credentials."""
        mock_anthropic = MagicMock()

        with patch("mcpforge.api_client.anthropic.AsyncAnthropic", return_value=mock_anthropic):
            client = AnthropicClient(api_key="test-key", model="claude-test-model")

        assert repr(client) == "AnthropicClient(model='claude-test-model')"

    async def test_retries_connection_errors(self):
        """generate retries transient provider connection drops."""
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        connection_error = anthropic.APIConnectionError(request=request)
        response = SimpleNamespace(content=[SimpleNamespace(text="ok")])

        mock_messages = MagicMock()
        mock_messages.create = AsyncMock(side_effect=[connection_error, response])

        mock_anthropic = MagicMock()
        mock_anthropic.messages = mock_messages

        with (
            patch("mcpforge.api_client.anthropic.AsyncAnthropic", return_value=mock_anthropic),
            patch("mcpforge.api_client.asyncio.sleep", new=AsyncMock()) as mock_sleep,
        ):
            client = AnthropicClient(api_key="test-key")
            result = await client.generate("system", "user")

        assert result == "ok"
        assert mock_messages.create.await_count == 2
        mock_sleep.assert_awaited_once()

    async def test_includes_temperature_for_sampling_models(self):
        """The default model accepts sampling params, so temperature is forwarded."""
        response = SimpleNamespace(content=[SimpleNamespace(text="ok")])
        mock_messages = MagicMock()
        mock_messages.create = AsyncMock(return_value=response)
        mock_anthropic = MagicMock()
        mock_anthropic.messages = mock_messages

        with patch("mcpforge.api_client.anthropic.AsyncAnthropic", return_value=mock_anthropic):
            client = AnthropicClient(api_key="test-key")  # default sonnet-4-6
            result = await client.generate("system", "user", temperature=0.0)

        assert result == "ok"
        _, kwargs = mock_messages.create.call_args
        assert kwargs["temperature"] == 0.0

    async def test_omits_temperature_for_sampling_rejecting_model(self):
        """Opus 4.8 rejects temperature with a 400, so the param must be omitted."""
        response = SimpleNamespace(content=[SimpleNamespace(text="ok")])
        mock_messages = MagicMock()
        mock_messages.create = AsyncMock(return_value=response)
        mock_anthropic = MagicMock()
        mock_anthropic.messages = mock_messages

        with patch("mcpforge.api_client.anthropic.AsyncAnthropic", return_value=mock_anthropic):
            client = AnthropicClient(api_key="test-key", model="claude-opus-4-8")
            result = await client.generate("system", "user", temperature=0.0)

        assert result == "ok"
        _, kwargs = mock_messages.create.call_args
        assert "temperature" not in kwargs
        assert kwargs["model"] == "claude-opus-4-8"

    async def test_skips_thinking_blocks_when_reading_text(self):
        """Adaptive-thinking responses lead with thinking blocks; pick the text block."""
        response = SimpleNamespace(
            content=[
                SimpleNamespace(thinking="internal reasoning"),
                SimpleNamespace(text="actual answer"),
            ]
        )
        mock_messages = MagicMock()
        mock_messages.create = AsyncMock(return_value=response)
        mock_anthropic = MagicMock()
        mock_anthropic.messages = mock_messages

        with patch("mcpforge.api_client.anthropic.AsyncAnthropic", return_value=mock_anthropic):
            client = AnthropicClient(api_key="test-key")
            result = await client.generate("system", "user")

        assert result == "actual answer"

    async def test_rejects_response_without_text_block(self):
        """A response with only non-text blocks surfaces the no-text error."""
        response = SimpleNamespace(content=[SimpleNamespace(thinking="still thinking")])
        mock_messages = MagicMock()
        mock_messages.create = AsyncMock(return_value=response)
        mock_anthropic = MagicMock()
        mock_anthropic.messages = mock_messages

        with patch("mcpforge.api_client.anthropic.AsyncAnthropic", return_value=mock_anthropic):
            client = AnthropicClient(api_key="test-key")
            with pytest.raises(RuntimeError) as exc_info:
                await client.generate("system", "user")

        assert str(exc_info.value) == "Anthropic response contained no text block"


class TestRetry:
    async def test_reraises_final_transient_failure_after_retries(self):
        """Transient provider failures are retried twice, then re-raised."""
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        connection_error = anthropic.APIConnectionError(request=request)
        operation = AsyncMock(side_effect=connection_error)

        with (
            patch("mcpforge.api_client.anthropic.AsyncAnthropic"),
            patch("mcpforge.api_client.random.uniform", return_value=0.0),
            patch("mcpforge.api_client.asyncio.sleep", new=AsyncMock()) as mock_sleep,
        ):
            client = AnthropicClient(api_key="test-key")
            with pytest.raises(anthropic.APIConnectionError) as exc_info:
                await client._with_retry(operation)

        assert exc_info.value is connection_error
        assert operation.await_count == 3
        assert [call.args[0] for call in mock_sleep.await_args_list] == [1.0, 2.0]

    async def test_retries_5xx_status_error_then_returns_value(self):
        """HTTP 5xx API status errors are retried before returning a later value."""
        status_error = _api_status_error(503)
        operation = AsyncMock(side_effect=[status_error, "ok"])

        with (
            patch("mcpforge.api_client.anthropic.AsyncAnthropic"),
            patch("mcpforge.api_client.random.uniform", return_value=0.0),
            patch("mcpforge.api_client.asyncio.sleep", new=AsyncMock()) as mock_sleep,
        ):
            client = AnthropicClient(api_key="test-key")
            result = await client._with_retry(operation)

        assert result == "ok"
        assert operation.await_count == 2
        mock_sleep.assert_awaited_once_with(1.0)

    async def test_does_not_retry_4xx_status_error(self):
        """HTTP 4xx API status errors are treated as caller errors."""
        status_error = _api_status_error(400)
        operation = AsyncMock(side_effect=status_error)

        with (
            patch("mcpforge.api_client.anthropic.AsyncAnthropic"),
            patch("mcpforge.api_client.asyncio.sleep", new=AsyncMock()) as mock_sleep,
        ):
            client = AnthropicClient(api_key="test-key")
            with pytest.raises(anthropic.APIStatusError) as exc_info:
                await client._with_retry(operation)

        assert exc_info.value is status_error
        operation.assert_awaited_once()
        mock_sleep.assert_not_awaited()

    async def test_retry_loop_fallthrough_raises_runtime_error(self):
        """If the retry loop cannot iterate, it raises the defensive fallthrough."""
        operation = AsyncMock(return_value="unused")

        with (
            patch("mcpforge.api_client.anthropic.AsyncAnthropic"),
            patch("mcpforge.api_client.range", return_value=(), create=True),
        ):
            client = AnthropicClient(api_key="test-key")
            with pytest.raises(RuntimeError) as exc_info:
                await client._with_retry(operation)

        assert str(exc_info.value) == "retry loop exited unexpectedly"
        operation.assert_not_awaited()


class TestModelRejectsSampling:
    @pytest.mark.parametrize(
        ("model", "expected"),
        [
            ("claude-opus-4-8", True),
            ("claude-opus-4-7", True),
            ("claude-opus-4-7-20250514", True),  # dated alias
            ("claude-opus-4-9", True),  # future minor — version floor, not enum
            ("claude-opus-4-10", True),  # double-digit minor sorts correctly
            ("claude-opus-5-0", True),  # future major
            ("claude-fable-5", True),
            ("claude-mythos-5", True),
            ("claude-sonnet-4-6", False),
            ("claude-opus-4-6", False),
            ("claude-opus-4-6-20250101", False),
            ("claude-haiku-4-5", False),
        ],
    )
    def test_predicate(self, model, expected):
        assert _model_rejects_sampling(model) is expected


class TestGenerateJson:
    async def test_uses_structured_output_and_returns_parsed_model(self):
        """generate_json drives messages.parse and returns the parsed Pydantic model."""
        parsed_response = SimpleNamespace(parsed_output=StructuredSmoke(name="tickets", count=2))
        mock_messages = MagicMock()
        mock_messages.parse = AsyncMock(return_value=parsed_response)
        mock_anthropic = MagicMock()
        mock_anthropic.messages = mock_messages

        with patch("mcpforge.api_client.anthropic.AsyncAnthropic", return_value=mock_anthropic):
            client = AnthropicClient(api_key="test-key")
            result = await client.generate_json("system", "user", StructuredSmoke)

        assert result == StructuredSmoke(name="tickets", count=2)
        mock_messages.parse.assert_awaited_once_with(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            system="system",
            messages=[{"role": "user", "content": "user"}],
            output_format=StructuredSmoke,
        )
        # Structured output never carries a sampling param, even on the default model.
        assert "temperature" not in mock_messages.parse.call_args.kwargs

    async def test_works_for_sampling_rejecting_model(self):
        """Structured output carries no temperature, so Opus 4.8 generates cleanly."""
        parsed_response = SimpleNamespace(parsed_output=StructuredSmoke(name="ok", count=1))
        mock_messages = MagicMock()
        mock_messages.parse = AsyncMock(return_value=parsed_response)
        mock_anthropic = MagicMock()
        mock_anthropic.messages = mock_messages

        with patch("mcpforge.api_client.anthropic.AsyncAnthropic", return_value=mock_anthropic):
            client = AnthropicClient(api_key="test-key", model="claude-opus-4-8")
            result = await client.generate_json("system", "user", StructuredSmoke)

        assert result == StructuredSmoke(name="ok", count=1)
        _, kwargs = mock_messages.parse.call_args
        assert "temperature" not in kwargs

    async def test_rejects_empty_structured_output(self):
        """A response that parses to nothing surfaces a clear error."""
        parsed_response = SimpleNamespace(parsed_output=None)
        mock_messages = MagicMock()
        mock_messages.parse = AsyncMock(return_value=parsed_response)
        mock_anthropic = MagicMock()
        mock_anthropic.messages = mock_messages

        with patch("mcpforge.api_client.anthropic.AsyncAnthropic", return_value=mock_anthropic):
            client = AnthropicClient(api_key="test-key")
            with pytest.raises(ValueError, match="StructuredSmoke"):
                await client.generate_json("system", "user", StructuredSmoke)


class TestGenerateStream:
    async def test_yields_string_chunks(self):
        """generate_stream yields string chunks from the stream."""
        chunks = ["Hello", ", ", "world", "!"]

        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        async def _fake_text_stream():
            for chunk in chunks:
                yield chunk

        mock_stream.text_stream = _fake_text_stream()

        mock_messages = MagicMock()
        mock_messages.stream = MagicMock(return_value=mock_stream)

        mock_anthropic = MagicMock()
        mock_anthropic.messages = mock_messages

        with patch("mcpforge.api_client.anthropic.AsyncAnthropic", return_value=mock_anthropic):
            client = AnthropicClient(api_key="test-key")
            result = []
            async for chunk in client.generate_stream("system", "user"):
                result.append(chunk)

        assert result == chunks

    async def test_chunks_concatenate_to_full_text(self):
        """Concatenated chunks equal the full expected text."""
        chunks = ["The ", "answer ", "is ", "42"]
        expected = "The answer is 42"

        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        async def _fake_text_stream():
            for chunk in chunks:
                yield chunk

        mock_stream.text_stream = _fake_text_stream()

        mock_messages = MagicMock()
        mock_messages.stream = MagicMock(return_value=mock_stream)

        mock_anthropic = MagicMock()
        mock_anthropic.messages = mock_messages

        with patch("mcpforge.api_client.anthropic.AsyncAnthropic", return_value=mock_anthropic):
            client = AnthropicClient(api_key="test-key")
            result = []
            async for chunk in client.generate_stream("system", "user"):
                result.append(chunk)

        assert "".join(result) == expected

    async def test_uses_correct_parameters(self):
        """generate_stream passes correct parameters to messages.stream."""
        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        async def _fake_text_stream():
            yield "chunk"

        mock_stream.text_stream = _fake_text_stream()

        mock_messages = MagicMock()
        mock_messages.stream = MagicMock(return_value=mock_stream)

        mock_anthropic = MagicMock()
        mock_anthropic.messages = mock_messages

        with patch("mcpforge.api_client.anthropic.AsyncAnthropic", return_value=mock_anthropic):
            client = AnthropicClient(api_key="test-key", model="claude-test-model")
            async for _ in client.generate_stream(
                "sys prompt", "user msg", max_tokens=1024, temperature=0.5
            ):
                pass

        mock_messages.stream.assert_called_once_with(
            model="claude-test-model",
            max_tokens=1024,
            temperature=0.5,
            system="sys prompt",
            messages=[{"role": "user", "content": "user msg"}],
        )

    async def test_omits_temperature_for_sampling_rejecting_model(self):
        """A model that rejects sampling must not receive temperature on the stream call."""
        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        async def _fake_text_stream():
            yield "chunk"

        mock_stream.text_stream = _fake_text_stream()

        mock_messages = MagicMock()
        mock_messages.stream = MagicMock(return_value=mock_stream)

        mock_anthropic = MagicMock()
        mock_anthropic.messages = mock_messages

        with patch("mcpforge.api_client.anthropic.AsyncAnthropic", return_value=mock_anthropic):
            client = AnthropicClient(api_key="test-key", model="claude-opus-4-8")
            async for _ in client.generate_stream("sys", "user", temperature=0.5):
                pass

        _, kwargs = mock_messages.stream.call_args
        assert "temperature" not in kwargs
        assert kwargs["model"] == "claude-opus-4-8"

    async def test_empty_stream_yields_nothing(self):
        """generate_stream with empty text_stream yields no chunks."""
        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        async def _empty_text_stream():
            return
            yield  # make it an async generator

        mock_stream.text_stream = _empty_text_stream()

        mock_messages = MagicMock()
        mock_messages.stream = MagicMock(return_value=mock_stream)

        mock_anthropic = MagicMock()
        mock_anthropic.messages = mock_messages

        with patch("mcpforge.api_client.anthropic.AsyncAnthropic", return_value=mock_anthropic):
            client = AnthropicClient(api_key="test-key")
            result = []
            async for chunk in client.generate_stream("system", "user"):
                result.append(chunk)

        assert result == []

    async def test_raises_timeout_when_chunk_stalls(self):
        """generate_stream raises TimeoutError when the next chunk exceeds chunk_timeout."""
        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        async def _stalled_text_stream():
            await asyncio.Event().wait()
            yield "never"

        mock_stream.text_stream = _stalled_text_stream()

        mock_messages = MagicMock()
        mock_messages.stream = MagicMock(return_value=mock_stream)

        mock_anthropic = MagicMock()
        mock_anthropic.messages = mock_messages

        with patch("mcpforge.api_client.anthropic.AsyncAnthropic", return_value=mock_anthropic):
            client = AnthropicClient(api_key="test-key")
            with pytest.raises(TimeoutError) as exc_info:
                async for _ in client.generate_stream("system", "user", chunk_timeout=0.001):
                    pass

        assert str(exc_info.value) == "Streaming generation stalled — no data received for 0.001s"

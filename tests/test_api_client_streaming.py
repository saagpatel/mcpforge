"""Tests for AnthropicClient.generate_stream()."""

from unittest.mock import AsyncMock, MagicMock, patch

from mcpforge.api_client import AnthropicClient


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

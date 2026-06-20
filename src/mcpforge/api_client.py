"""Anthropic API client wrapper with retry logic.

MODEL POLICY: `generate_json()` uses Anthropic structured outputs
(`messages.parse` with `output_format`), so JSON determinism no longer
depends on `temperature=0`. The newest reasoning models (Opus 4.7+,
Fable 5, Mythos 5) reject `temperature`/`top_p`/`top_k` with a 400, so
`generate()` forwards `temperature` only for models that accept it
(see `_model_rejects_sampling`). The default model is safe to upgrade to
any of those models without further client changes.
"""

import asyncio
import os
import random
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TypeVar

import anthropic
from pydantic import BaseModel

DEFAULT_MODEL = "claude-sonnet-4-6"

_T = TypeVar("_T")

# Model families that reject temperature/top_p/top_k with a 400 across every
# version (Fable and Mythos thinking is always on, with no sampling lever).
_SAMPLING_REJECTING_FAMILIES = ("fable", "mythos")
# Opus rejects sampling from this minor onward; 4.6 and earlier still accept it.
_OPUS_SAMPLING_FLOOR = (4, 7)
_OPUS_VERSION_RE = re.compile(r"opus-(\d+)-(\d+)")


def _model_rejects_sampling(model: str) -> bool:
    """Return True if the model rejects temperature/top_p/top_k (400 error).

    Expressed as a version floor rather than an enumeration so the default
    model stays safe to upgrade to future reasoning models: Opus >= 4.7 and
    the Fable/Mythos families reject sampling; Opus 4.6, Sonnet, and Haiku
    still accept it.
    """
    normalized = model.lower()
    if any(family in normalized for family in _SAMPLING_REJECTING_FAMILIES):
        return True
    match = _OPUS_VERSION_RE.search(normalized)
    if match:
        version = (int(match.group(1)), int(match.group(2)))
        return version >= _OPUS_SAMPLING_FLOOR
    return False


def _first_text_block(response: object) -> str:
    """Return the first text block's text, skipping thinking blocks.

    Adaptive-thinking responses lead with thinking blocks, so the text is
    not necessarily ``content[0]``. Thinking blocks expose ``thinking`` but
    not ``text``, so the first block with a ``text`` attribute is the answer.
    """
    for block in response.content:  # type: ignore[attr-defined]
        text = getattr(block, "text", None)
        if text is not None:
            return text
    raise RuntimeError("Anthropic response contained no text block")


class AnthropicClient:
    """Async wrapper around anthropic.AsyncAnthropic with exponential-backoff retry."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not resolved_key:
            raise ValueError(
                "Anthropic API key is required. "
                "Set the ANTHROPIC_API_KEY environment variable or pass api_key= explicitly."
            )
        self._model = model
        self._client = anthropic.AsyncAnthropic(api_key=resolved_key)

    def __repr__(self) -> str:
        return f"AnthropicClient(model={self._model!r})"

    def _sampling_params(self, temperature: float) -> dict[str, float]:
        """``{"temperature": t}`` for models that accept it, else ``{}`` (avoids a 400)."""
        if _model_rejects_sampling(self._model):
            return {}
        return {"temperature": temperature}

    async def _with_retry(self, operation: Callable[[], Awaitable[_T]]) -> _T:
        """Run an async provider call with exponential-backoff retry (3 attempts)."""
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                return await operation()
            except (anthropic.RateLimitError, anthropic.APIConnectionError) as exc:
                last_exc = exc
                if attempt == 2:
                    raise
                await asyncio.sleep((2**attempt) + random.uniform(0.0, 1.0))
            except anthropic.APIStatusError as exc:
                last_exc = exc
                if exc.status_code >= 500 and attempt < 2:
                    await asyncio.sleep((2**attempt) + random.uniform(0.0, 1.0))
                    continue
                raise
        raise RuntimeError("retry loop exited unexpectedly") from last_exc

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 8192,
        temperature: float = 0.0,
    ) -> str:
        """Send a message and return the text response.

        ``temperature`` is forwarded only for models that accept sampling
        params; models that reject it (Opus 4.7+, Fable 5, Mythos 5) omit it
        to avoid a 400. Retries up to 3 times on transient provider errors.
        """
        response = await self._with_retry(
            lambda: self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
                **self._sampling_params(temperature),
            )
        )
        return _first_text_block(response)

    async def generate_json(
        self,
        system_prompt: str,
        user_message: str,
        response_model: type[BaseModel],
        max_tokens: int = 8192,
    ) -> BaseModel:
        """Generate a structured response validated against a Pydantic model.

        Uses Anthropic structured outputs (``messages.parse`` with
        ``output_format``) so the schema is enforced provider-side and
        determinism does not depend on ``temperature`` — newer reasoning
        models reject the temperature lever.
        """
        response = await self._with_retry(
            lambda: self._client.messages.parse(
                model=self._model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
                output_format=response_model,
            )
        )
        parsed = response.parsed_output
        if parsed is None:
            raise ValueError(
                f"Anthropic returned no parseable structured output for {response_model.__name__}."
            )
        return parsed

    async def generate_stream(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 16384,
        temperature: float = 0.2,
        chunk_timeout: float = 60.0,
    ) -> AsyncIterator[str]:
        """Stream text chunks as they arrive from the API.

        Yields str chunks. No retry — streaming connections are not retryable.
        Raises TimeoutError if no chunk arrives within chunk_timeout seconds.
        ``temperature`` is forwarded only for models that accept sampling params.
        """
        async with self._client.messages.stream(
            model=self._model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            **self._sampling_params(temperature),
        ) as stream:
            aiter = stream.text_stream.__aiter__()
            while True:
                try:
                    text = await asyncio.wait_for(aiter.__anext__(), timeout=chunk_timeout)
                    yield text
                except StopAsyncIteration:
                    break
                except TimeoutError:
                    raise TimeoutError(
                        f"Streaming generation stalled — no data received for {chunk_timeout}s"
                    ) from None

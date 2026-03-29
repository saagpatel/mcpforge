"""Anthropic API client wrapper with retry logic."""

import asyncio
import json
import os
import random
import re
from collections.abc import AsyncIterator

import anthropic
from pydantic import BaseModel, ValidationError


class AnthropicClient:
    """Async wrapper around anthropic.AsyncAnthropic with exponential-backoff retry."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
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

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 8192,
        temperature: float = 0.0,
    ) -> str:
        """Send a message and return the text response.

        Retries up to 3 times with exponential backoff on 429 and 5xx errors.
        """
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                response = await self._client.messages.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                )
                return response.content[0].text  # type: ignore[union-attr]
            except anthropic.RateLimitError as exc:
                last_exc = exc
                if attempt == 2:
                    raise
                wait = (2**attempt) + random.uniform(0.0, 1.0)
                await asyncio.sleep(wait)
            except anthropic.APIStatusError as exc:
                last_exc = exc
                if exc.status_code >= 500 and attempt < 2:
                    wait = (2**attempt) + random.uniform(0.0, 1.0)
                    await asyncio.sleep(wait)
                    continue
                raise
        raise RuntimeError("generate() exited retry loop unexpectedly") from last_exc

    async def generate_json(
        self,
        system_prompt: str,
        user_message: str,
        response_model: type[BaseModel],
        max_tokens: int = 8192,
    ) -> BaseModel:
        """Generate and parse a structured JSON response into a Pydantic model instance.

        Uses temperature=0 for deterministic JSON output. Strips markdown fences
        before parsing so the LLM can optionally wrap its response in ```json blocks.
        """
        text = await self.generate(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=max_tokens,
            temperature=0.0,
        )
        try:
            data = _extract_json(text)
            return response_model.model_validate(data)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Response was not valid JSON for {response_model.__name__}.\n"
                f"Raw response (first 500 chars): {text[:500]}"
            ) from exc
        except ValidationError as exc:
            raise ValueError(
                f"Response JSON did not match {response_model.__name__} schema: {exc}"
            ) from exc


    async def generate_stream(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 16384,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]:
        """Stream text chunks as they arrive from the API.

        Yields str chunks. No retry — streaming connections are not retryable.
        Raises immediately on API errors.
        """
        async with self._client.messages.stream(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            async for text in stream.text_stream:
                yield text


def _extract_json(text: str) -> dict:
    """Extract a JSON object from text, stripping optional markdown code fences."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    return json.loads(text.strip())

"""OpenRouter provider client — run mcpforge against any model via one key.

OpenRouter exposes an OpenAI-compatible API, so this client reuses the
``openai`` SDK pointed at OpenRouter's base URL. It is the "bring any model"
escape hatch: any OpenRouter model id works, including free and low-cost ones.

Caveat (surfaced to users via ``OPENROUTER_DISCLAIMER``): generation quality
and structured-output (JSON schema) support vary by model and by the upstream
provider OpenRouter routes to. ``generate_json`` sets
``provider.require_parameters`` so OpenRouter only routes to providers that
honor the JSON schema instead of silently falling back to loose JSON.
"""

import asyncio
import os
from collections.abc import AsyncIterator

from openai import AsyncOpenAI
from pydantic import BaseModel

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# Recommended default; override with --model to use any OpenRouter model id.
DEFAULT_OPENROUTER_MODEL = "anthropic/claude-opus-4.8"

# Models known to handle strict structured outputs well at high reasoning effort.
RECOMMENDED_MODELS = ("anthropic/claude-opus-4.8", "openai/gpt-5.5")
OPENROUTER_DISCLAIMER = (
    "OpenRouter lets you run mcpforge against any model and key, including free "
    "and low-cost ones. Generation quality and structured-output (JSON schema) "
    "support vary by model and provider — for reliable results the recommended "
    "models are Anthropic Claude Opus 4.8 (xHigh effort) and/or OpenAI GPT 5.5 "
    "(High/Extra High). Pick one with --model, e.g. "
    "--model anthropic/claude-opus-4.8."
)

# Forces OpenRouter to route only to providers that honor the JSON schema,
# instead of silently downgrading to json_object mode.
_REQUIRE_SCHEMA_PROVIDER = {"provider": {"require_parameters": True}}


class OpenRouterClient:
    """OpenAI-compatible client pointed at OpenRouter's chat.completions endpoint."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_OPENROUTER_MODEL,
    ) -> None:
        resolved_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not resolved_key:
            raise ValueError(
                "OpenRouter API key is required. "
                "Set the OPENROUTER_API_KEY environment variable or pass api_key= explicitly."
            )
        self._model = model or DEFAULT_OPENROUTER_MODEL
        self._client = AsyncOpenAI(
            api_key=resolved_key,
            base_url=os.environ.get("OPENROUTER_BASE_URL", OPENROUTER_BASE_URL),
            default_headers={"X-Title": "mcpforge"},
        )

    def __repr__(self) -> str:
        return f"OpenRouterClient(model={self._model!r})"

    def _messages(self, system_prompt: str, user_message: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 8192,
        temperature: float = 0.0,
    ) -> str:
        """Generate plain text through the chat.completions endpoint."""
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=self._messages(system_prompt, user_message),
            max_tokens=max_tokens,
            temperature=temperature,
        )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("OpenRouter returned an empty response.")
        return content

    async def generate_json(
        self,
        system_prompt: str,
        user_message: str,
        response_model: type[BaseModel],
        max_tokens: int = 8192,
    ) -> BaseModel:
        """Generate a strict structured response parsed into a Pydantic model.

        Determinism comes from the JSON schema, not temperature, so no sampling
        param is sent — that keeps the path compatible with models (e.g. Opus
        4.7+) that reject temperature.
        """
        response = await self._client.chat.completions.parse(
            model=self._model,
            messages=self._messages(system_prompt, user_message),
            max_tokens=max_tokens,
            response_format=response_model,
            extra_body=_REQUIRE_SCHEMA_PROVIDER,
        )
        parsed = response.choices[0].message.parsed
        if not isinstance(parsed, response_model):
            raise ValueError(
                f"OpenRouter response did not match {response_model.__name__} schema. "
                f"The selected model ({self._model}) may not support strict structured "
                f"outputs — see the recommended models."
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
        """Stream text deltas from the chat.completions endpoint.

        Raises TimeoutError if no chunk arrives within chunk_timeout seconds.
        Usage-only tail chunks (empty ``choices``) are skipped.
        """
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=self._messages(system_prompt, user_message),
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        aiter = stream.__aiter__()
        while True:
            try:
                chunk = await asyncio.wait_for(aiter.__anext__(), timeout=chunk_timeout)
            except StopAsyncIteration:
                break
            except TimeoutError:
                raise TimeoutError(
                    f"Streaming generation stalled — no data received for {chunk_timeout}s"
                ) from None
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

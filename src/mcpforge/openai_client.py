"""OpenAI provider client for gated structured-output validation."""

import os
from collections.abc import AsyncIterator

from openai import AsyncOpenAI
from pydantic import BaseModel

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


class OpenAIClient:
    """Small OpenAI client surface used for gated provider smokes."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_OPENAI_MODEL,
    ) -> None:
        resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not resolved_key:
            raise ValueError(
                "OpenAI API key is required. "
                "Set the OPENAI_API_KEY environment variable or pass api_key= explicitly."
            )
        self._model = model or DEFAULT_OPENAI_MODEL
        self._client = AsyncOpenAI(api_key=resolved_key)

    def __repr__(self) -> str:
        return f"OpenAIClient(model={self._model!r})"

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 8192,
        temperature: float = 0.0,
    ) -> str:
        """Generate plain text through the Responses API."""
        response = await self._client.responses.create(
            model=self._model,
            instructions=system_prompt,
            input=user_message,
            max_output_tokens=max_tokens,
            temperature=temperature,
        )
        return str(response.output_text)

    async def generate_json(
        self,
        system_prompt: str,
        user_message: str,
        response_model: type[BaseModel],
        max_tokens: int = 8192,
    ) -> BaseModel:
        """Generate a strict structured response parsed into a Pydantic model."""
        response = await self._client.responses.parse(
            model=self._model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_output_tokens=max_tokens,
            text_format=response_model,
        )
        parsed = response.output_parsed
        if not isinstance(parsed, response_model):
            raise ValueError(f"OpenAI response did not match {response_model.__name__} schema")
        return parsed

    async def generate_stream(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 16384,
        temperature: float = 0.2,
        chunk_timeout: float = 60.0,
    ) -> AsyncIterator[str]:
        """Streaming is intentionally not enabled for the gated OpenAI path."""
        raise NotImplementedError(
            "OpenAI streaming is gated until hosted streaming smokes are implemented."
        )
        yield ""

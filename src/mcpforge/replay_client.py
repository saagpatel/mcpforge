"""A replay client that serves pre-recorded responses through the real pipeline.

Implements the ``LLMProviderClient`` protocol but returns hand-authored
responses instead of calling any API, so ``mcpforge demo`` can exercise the
genuine plan -> generate -> validate flow with no API key and no spend.
"""

from collections.abc import AsyncIterator

from pydantic import BaseModel

from mcpforge.models import ServerPlan


class ReplayClient:
    """Serves a recorded plan plus ordered ``generate()`` responses.

    The generate pipeline calls ``generate_json`` once (the plan) and
    ``generate`` in a fixed order (server code, then tests), so responses are
    replayed positionally. Exhausting the recording raises rather than
    fabricating output, surfacing a broken cassette loudly.
    """

    def __init__(self, plan: ServerPlan, generate_responses: list[str]) -> None:
        self._plan = plan
        self._generate_responses = list(generate_responses)
        self._generate_index = 0

    def __repr__(self) -> str:
        return f"ReplayClient(plan={self._plan.slug!r}, responses={len(self._generate_responses)})"

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 8192,
        temperature: float = 0.0,
    ) -> str:
        """Return the next recorded text response in order."""
        if self._generate_index >= len(self._generate_responses):
            raise RuntimeError(
                "ReplayClient ran out of recorded generate() responses — the cassette "
                "does not cover this generation path."
            )
        response = self._generate_responses[self._generate_index]
        self._generate_index += 1
        return response

    async def generate_json(
        self,
        system_prompt: str,
        user_message: str,
        response_model: type[BaseModel],
        max_tokens: int = 8192,
    ) -> BaseModel:
        """Return the recorded plan (the only structured call in the pipeline)."""
        if not isinstance(self._plan, response_model):
            raise TypeError(
                f"ReplayClient recorded a {type(self._plan).__name__}, "
                f"but the pipeline asked for {response_model.__name__}."
            )
        return self._plan

    async def generate_stream(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 16384,
        temperature: float = 0.2,
        chunk_timeout: float = 60.0,
    ) -> AsyncIterator[str]:
        """Streaming is not part of the recorded demo path."""
        raise NotImplementedError("ReplayClient does not support streaming generation.")
        yield ""  # pragma: no cover - makes this an async generator

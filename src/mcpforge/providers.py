"""Provider selection and capability metadata for LLM generation backends."""

from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass
from typing import Protocol

from pydantic import BaseModel

from mcpforge.api_client import DEFAULT_MODEL, AnthropicClient
from mcpforge.openai_client import DEFAULT_OPENAI_MODEL, OpenAIClient

DEFAULT_PROVIDER = "anthropic"


class LLMProviderClient(Protocol):
    """Small client surface mcpforge needs from any generation provider."""

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 8192,
        temperature: float = 0.0,
    ) -> str: ...

    async def generate_json(
        self,
        system_prompt: str,
        user_message: str,
        response_model: type[BaseModel],
        max_tokens: int = 8192,
    ) -> BaseModel: ...

    def generate_stream(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 16384,
        temperature: float = 0.2,
        chunk_timeout: float = 60.0,
    ) -> AsyncIterator[str]: ...


@dataclass(frozen=True)
class ProviderCapabilities:
    """Provider feature flags used by doctor and future provider gates."""

    name: str
    default_model: str
    structured_json: bool
    streaming: bool
    temperature_zero: bool
    hosted_smoke: bool
    status: str

    def to_dict(self) -> dict[str, str | bool]:
        return asdict(self)


_CAPABILITIES: dict[str, ProviderCapabilities] = {
    "anthropic": ProviderCapabilities(
        name="anthropic",
        default_model=DEFAULT_MODEL,
        structured_json=True,
        streaming=True,
        temperature_zero=True,
        hosted_smoke=True,
        status="stable",
    ),
    "openai": ProviderCapabilities(
        name="openai",
        default_model=DEFAULT_OPENAI_MODEL,
        structured_json=True,
        streaming=False,
        temperature_zero=False,
        hosted_smoke=True,
        status="gated",
    ),
}


def provider_capabilities(provider: str = DEFAULT_PROVIDER) -> ProviderCapabilities:
    """Return known capability metadata for a provider."""
    normalized = provider.lower()
    if normalized not in _CAPABILITIES:
        raise ValueError(f"Unsupported provider: {provider}")
    return _CAPABILITIES[normalized]


def list_provider_capabilities() -> list[dict[str, str | bool]]:
    """Return capabilities for all known providers."""
    return [cap.to_dict() for cap in _CAPABILITIES.values()]


def create_provider_client(
    provider: str = DEFAULT_PROVIDER,
    *,
    model: str = DEFAULT_MODEL,
) -> LLMProviderClient:
    """Create the configured generation client.

    OpenAI has a strict structured-output client, but full generation remains gated
    until hosted planning and generation smokes prove the whole path.
    """
    normalized = provider.lower()
    if normalized == "anthropic":
        return AnthropicClient(model=model)
    if normalized == "openai":
        import os

        if os.environ.get("MCPFORGE_ENABLE_OPENAI_PROVIDER") == "1":
            return OpenAIClient(model=model or DEFAULT_OPENAI_MODEL)
        raise ValueError(
            "OpenAI provider support is gated until hosted planning and generation "
            "smokes prove the full mcpforge path. Set MCPFORGE_ENABLE_OPENAI_PROVIDER=1 "
            "only for opt-in smoke testing."
        )
    raise ValueError(f"Unsupported provider: {provider}")

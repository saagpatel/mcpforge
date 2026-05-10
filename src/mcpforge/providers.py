"""Provider selection and capability metadata for LLM generation backends."""

from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass
from typing import Protocol

from pydantic import BaseModel

from mcpforge.api_client import DEFAULT_MODEL, AnthropicClient

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
        default_model="",
        structured_json=False,
        streaming=False,
        temperature_zero=False,
        hosted_smoke=False,
        status="planned",
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

    OpenAI is intentionally listed but not implemented until strict structured-output
    smokes are added. This preserves the existing Anthropic default behavior.
    """
    normalized = provider.lower()
    if normalized == "anthropic":
        return AnthropicClient(model=model)
    if normalized == "openai":
        raise ValueError(
            "OpenAI provider support is planned but gated until deterministic "
            "structured-output and hosted generation smokes are implemented."
        )
    raise ValueError(f"Unsupported provider: {provider}")

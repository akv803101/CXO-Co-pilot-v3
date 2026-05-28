"""LLM provider registry + factory.

Reads registry/models.yaml to discover providers and models. Selection is a
"provider:model" string (e.g. "anthropic:claude-opus-4-7", "groq:llama-3.3-70b-versatile").
API keys are resolved from secrets.toml via config at call time.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

import config

from .anthropic_provider import AnthropicProvider
from .base import ChatResult, LLMProvider, ToolCall  # re-export
from .openai_provider import OpenAICompatibleProvider

_REGISTRY_PATH = Path(__file__).parent.parent / "registry" / "models.yaml"

_ADAPTERS = {
    "anthropic": AnthropicProvider,
    "openai_compatible": OpenAICompatibleProvider,
}


@lru_cache(maxsize=1)
def _registry() -> dict[str, Any]:
    with _REGISTRY_PATH.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def default_option() -> str:
    reg = _registry()
    return reg.get("default") or list_options()[0]


def list_options() -> list[str]:
    """All selectable "provider:model" strings, in registry order."""
    out: list[str] = []
    for pname, pconf in _registry().get("providers", {}).items():
        for model in pconf.get("models", []):
            out.append(f"{pname}:{model}")
    return out


def provider_has_key(option: str) -> bool:
    pname = option.split(":", 1)[0]
    pconf = _registry().get("providers", {}).get(pname, {})
    return bool(config.get(pconf.get("api_key_env", "")))


def get_provider(option: str | None = None) -> LLMProvider:
    """Build an LLMProvider for a "provider:model" selection."""
    option = option or default_option()
    pname, _, model = option.partition(":")
    pconf = _registry().get("providers", {}).get(pname)
    if pconf is None:
        raise ValueError(f"Unknown provider '{pname}'. Check registry/models.yaml.")
    adapter_cls = _ADAPTERS.get(pconf["adapter"])
    if adapter_cls is None:
        raise ValueError(f"Unknown adapter '{pconf['adapter']}' for provider '{pname}'.")
    return adapter_cls(
        model=model or (pconf.get("models") or [""])[0],
        api_key=config.get(pconf.get("api_key_env")),
        base_url=pconf.get("base_url"),
    )


__all__ = [
    "ChatResult",
    "LLMProvider",
    "ToolCall",
    "default_option",
    "list_options",
    "provider_has_key",
    "get_provider",
]

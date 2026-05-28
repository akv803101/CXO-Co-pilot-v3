"""Provider-agnostic LLM interface.

Every adapter (Anthropic, OpenAI-compatible, …) implements `chat()` with the same
contract, returning a normalized ChatResult. This is what lets the orchestrator
route the exact same prompt + tool schema to any model.

Tool schema (provider-neutral), passed to chat(tools=...):
    {"name": str, "description": str, "input_schema": {<JSON Schema>}}
Adapters convert this to each provider's native tool format.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatResult:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: Any = None


class LLMProvider(ABC):
    """One model behind one provider. Stateless per call."""

    def __init__(self, model: str, api_key: str | None, base_url: str | None = None):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    def chat(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 2048,
    ) -> ChatResult:
        """Send one turn. messages = [{"role","content"}, …]; tools = neutral schema."""
        raise NotImplementedError

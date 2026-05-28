"""Anthropic adapter — native Claude tool-calling."""

from __future__ import annotations

from typing import Any

from .base import ChatResult, LLMProvider, ToolCall


def _to_anthropic_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": t["name"],
            "description": t.get("description", ""),
            "input_schema": t.get("input_schema", {"type": "object", "properties": {}}),
        }
        for t in tools
    ]


class AnthropicProvider(LLMProvider):
    def _client(self):
        from anthropic import Anthropic

        return Anthropic(api_key=self.api_key)

    def chat(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 2048,
    ) -> ChatResult:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = _to_anthropic_tools(tools)
        resp = self._client().messages.create(**kwargs)
        text = "".join(
            b.text for b in resp.content if getattr(b, "type", None) == "text"
        )
        calls = [
            ToolCall(id=b.id, name=b.name, arguments=b.input)
            for b in resp.content
            if getattr(b, "type", None) == "tool_use"
        ]
        return ChatResult(text=text, tool_calls=calls, raw=resp)

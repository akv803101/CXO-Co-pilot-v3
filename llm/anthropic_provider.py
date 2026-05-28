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


def _to_anthropic_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert neutral messages (incl. tool_calls / tool results) to Anthropic shape."""
    out: list[dict[str, Any]] = []
    for m in messages:
        role = m["role"]
        if role == "user":
            out.append({"role": "user", "content": m["content"]})
        elif role == "assistant":
            blocks: list[dict[str, Any]] = []
            if m.get("content"):
                blocks.append({"type": "text", "text": m["content"]})
            for tc in m.get("tool_calls", []):
                blocks.append(
                    {"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments}
                )
            out.append({"role": "assistant", "content": blocks or m.get("content", "")})
        elif role == "tool":
            out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m["tool_call_id"],
                            "content": m["content"],
                        }
                    ],
                }
            )
    return out


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
            "messages": _to_anthropic_messages(messages),
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

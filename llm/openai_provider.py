"""OpenAI-compatible adapter.

Covers OpenAI, Groq, Together, Fireworks, OpenRouter, and local servers (vLLM/
Ollama) — anything exposing the OpenAI chat-completions API. The only difference
between them is base_url + api_key, supplied from registry/models.yaml.
"""

from __future__ import annotations

import json
from typing import Any

from .base import ChatResult, LLMProvider, ToolCall


def _to_openai_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            },
        }
        for t in tools
    ]


def _to_openai_messages(
    system: str, messages: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Convert neutral messages (incl. tool_calls / tool results) to OpenAI shape."""
    out: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for m in messages:
        role = m["role"]
        if role == "user":
            out.append({"role": "user", "content": m["content"]})
        elif role == "assistant":
            msg: dict[str, Any] = {"role": "assistant", "content": m.get("content") or None}
            if m.get("tool_calls"):
                msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in m["tool_calls"]
                ]
            out.append(msg)
        elif role == "tool":
            out.append(
                {"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]}
            )
    return out


class OpenAICompatibleProvider(LLMProvider):
    def _client(self):
        from openai import OpenAI

        return OpenAI(api_key=self.api_key, base_url=self.base_url)

    def chat(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 2048,
    ) -> ChatResult:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": _to_openai_messages(system, messages),
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = _to_openai_tools(tools)
        resp = self._client().chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        calls = []
        for tc in getattr(msg, "tool_calls", None) or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))
        return ChatResult(text=msg.content or "", tool_calls=calls, raw=resp)

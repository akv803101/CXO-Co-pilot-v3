"""Provider-agnostic MCP host.

Spawns each active source's MCP server (stdio, via `connectors/mcp_config`),
speaks JSON-RPC 2.0 over newline-delimited stdio, discovers each server's tools,
and exposes them as a single neutral tool list that any LLM adapter can use.

No asyncio — a plain synchronous client, which is the simplest thing that works
reliably inside Streamlit. One McpHost per ask(); close() tears down subprocesses.
"""

from __future__ import annotations

import json
import re
import subprocess
import threading
from typing import Any

from connectors import mcp_config

_PROTOCOL_VERSION = "2024-11-05"
_NAME_RE = re.compile(r"[^a-zA-Z0-9_-]")


def _safe_tool_name(source_id: str, tool: str) -> str:
    name = _NAME_RE.sub("_", f"{source_id}__{tool}")
    return name[:64]


class _Server:
    """One MCP server subprocess + JSON-RPC framing."""

    def __init__(self, source_id: str, cfg: dict[str, Any], timeout: float = 30.0):
        self.source_id = source_id
        self.timeout = timeout
        import os

        env = {**os.environ, **(cfg.get("env") or {})}
        self.proc = subprocess.Popen(
            [cfg["command"], *cfg["args"]],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
            text=True,
            bufsize=1,
        )
        self._id = 0
        self._lock = threading.Lock()

    # ----- framing
    def _send(self, obj: dict[str, Any]) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def _read_until(self, want_id: int) -> dict[str, Any]:
        """Read newline-delimited messages until the response with want_id."""
        assert self.proc.stdout is not None
        result: dict[str, Any] = {}

        def reader() -> None:
            nonlocal result
            for line in self.proc.stdout:  # type: ignore[union-attr]
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue  # ignore non-JSON noise
                if msg.get("id") == want_id:
                    result = msg
                    return

        t = threading.Thread(target=reader, daemon=True)
        t.start()
        t.join(self.timeout)
        if not result:
            raise TimeoutError(f"MCP server '{self.source_id}' did not respond in time.")
        if "error" in result:
            raise RuntimeError(f"MCP error from '{self.source_id}': {result['error']}")
        return result.get("result", {})

    def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            self._id += 1
            rid = self._id
            self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}})
            return self._read_until(rid)

    def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        with self._lock:
            self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    # ----- lifecycle
    def initialize(self) -> None:
        self._request(
            "initialize",
            {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "cxo-copilot", "version": "1.0"},
            },
        )
        self._notify("notifications/initialized")

    def list_tools(self) -> list[dict[str, Any]]:
        return self._request("tools/list").get("tools", [])

    def call_tool(self, tool: str, arguments: dict[str, Any]) -> str:
        res = self._request("tools/call", {"name": tool, "arguments": arguments})
        parts = [
            c.get("text", "")
            for c in res.get("content", [])
            if c.get("type") == "text"
        ]
        return "\n".join(parts) if parts else json.dumps(res)

    def close(self) -> None:
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


class McpHost:
    """Aggregate of all active sources' MCP servers."""

    def __init__(self, sources: list[dict[str, Any]], timeout: float = 30.0):
        self._servers: list[_Server] = []
        # neutral_tool_name -> (server, original_tool_name)
        self._registry: dict[str, tuple[_Server, str]] = {}
        self._schema: list[dict[str, Any]] = []
        for cfg in mcp_config.servers_for(sources):
            server = _Server(cfg["id"], cfg, timeout=timeout)
            server.initialize()
            self._servers.append(server)
            for tool in server.list_tools():
                neutral = _safe_tool_name(cfg["id"], tool["name"])
                self._registry[neutral] = (server, tool["name"])
                self._schema.append(
                    {
                        "name": neutral,
                        "description": f"[source: {cfg['id']}] {tool.get('description', '')}",
                        "input_schema": tool.get("inputSchema")
                        or {"type": "object", "properties": {}},
                    }
                )

    def tools(self) -> list[dict[str, Any]]:
        return self._schema

    def has_tools(self) -> bool:
        return bool(self._schema)

    def call(self, neutral_name: str, arguments: dict[str, Any]) -> str:
        entry = self._registry.get(neutral_name)
        if entry is None:
            return f"Error: unknown tool '{neutral_name}'."
        server, tool = entry
        try:
            return server.call_tool(tool, arguments)
        except Exception as exc:
            return f"Error calling {neutral_name}: {exc}"

    def close(self) -> None:
        for server in self._servers:
            server.close()

    def __enter__(self) -> "McpHost":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

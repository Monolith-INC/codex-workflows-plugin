from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Any

from .contracts import IntegrationError


class StdioMcpClient:
    """Small dependency-free MCP client used by the integration gateway.

    The client intentionally starts one configured provider process per call. This
    keeps provider authentication and lifecycle outside the orchestrator and
    avoids leaking provider sessions into host hook processes.
    """

    def __init__(self, command: str, args: list[str], *, timeout: float = 30.0):
        self.command = command
        self.args = list(args)
        self.timeout = timeout

    def call(self, tool: str, arguments: dict[str, Any]) -> Any:
        try:
            process = subprocess.Popen(
                [self.command, *self.args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=os.environ.copy(),
            )
        except OSError as exc:
            raise IntegrationError("provider_unavailable", f"Could not start provider tool: {exc}") from exc

        try:
            self._send(process, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
            self._read_response(process, 1)
            self._send(process, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
            self._send(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": tool, "arguments": arguments},
                },
            )
            response = self._read_response(process, 2)
        finally:
            try:
                process.kill()
            except OSError:
                pass
        if "error" in response:
            error = response["error"]
            raise IntegrationError("provider_error", str(error))
        result = response.get("result") or {}
        if result.get("isError"):
            raise IntegrationError("provider_error", _content_text(result.get("content")))
        return _decode_content(result.get("content"), result)

    def _send(self, process: subprocess.Popen[str], payload: dict[str, Any]) -> None:
        if process.stdin is None:
            raise IntegrationError("provider_unavailable", "Provider stdin is unavailable.")
        process.stdin.write(json.dumps(payload) + "\n")
        process.stdin.flush()

    def _read_response(self, process: subprocess.Popen[str], expected_id: int) -> dict[str, Any]:
        if process.stdout is None:
            raise IntegrationError("provider_unavailable", "Provider stdout is unavailable.")
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            line = process.stdout.readline()
            if not line:
                break
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("id") == expected_id:
                return payload
        raise IntegrationError("provider_timeout", "Provider tool did not return a response in time.", retryable=True)


def client_from_connection(connection: dict[str, Any]) -> StdioMcpClient:
    command = connection.get("command")
    args = connection.get("args", [])
    if not isinstance(command, str) or not command or not isinstance(args, list):
        raise IntegrationError("invalid_config", "Provider connection requires command and args.")
    return StdioMcpClient(command, [str(item) for item in args], timeout=float(connection.get("timeout", 30)))


def _decode_content(content: Any, fallback: Any) -> Any:
    text = _content_text(content)
    if text:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return fallback


def _content_text(content: Any) -> str:
    if not isinstance(content, list):
        return ""
    return "\n".join(str(item.get("text", "")) for item in content if isinstance(item, dict) and item.get("type") == "text")

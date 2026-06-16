# ============================================================
# SECTION: mcp-client-adapter
# PURPOSE: MCP client that spawns the server as a subprocess and routes tool calls
# DOC: docs/sections/mcp-server-architecture.md
# ============================================================

"""
MCP Client Adapter for Deklarant Pro GUI.

Starts the local development MCP server as a subprocess and communicates via
stdio JSON-RPC. Production deployment can move the same server module to Ubuntu.
"""

import json
import logging
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger("mcp_client")

STARTUP_TIMEOUT = 10
TOOL_TIMEOUT = 30
MCP_SERVER_MODULE = "mcp_server.server"

_request_counter = 0
_request_lock = threading.Lock()


class McpClientAdapter(QObject):
    """
    MCP Client Adapter — manages the MCP server subprocess.

    Signals:
        server_ready: Emitted when the server has initialized successfully.
        server_error: Emitted when the server encounters an error.
        server_stopped: Emitted when the server subprocess exits.
    """

    server_ready = Signal()
    server_error = Signal(str)
    server_stopped = Signal(int)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._process: Optional[subprocess.Popen] = None
        self._running = False
        self._ready = False
        self._pending: dict[int, threading.Event] = {}
        self._responses: dict[int, dict] = {}
        self._reader_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._available_tools: list[str] = []

    def start(self) -> bool:
        """Start the MCP server subprocess. Returns True on success."""
        if self._running:
            logger.warning("MCP client already running")
            return True

        project_root = Path(__file__).resolve().parent.parent
        venv_python = project_root / ".venv" / "bin" / "python3"
        python_exe = str(venv_python) if venv_python.exists() else sys.executable

        try:
            self._process = subprocess.Popen(
                [python_exe, "-m", MCP_SERVER_MODULE],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=str(project_root),
            )
        except Exception as e:
            logger.warning("Failed to start MCP server: %s", e)
            self.server_error.emit("Ne mogu pokrenuti MCP server")
            return False

        self._running = True
        self._reader_thread = threading.Thread(
            target=self._read_responses,
            daemon=True,
            name="mcp-reader",
        )
        self._reader_thread.start()

        response = self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "deklarant-pro-gui", "version": "1.0.0"},
        }, timeout=STARTUP_TIMEOUT)

        if response is None or "error" in response:
            logger.warning("MCP server did not initialize")
            self.stop()
            return False

        self._send_notification("notifications/initialized", {})

        response = self._send_request("tools/list", {}, timeout=5)
        tools = (response or {}).get("result", {}).get("tools", [])
        self._available_tools = [t["name"] for t in tools]
        logger.info("MCP server tools: %s", self._available_tools)

        self._ready = True
        self.server_ready.emit()
        return True

    def stop(self):
        """Stop the MCP server subprocess."""
        self._running = False
        self._ready = False

        with self._lock:
            for event in self._pending.values():
                event.set()
            self._pending.clear()

        if self._process:
            try:
                if self._process.stdin:
                    self._process.stdin.close()
                self._process.terminate()
                try:
                    self._process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self._process.kill()
            except Exception:
                logger.debug("MCP process cleanup failed", exc_info=True)

            exit_code = self._process.poll()
            self._process = None
            logger.info("MCP server stopped (exit: %s)", exit_code)
            self.server_stopped.emit(exit_code or 0)

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def available_tools(self) -> list[str]:
        return list(self._available_tools)

    def call_tool(self, name: str, **kwargs) -> dict[str, Any]:
        """
        Call an MCP tool synchronously.

        Returns parsed JSON result, or {"error": "...", "fallback": True} on failure.
        """
        if not self._ready:
            return {"error": "MCP server not ready", "fallback": True}

        try:
            response = self._send_request("tools/call", {
                "name": name,
                "arguments": kwargs,
            }, timeout=TOOL_TIMEOUT)

            if response is None:
                return {"error": "MCP server timeout", "fallback": True}

            if "error" in response:
                return {"error": "MCP tool call failed", "fallback": True}

            content = response.get("result", {}).get("content", [])
            if content:
                text = content[0].get("text", "{}")
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"raw": text}

            return {}
        except Exception as e:
            logger.warning("Tool call '%s' failed: %s", name, e)
            return {"error": "MCP tool call failed", "fallback": True}

    def has_tool(self, name: str) -> bool:
        """Check if a tool is available on the server."""
        return name in self._available_tools

    def _send_request(
        self,
        method: str,
        params: dict,
        timeout: float = 10,
    ) -> Optional[dict]:
        global _request_counter

        with _request_lock:
            _request_counter += 1
            msg_id = _request_counter

        event = threading.Event()
        with self._lock:
            self._pending[msg_id] = event

        msg = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": method,
            "params": params,
        }
        self._write_line(json.dumps(msg, ensure_ascii=False))

        if event.wait(timeout=timeout):
            with self._lock:
                return self._responses.pop(msg_id, None)

        with self._lock:
            self._pending.pop(msg_id, None)
        return None

    def _send_notification(self, method: str, params: dict):
        msg = {"jsonrpc": "2.0", "method": method, "params": params}
        self._write_line(json.dumps(msg, ensure_ascii=False))

    def _write_line(self, line: str):
        if self._process and self._process.stdin:
            try:
                self._process.stdin.write(line + "\n")
                self._process.stdin.flush()
            except (BrokenPipeError, OSError) as e:
                logger.warning("Write to MCP server failed: %s", e)
                self._running = False

    def _read_responses(self):
        while self._running and self._process and self._process.stdout:
            try:
                line = self._process.stdout.readline()
                if not line:
                    break

                line = line.strip()
                if not line:
                    continue

                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    logger.debug("Non-JSON line from MCP: %s", line[:100])
                    continue

                msg_id = msg.get("id")
                if msg_id is not None:
                    with self._lock:
                        self._responses[msg_id] = msg
                        event = self._pending.pop(msg_id, None)
                    if event:
                        event.set()
            except (BrokenPipeError, OSError):
                break
            except Exception:
                logger.exception("MCP reader error")

        logger.info("MCP reader thread stopped")
        if self._running:
            self._running = False
            self._ready = False
            self.server_error.emit("MCP server connection lost")

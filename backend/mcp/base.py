import json
import subprocess
import time
from typing import Any, Dict, Optional, Sequence

from backend.app.core.logger import logger


class McpError(Exception):
    pass


class McpStdioClient:
    def __init__(self, command: str, args: Sequence[str]) -> None:
        self._command = command
        self._args = list(args)
        self._proc = subprocess.Popen(
            [self._command] + self._args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        if not self._proc.stdin or not self._proc.stdout:
            raise McpError("启动 MCP 进程失败")
        logger.info(f"[MCP] MCP 启动成功: {self._command} {self._args[0]}")
        self._stdin = self._proc.stdin
        self._stdout = self._proc.stdout
        self._stderr = self._proc.stderr
        self._next_id = 0

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def close(self) -> None:
        try:
            if self._stdin and not self._stdin.closed:
                self._stdin.close()
        finally:
            if self._proc and self._proc.poll() is None:
                try:
                    self._proc.terminate()
                except Exception:
                    pass

    def _send_request(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: float = 60.0) -> Dict[str, Any]:
        self._next_id += 1
        req_id = str(self._next_id)
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {},
        }
        line = json.dumps(payload, ensure_ascii=False)
        self._stdin.write(line + "\n")
        self._stdin.flush()
        deadline = time.time() + timeout
        while True:
            if time.time() > deadline:
                raise McpError(f"timeout waiting for response to method {method!r} (id={req_id})")
            raw = self._stdout.readline()
            if raw == "":
                code = self._proc.poll()
                stderr_output = ""
                if self._stderr is not None:
                    try:
                        stderr_output = self._stderr.read() or ""
                    except Exception:
                        stderr_output = ""
                base_msg = f"MCP server exited unexpectedly with code {code}"
                if stderr_output:
                    tail = stderr_output[-2000:]
                    base_msg += "\n---- MCP stderr (tail) ----\n" + tail + "\n---- end stderr ----"
                raise McpError(base_msg)
            raw = raw.strip()
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(msg, dict):
                continue
            if str(msg.get("id")) != req_id:
                continue
            if "error" in msg:
                raise McpError(f"MCP error calling {method!r}: {msg['error']}")
            return msg.get("result", {})

    def initialize(self) -> Dict[str, Any]:
        params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "graph-knowledge-backend",
                "version": "0.1.0",
            },
        }
        return self._send_request("initialize", params=params, timeout=30.0)

    def list_tools(self) -> Dict[str, Any]:
        return self._send_request("tools/list", params={}, timeout=30.0)

    def call_tool(self, name: str, arguments: Dict[str, Any], timeout: float = 120.0) -> Dict[str, Any]:
        params = {"name": name, "arguments": arguments}
        return self._send_request("tools/call", params=params, timeout=timeout)

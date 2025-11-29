from typing import Any, Dict, Optional
import json
import urllib.request
import urllib.error

from backend.mcp.base import McpStdioClient, McpError
from backend.app.llm.config import CodeWorkspaceConfig


class AceCodeEngineMcp:
    def __init__(self) -> None:
        """AceCodeEngine 的 MCP 封装。

        所有配置集中在此处，业务侧无需关心：
        - BASE_URL / TOKEN 用于 stdio 启动 acemcp
        - WEB_PORT 控制 acemcp 的 --web-port（默认 8888）
        - HTTP_BASE_URL 为 HTTP 访问地址（默认 http://127.0.0.1:<port>）
        - USE_HTTP 控制是否优先走 HTTP（默认开启）
        """

        # === 统一配置区域（如需修改，只需改这里） ===
        # acemcp 连接的后端索引服务地址
        self._base_url = "https://d7.api.augmentcode.com/"
        # acemcp 调用该服务使用的 Token
        self._token = "3e1e9d694889d92432990466938dfd6ba7f04a6a0280a280acd6e7d5a4a2a546"
        # acemcp Web 管理端口，对应 --web-port
        self._web_port = 8888
        # 是否优先走 HTTP 接口
        self._use_http = True
        # acemcp Web 管理地址
        self._http_base_url = f"http://127.0.0.1:{self._web_port}"
        # 默认代码项目根目录（AI 调用时无需传入）
        self._default_project_root = CodeWorkspaceConfig.get_project_root()

        # stdio MCP 客户端，仅在 HTTP 不可用或显式关闭时使用
        self._client: Optional[McpStdioClient] = None

    # -------------------- stdio MCP 支持（可选回退） --------------------

    def _build_args(self) -> list[str]:
        args: list[str] = ["acemcp"]
        if self._web_port is not None:
            args += ["--web-port", str(self._web_port)]
        if self._base_url:
            args += ["--base-url", self._base_url]
        if self._token:
            args += ["--token", self._token]
        return args

    def _ensure_client(self) -> McpStdioClient:
        if self._client is None or not self._client.is_running():
            if self._client is not None:
                self._client.close()
            self._client = McpStdioClient(command="uvx", args=self._build_args())
            self._client.initialize()
        return self._client

    def ensure_running(self) -> None:
        self._ensure_client()

    # -------------------- HTTP 工具调用 --------------------

    def _http_search_context(self, project_root_path: str, query: str, timeout: float) -> Dict[str, Any]:
        url = self._http_base_url.rstrip("/") + "/api/tools/execute"
        payload = {
            "tool_name": "search_context",
            "arguments": {
                "project_root_path": project_root_path,
                "query": query,
            },
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_bytes = resp.read()
                text = resp_bytes.decode("utf-8")
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"raw": text}
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="ignore")
            except Exception:
                pass
            raise McpError(f"HTTP error {e.code} calling acemcp: {e.reason}, body={body}")
        except urllib.error.URLError as e:
            raise McpError(f"Failed to call acemcp HTTP endpoint {url}: {e.reason}")

    # -------------------- 对外能力：search_context --------------------

    def search_context(self, query: str, project_root_path: Optional[str] = None, timeout: float = 300.0) -> Dict[str, Any]:
        """检索代码上下文。
        
        Args:
            query: 自然语言查询
            project_root_path: 项目根目录，为空时使用内部默认配置
            timeout: 超时时间
        """
        root = project_root_path or self._default_project_root
        if not root:
            raise McpError("未配置项目根目录，请在 AceCodeEngineMcp 中设置 _default_project_root")
        normalized_root = root.replace("\\", "/")

        # 优先尝试通过 HTTP 接口调用
        if self._use_http:
            try:
                return self._http_search_context(normalized_root, query, timeout)
            except McpError:
                # HTTP 不可用时自动回退到 stdio MCP
                pass

        # 回退：通过 stdio MCP 调用，并保持此前自动启动与重试逻辑
        client = self._ensure_client()
        arguments: Dict[str, Any] = {
            "project_root_path": normalized_root,
            "query": query,
        }
        try:
            return client.call_tool("search_context", arguments=arguments, timeout=timeout)
        except McpError as e:
            message = str(e)
            if "MCP server exited unexpectedly" in message:
                self._client = None
                client = self._ensure_client()
                return client.call_tool("search_context", arguments=arguments, timeout=timeout)
            raise


_GLOBAL_CLIENT: Optional[AceCodeEngineMcp] = None


def get_ace_mcp_client() -> AceCodeEngineMcp:
    global _GLOBAL_CLIENT
    if _GLOBAL_CLIENT is None:
        _GLOBAL_CLIENT = AceCodeEngineMcp()
    return _GLOBAL_CLIENT


def warmup_ace_mcp() -> None:
    try:
        get_ace_mcp_client().ensure_running()
    except Exception:
        pass

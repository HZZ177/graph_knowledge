"""代码检索类工具

提供代码库操作能力：
- search_code_context: 语义级代码搜索（MCP）
- list_directory: 列出目录结构
- read_file: 读取文件内容
- read_file_range: 读取文件指定行范围
- grep_code: 精确文本/正则搜索（ripgrep）
"""

import json
import os
from datetime import datetime
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.app.llm.config import CodeWorkspaceConfig
from backend.app.core.logger import logger
from backend.mcp.ace_code_engine import get_ace_mcp_client


# ============================================================
# search_code_context
# ============================================================

class SearchCodeContextInput(BaseModel):
    query: str = Field(..., description="用于代码上下文检索的自然语言查询，如'开卡接口的校验逻辑'、'支付回调处理流程'")
    workspace: str = Field(..., description="目标代码库名称，用于指定搜索哪个代码库")


@tool(args_schema=SearchCodeContextInput)
def search_code_context(query: str, workspace: Optional[str] = None) -> str:
    """在指定代码仓库中检索与查询相关的代码上下文，用于深入了解接口、服务或业务流程的实现细节。"""
    try:
        project_root = CodeWorkspaceConfig.get_workspace_root(workspace)
        client = get_ace_mcp_client()
        result = client.search_context(query, project_root_path=project_root)
        if isinstance(result, dict):
            def _normalize_item(item: dict) -> Optional[dict]:
                if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                    return None
                raw = item["text"]
                new_type = item.get("type", "text")
                new_text = raw
                # 如果 text 本身是 JSON（如 {"type": "text", "text": "..."}），先解析一层
                try:
                    inner = json.loads(raw)
                    if isinstance(inner, dict) and isinstance(inner.get("text"), str):
                        new_text = inner["text"]
                        new_type = inner.get("type", new_type)
                except Exception:
                    # 否则尝试按 unicode_escape 处理 \uXXXX
                    try:
                        if "\\u" in raw or "\\n" in raw or "\\t" in raw:
                            new_text = bytes(raw, "utf-8").decode("unicode_escape")
                    except Exception:
                        new_text = raw
                return {"type": new_type, "text": new_text}

            # 优先处理标准 MCP 结构: {"content": [{"type": "text", "text": "..."}, ...]}
            contents = result.get("content")
            if isinstance(contents, list) and contents:
                normalized = []
                for item in contents:
                    norm = _normalize_item(item)
                    if norm is not None:
                        normalized.append(norm)
                if normalized:
                    return json.dumps({"content": normalized}, ensure_ascii=False)

            # 兼容直接带 text 字段的情况
            if isinstance(result.get("text"), str):
                norm = _normalize_item({"type": result.get("type", "text"), "text": result["text"]})
                if norm is not None:
                    return json.dumps(norm, ensure_ascii=False)

        # 兜底：直接返回 JSON 字符串（包含 ensure_ascii=False，以便中文正常显示）
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[search_code_context] 查询失败: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============================================================
# list_directory
# ============================================================

class ListDirectoryInput(BaseModel):
    path: Optional[str] = Field(
        default=None,
        description="相对项目根目录的目录路径，如 'backend/app'；为空表示项目根目录",
    )
    workspace: Optional[str] = Field(
        default=None,
        description="目标代码库标识符。不指定时使用默认工作区",
    )
    max_depth: int = Field(
        default=1,
        ge=1,
        le=5,
        description="遍历深度，1 表示只列出当前目录",
    )
    include_hidden: bool = Field(
        default=False,
        description="是否包含以 . 开头的隐藏文件/目录",
    )
    include_files: bool = Field(
        default=True,
        description="是否包含文件",
    )
    include_dirs: bool = Field(
        default=True,
        description="是否包含目录",
    )


@tool(args_schema=ListDirectoryInput)
def list_directory(
    path: Optional[str] = None,
    workspace: Optional[str] = None,
    max_depth: int = 2,
    include_hidden: bool = False,
    include_files: bool = True,
    include_dirs: bool = True,
) -> str:
    """列出指定代码库目录下的文件和子目录，用于浏览项目结构。"""
    try:
        root = os.path.abspath(CodeWorkspaceConfig.get_workspace_root(workspace))
        rel_path = path or ""
        target = os.path.abspath(os.path.join(root, rel_path))

        # 路径越界检查
        try:
            common = os.path.commonpath([root, target])
        except ValueError:
            return json.dumps({"error": "路径非法", "path": rel_path}, ensure_ascii=False)
        if common != root:
            return json.dumps({
                "error": "路径越界，不允许访问项目根目录之外的文件",
                "path": rel_path,
            }, ensure_ascii=False)

        if not os.path.isdir(target):
            return json.dumps({
                "error": "目录不存在或不是有效目录",
                "path": rel_path,
            }, ensure_ascii=False)

        entries = []
        root_abs = root

        for dirpath, dirnames, filenames in os.walk(target):
            rel_dir = os.path.relpath(dirpath, target)
            if rel_dir == ".":
                depth = 0
            else:
                depth = rel_dir.count(os.sep) + 1

            # 超出最大深度则不再向下遍历
            if depth >= max_depth:
                dirnames[:] = []

            # 过滤隐藏目录
            if not include_hidden:
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                filenames = [f for f in filenames if not f.startswith(".")]

            # 目录条目
            if include_dirs:
                for d in dirnames:
                    full_path = os.path.join(dirpath, d)
                    rel = os.path.relpath(full_path, root_abs)
                    try:
                        stat = os.stat(full_path)
                        modified_at = datetime.fromtimestamp(stat.st_mtime).isoformat()
                    except OSError:
                        stat = None
                        modified_at = None
                    entries.append({
                        "name": d,
                        "path": rel.replace("\\", "/"),
                        "type": "directory",
                        "size": None,
                        "modified_at": modified_at,
                    })

            # 文件条目
            if include_files:
                for f in filenames:
                    full_path = os.path.join(dirpath, f)
                    rel = os.path.relpath(full_path, root_abs)
                    try:
                        stat = os.stat(full_path)
                        size = stat.st_size
                        modified_at = datetime.fromtimestamp(stat.st_mtime).isoformat()
                    except OSError:
                        size = None
                        modified_at = None
                    entries.append({
                        "name": f,
                        "path": rel.replace("\\", "/"),
                        "type": "file",
                        "size": size,
                        "modified_at": modified_at,
                    })

        result = {
            "root": root_abs.replace("\\", "/"),
            "path": os.path.relpath(target, root_abs).replace("\\", "/"),
            "max_depth": max_depth,
            "entries": entries,
        }
        return json.dumps(result, ensure_ascii=False, default=str)

    except Exception as e:
        logger.error(f"[list_directory] 失败: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============================================================
# read_file
# ============================================================

class ReadFileInput(BaseModel):
    path: str = Field(..., description="仅传文件名如 'MyClass.java'，也兼容相对项目根目录的文件路径，如 'backend/app/main.py'，注意winodws分隔符")
    workspace: Optional[str] = Field(
        default=None,
        description="目标代码库标识符。不指定时使用默认工作区",
    )
    max_bytes: int = Field(
        default=200_000,
        ge=1,
        le=2_000_000,
        description="最大读取字节数，防止一次读取过大文件",
    )


@tool(args_schema=ReadFileInput)
def read_file(path: str, workspace: Optional[str] = None, max_bytes: int = 200_000) -> str:
    """读取指定代码库中文件的文本内容（可能被截断）。"""
    try:
        root = os.path.abspath(CodeWorkspaceConfig.get_workspace_root(workspace))
        logger.info(f"[read_file] 尝试读取文件: {path}，当前代码库根目录: {root}")

        # 规范化传入路径/文件名
        raw_path = path.strip()
        normalized = raw_path.replace("\\", "/")

        # 判断是"仅文件名"还是包含目录的路径
        has_sep = "/" in normalized or "\\" in raw_path

        resolved_rel_path = normalized

        if not has_sep:
            # 仅传入文件名：在项目根目录下递归搜索同名文件
            matches: list[str] = []
            for dirpath, _, filenames in os.walk(root):
                for fname in filenames:
                    if fname == normalized:
                        rel = os.path.relpath(os.path.join(dirpath, fname), root)
                        matches.append(rel.replace("\\", "/"))

            if not matches:
                return json.dumps({
                    "error": "未在项目根目录内找到同名文件",
                    "path": raw_path,
                }, ensure_ascii=False)

            if len(matches) > 1:
                # 多个重名文件，返回候选列表让上层自行选择
                return json.dumps({
                    "error": "ambiguous_path",
                    "message": "找到多个同名文件，请根据 candidates 中的路径选择一个精确路径重新调用 read_file",
                    "path": raw_path,
                    "candidates": matches,
                }, ensure_ascii=False)

            # 唯一匹配，使用该相对路径继续后续逻辑
            resolved_rel_path = matches[0]

        # 兼容 Windows 路径分隔符，按解析后的相对路径拼接
        full_path = os.path.abspath(os.path.join(root, resolved_rel_path.replace("\\", "/")))

        try:
            common = os.path.commonpath([root, full_path])
        except ValueError:
            return json.dumps({"error": "路径非法", "path": path}, ensure_ascii=False)
        if common != root:
            return json.dumps({
                "error": "路径越界，不允许访问项目根目录之外的文件",
                "path": resolved_rel_path,
            }, ensure_ascii=False)

        if not os.path.isfile(full_path):
            # 兜底：如果按传入路径找不到文件，再按文件名在项目根目录内搜索一次
            basename = os.path.basename(normalized)
            # 避免与前面的"仅文件名"逻辑重复，这里只在原始路径包含分隔符时兜底
            if basename and basename != normalized:
                matches: list[str] = []
                for dirpath, _, filenames in os.walk(root):
                    for fname in filenames:
                        if fname == basename:
                            rel = os.path.relpath(os.path.join(dirpath, fname), root)
                            matches.append(rel.replace("\\", "/"))

                if not matches:
                    return json.dumps({
                        "error": "文件不存在或不是普通文件",
                        "path": path,
                    }, ensure_ascii=False)

                if len(matches) > 1:
                    # 多个重名文件，返回候选列表让上层自行选择
                    return json.dumps({
                        "error": "ambiguous_path",
                        "message": "找到多个同名文件，请根据 candidates 中的路径选择一个精确路径重新调用 read_file",
                        "path": basename,
                        "candidates": matches,
                    }, ensure_ascii=False)

                # 唯一匹配，使用该相对路径继续后续读取逻辑
                resolved_rel_path = matches[0]
                full_path = os.path.abspath(os.path.join(root, resolved_rel_path.replace("\\", "/")))
            else:
                return json.dumps({
                    "error": "文件不存在或不是普通文件",
                    "path": path,
                }, ensure_ascii=False)

        # 读取原始字节
        with open(full_path, "rb") as f:
            data = f.read(max_bytes + 1)

        truncated = len(data) > max_bytes
        if truncated:
            data = data[:max_bytes]

        # 尝试多种编码解码
        encoding_candidates = ["utf-8", "utf-8-sig", "latin-1"]
        last_error = None
        text = None
        used_encoding = None
        for enc in encoding_candidates:
            try:
                text = data.decode(enc)
                used_encoding = enc
                break
            except UnicodeDecodeError as de:
                last_error = de
        if text is None:
            msg = "无法以文本方式读取文件（可能是二进制文件）"
            if last_error is not None:
                msg = f"{msg}: {last_error}"
            return json.dumps({
                "error": msg,
                "path": path,
            }, ensure_ascii=False)

        try:
            size = os.path.getsize(full_path)
        except OSError:
            size = None

        result = {
            "path": resolved_rel_path,
            "absolute_path": full_path.replace("\\", "/"),
            "encoding": used_encoding,
            "size": size,
            "truncated": truncated,
            "max_bytes": max_bytes,
            "content": text,
        }
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        logger.error(f"[read_file] 失败: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============================================================
# read_file_range
# ============================================================

class ReadFileRangeInput(BaseModel):
    path: str = Field(..., description="相对项目根目录的文件路径，如 'backend/app/main.py'")
    workspace: Optional[str] = Field(
        default=None,
        description="目标代码库标识符。不指定时使用默认工作区",
    )
    start_line: int = Field(..., ge=1, description="起始行号（从 1 开始，包含）")
    end_line: int = Field(..., ge=1, description="结束行号（从 1 开始，包含）")


@tool(args_schema=ReadFileRangeInput)
def read_file_range(path: str, workspace: Optional[str] = None, start_line: int = 1, end_line: int = 100) -> str:
    """按行读取指定代码库文件的部分内容，用于查看局部代码上下文。"""
    try:
        if end_line < start_line:
            return json.dumps({
                "error": "end_line 必须大于等于 start_line",
                "path": path,
                "start_line": start_line,
                "end_line": end_line,
            }, ensure_ascii=False)

        root = os.path.abspath(CodeWorkspaceConfig.get_workspace_root(workspace))
        full_path = os.path.abspath(os.path.join(root, path))

        try:
            common = os.path.commonpath([root, full_path])
        except ValueError:
            return json.dumps({"error": "路径非法", "path": path}, ensure_ascii=False)
        if common != root:
            return json.dumps({
                "error": "路径越界，不允许访问项目根目录之外的文件",
                "path": path,
            }, ensure_ascii=False)

        if not os.path.isfile(full_path):
            return json.dumps({
                "error": "文件不存在或不是普通文件",
                "path": path,
            }, ensure_ascii=False)

        lines = []
        total_lines = 0

        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            for idx, line in enumerate(f, start=1):
                total_lines = idx
                if start_line <= idx <= end_line:
                    lines.append({"line_no": idx, "text": line.rstrip("\n")})

        if start_line > total_lines:
            return json.dumps({
                "error": f"行号超出文件范围（总行数: {total_lines})",
                "path": path,
                "start_line": start_line,
                "end_line": end_line,
                "total_lines": total_lines,
            }, ensure_ascii=False)

        result = {
            "path": path,
            "absolute_path": full_path.replace("\\", "/"),
            "start_line": start_line,
            "end_line": end_line,
            "total_lines": total_lines,
            "lines": lines,
        }
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        logger.error(f"[read_file_range] 失败: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============================================================
# grep_code
# ============================================================

class GrepCodeInput(BaseModel):
    """grep_code 工具输入参数"""
    pattern: str = Field(..., description="搜索模式，支持正则表达式。如 'getUserById'、'class.*Service'、'def\\s+process_'")
    workspace: str = Field(..., description="目标代码库名称")
    path: Optional[str] = Field(default=None, description="限制搜索的子目录路径，如 'src/services'。不指定则搜索整个代码库")
    file_pattern: Optional[str] = Field(default=None, description="文件名 glob 过滤，如 '*.java'、'*.py'、'*.ts'")
    ignore_case: bool = Field(default=True, description="是否忽略大小写，默认忽略")
    context_lines: int = Field(default=3, ge=0, le=10, description="匹配行前后显示的上下文行数，默认3行")
    max_matches: int = Field(default=30, ge=1, le=100, description="最大匹配数量，防止结果过多")


@tool(args_schema=GrepCodeInput)
def grep_code(
    pattern: str,
    workspace: str,
    path: Optional[str] = None,
    file_pattern: Optional[str] = None,
    ignore_case: bool = True,
    context_lines: int = 3,
    max_matches: int = 30,
) -> str:
    """在代码库中精确搜索文本或正则表达式，快速定位函数、类、变量等。
    
    适用场景：
    - 精确查找函数名、类名、变量名的定义和引用
    - 搜索特定字符串、错误消息、日志关键词
    - 查找特定模式的代码（如所有注释）
    
    与 search_code_context 的区别：
    - grep_code: 精确的文本/正则匹配，速度快，适合已知关键词
    - search_code_context: 语义级搜索，理解代码含义，适合模糊需求
    """
    import subprocess
    from backend.app.core.ripgrep import get_ripgrep_path, is_ripgrep_installed
    
    try:
        if not is_ripgrep_installed():
            return json.dumps({
                "error": "ripgrep 未安装，请重启服务器自动安装或手动安装",
            }, ensure_ascii=False)
        
        rg_path = get_ripgrep_path()
        root = os.path.abspath(CodeWorkspaceConfig.get_workspace_root(workspace))
        search_path = os.path.join(root, path) if path else root
        
        # 验证搜索路径
        if not os.path.exists(search_path):
            return json.dumps({
                "error": f"搜索路径不存在: {path}",
                "workspace": workspace,
            }, ensure_ascii=False)
        
        # 构建 ripgrep 命令
        cmd = [
            rg_path,
            "--json",           # JSON 输出便于解析
            "--no-heading",     # 不分组显示
            "-m", str(max_matches),  # 限制总匹配数
        ]
        
        if ignore_case:
            cmd.append("-i")
        
        if context_lines > 0:
            cmd.extend(["-C", str(context_lines)])
        
        if file_pattern:
            cmd.extend(["-g", file_pattern])
        
        cmd.append(pattern)
        cmd.append(search_path)
        
        # 执行搜索（指定 UTF-8 编码，处理 Windows 默认 GBK 问题）
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=30,
            cwd=root
        )
        
        # 解析 JSON 输出
        matches = []
        current_file = None
        current_match = None
        
        stdout = result.stdout or ""
        for line in stdout.strip().split("\n"):
            if not line:
                continue
            try:
                data = json.loads(line)
                msg_type = data.get("type")
                
                if msg_type == "match":
                    # 保存上一个匹配
                    if current_match:
                        matches.append(current_match)
                    
                    match_data = data.get("data", {})
                    file_path = match_data.get("path", {}).get("text", "")
                    rel_path = os.path.relpath(file_path, root).replace("\\", "/")
                    
                    current_match = {
                        "file": rel_path,
                        "line_number": match_data.get("line_number"),
                        "line_text": match_data.get("lines", {}).get("text", "").rstrip("\n\r"),
                        "context_before": [],
                        "context_after": [],
                    }
                    current_file = rel_path
                    
                elif msg_type == "context" and current_match:
                    # 上下文行
                    ctx_data = data.get("data", {})
                    ctx_line_num = ctx_data.get("line_number")
                    ctx_text = ctx_data.get("lines", {}).get("text", "").rstrip("\n\r")
                    
                    if ctx_line_num < current_match["line_number"]:
                        current_match["context_before"].append(ctx_text)
                    else:
                        current_match["context_after"].append(ctx_text)
                        
            except json.JSONDecodeError:
                continue
        
        # 添加最后一个匹配
        if current_match:
            matches.append(current_match)
        
        if not matches:
            return json.dumps({
                "pattern": pattern,
                "workspace": workspace,
                "path": path,
                "matches": [],
                "message": f"未找到匹配 '{pattern}' 的内容"
            }, ensure_ascii=False)
        
        return json.dumps({
            "pattern": pattern,
            "workspace": workspace,
            "path": path,
            "total_matches": len(matches),
            "matches": matches,
        }, ensure_ascii=False)
        
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "搜索超时，请缩小搜索范围"}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[grep_code] 失败: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)

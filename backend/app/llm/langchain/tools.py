"""LangChain Chat 工具集

基于 LangChain @tool 装饰器实现的 8 个工具函数：
- 实体发现类（3个）：search_businesses, search_implementations, search_data_resources
- 上下文类（3个）：get_business_context, get_implementation_context, get_resource_context
- 图拓扑类（2个）：get_neighbors, get_path_between_entities

实体发现采用"候选列表 + 快速模型选择"方案。
"""

import json
import os
from datetime import datetime
from typing import Optional, List

from langchain_core.tools import tool
from pydantic import BaseModel, Field
import litellm

from backend.app.db.sqlite import SessionLocal
from backend.app.models.resource_graph import (
    Business,
    Step,
    Implementation,
    DataResource,
)
from backend.app.services.graph_service import (
    get_business_context as _get_business_context,
    get_implementation_context as _get_implementation_context,
    get_resource_context as _get_resource_context,
    get_resource_usages as _get_resource_usages,
    get_neighborhood,
)
from backend.app.llm.factory import get_litellm_config
from backend.app.llm.config import CodeWorkspaceConfig
from backend.app.core.logger import logger
from backend.mcp.ace_code_engine import get_ace_mcp_client


# ============================================================
# 小 LLM 实体选择器
# ============================================================

ENTITY_SELECTOR_PROMPT = """你是一个实体匹配助手。根据用户的查询描述，从候选列表中选择最相关的实体。

## 用户查询
{query}

## 候选列表（JSON 格式）
```json
{candidates}
```

## 任务
请分析用户查询，从上述 JSON 候选列表中选择最相关的实体（最多选择 {limit} 个）。
只返回你认为相关的实体，如果没有相关的可以返回空列表。

## 输出格式
请严格按 JSON 格式返回选中的实体 ID 列表，例如：
{{"selected_ids": ["id1", "id2"]}}

## **重要** 严禁更改 id 的内容！必须从候选列表中原样复制 id 值！

只输出 JSON，不要有其他内容。"""


def _call_selector_llm(query: str, candidates: List[dict], id_field: str, limit: int = 5) -> List[str]:
    """调用小 LLM 进行实体选择
    
    Args:
        query: 用户查询
        candidates: 候选列表（字典列表）
        id_field: ID 字段名（如 'process_id', 'impl_id' 等）
        limit: 最多选择数量
    
    Returns:
        选中的 ID 列表
    """
    db = SessionLocal()
    try:
        config = get_litellm_config(db)
        
        # 将候选列表转为 JSON 字符串
        candidates_json = json.dumps(candidates, ensure_ascii=False, indent=2)
        
        prompt = ENTITY_SELECTOR_PROMPT.format(
            query=query,
            candidates=candidates_json,
            limit=limit,
        )
        
        logger.debug(f"[EntitySelector] 调用模型: {config.model}, base: {config.api_base}")
        
        response = litellm.completion(
            model=config.model,
            api_key=config.api_key,
            api_base=config.api_base,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=2000,
        )

        logger.debug(f"[EntitySelector] 模型响应: {response}")
        result_text = response.choices[0].message.content.strip()
        logger.debug(f"[EntitySelector] LLM 返回: {result_text}")
        
        # 检查是否为空
        if not result_text:
            logger.warning("[EntitySelector] LLM 返回空内容")
            return []
        
        # 解析 JSON
        if result_text.startswith("```"):
            lines = result_text.split("```")
            if len(lines) >= 2:
                result_text = lines[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
        
        result_text = result_text.strip()
        result = json.loads(result_text)
        return result.get("selected_ids", [])
        
    except Exception as e:
        logger.error(f"[EntitySelector] 调用失败: {e}", exc_info=True)
        return []
    finally:
        db.close()


class SearchCodeContextInput(BaseModel):
    query: str = Field(..., description="用于代码上下文检索的自然语言查询，如'开卡接口的校验逻辑'、'支付回调处理流程'")


@tool(args_schema=SearchCodeContextInput)
def search_code_context(query: str) -> str:
    """在代码仓库中检索与查询相关的代码上下文，用于深入了解接口、服务或业务流程的实现细节。"""
    try:
        client = get_ace_mcp_client()
        result = client.search_context(query)
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

class ListDirectoryInput(BaseModel):
    path: Optional[str] = Field(
        default=None,
        description="相对项目根目录的目录路径，如 'backend/app'；为空表示项目根目录",
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
    max_depth: int = 2,
    include_hidden: bool = False,
    include_files: bool = True,
    include_dirs: bool = True,
) -> str:
    """列出指定目录下的文件和子目录，用于浏览项目结构。"""
    try:
        root = os.path.abspath(CodeWorkspaceConfig.get_project_root())
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


class ReadFileInput(BaseModel):
    path: str = Field(..., description="仅传文件名如 'MyClass.java'，也兼容相对项目根目录的文件路径，如 'backend/app/main.py'，注意winodws分隔符")
    max_bytes: int = Field(
        default=200_000,
        ge=1,
        le=2_000_000,
        description="最大读取字节数，防止一次读取过大文件",
    )


@tool(args_schema=ReadFileInput)
def read_file(path: str, max_bytes: int = 200_000) -> str:
    """读取指定文件的文本内容（可能被截断）。"""
    try:
        root = os.path.abspath(CodeWorkspaceConfig.get_project_root())

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


class ReadFileRangeInput(BaseModel):
    path: str = Field(..., description="相对项目根目录的文件路径，如 'backend/app/main.py'")
    start_line: int = Field(..., ge=1, description="起始行号（从 1 开始，包含）")
    end_line: int = Field(..., ge=1, description="结束行号（从 1 开始，包含）")


@tool(args_schema=ReadFileRangeInput)
def read_file_range(path: str, start_line: int, end_line: int) -> str:
    """按行读取文件的部分内容，用于查看局部代码上下文。"""
    try:
        if end_line < start_line:
            return json.dumps({
                "error": "end_line 必须大于等于 start_line",
                "path": path,
                "start_line": start_line,
                "end_line": end_line,
            }, ensure_ascii=False)

        root = os.path.abspath(CodeWorkspaceConfig.get_project_root())
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
# 实体发现类工具
# ============================================================

class SearchBusinessesInput(BaseModel):
    """search_businesses 工具输入参数"""
    query: str = Field(..., description="用户对业务流程的自然语言描述，如：'开卡流程'、'新用户首登送券活动'")
    limit: int = Field(default=5, description="最多返回的候选数量", ge=1, le=20)


@tool(args_schema=SearchBusinessesInput)
def search_businesses(query: str, limit: int = 5) -> str:
    """根据自然语言描述查找业务流程。
    用于当用户提到'某个业务/流程/活动'但没有给出 process_id 时。
    返回最匹配的候选列表，包含 process_id、名称等信息。
    """
    db = SessionLocal()
    try:
        businesses = db.query(Business).all()
        
        if not businesses:
            return json.dumps({
                "candidates": [],
                "message": "暂无业务流程数据"
            }, ensure_ascii=False)
        
        # 构造候选列表（JSON 格式）
        candidates_list = []
        for b in businesses:
            desc = b.description[:80] + "..." if b.description and len(b.description) > 80 else (b.description or "")
            candidates_list.append({
                "process_id": b.process_id,
                "name": b.name,
                "channel": b.channel or "",
                "description": desc,
            })
        
        # 调用小 LLM 进行筛选
        logger.debug(f"[search_businesses] 快速模型输入: query={query}, 候选数={len(candidates_list)}")
        selected_ids = _call_selector_llm(query, candidates_list, "process_id", limit)
        logger.info(f"[search_businesses] 快速模型选中: {selected_ids}")
        
        # 根据选中的 ID 构造结果
        id_to_business = {b.process_id: b for b in businesses}
        candidates = []
        for pid in selected_ids:
            if pid in id_to_business:
                b = id_to_business[pid]
                candidates.append({
                    "process_id": b.process_id,
                    "name": b.name,
                    "description": b.description or "",
                    "channel": b.channel or "",
                })
        
        if not candidates:
            return json.dumps({
                "candidates": [],
                "message": f"在 {len(businesses)} 个业务流程中未找到与 '{query}' 相关的结果",
                "total_count": len(businesses),
            }, ensure_ascii=False)
        
        return json.dumps({
            "query": query,
            "total_count": len(businesses),
            "matched_count": len(candidates),
            "candidates": candidates,
        }, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"[search_businesses] 查询失败: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    finally:
        db.close()


class SearchImplementationsInput(BaseModel):
    """search_implementations 工具输入参数"""
    query: str = Field(..., description="对接口或实现的自然语言描述，如：'订单详情接口'、'支付回调'")
    system: Optional[str] = Field(default=None, description="可选，限制在某个系统内搜索，如 'order-service'")
    limit: int = Field(default=5, description="最多返回的候选数量", ge=1, le=20)


@tool(args_schema=SearchImplementationsInput)
def search_implementations(query: str, system: Optional[str] = None, limit: int = 5) -> str:
    """根据自然语言描述或 URI 片段查找实现/接口。
    例如'订单详情接口'、'/api/order/detail'。
    返回最匹配的候选列表，包含 impl_id、名称、系统等信息。
    """
    db = SessionLocal()
    try:
        q = db.query(Implementation)
        if system:
            q = q.filter(Implementation.system == system)
        implementations = q.all()
        
        if not implementations:
            return json.dumps({
                "candidates": [],
                "message": "暂无匹配的实现/接口数据" + (f"（系统: {system}）" if system else "")
            }, ensure_ascii=False)
        
        # 构造候选列表（JSON 格式）
        candidates_list = []
        for impl in implementations:
            desc = impl.description[:80] + "..." if impl.description and len(impl.description) > 80 else (impl.description or "")
            candidates_list.append({
                "impl_id": impl.impl_id,
                "name": impl.name,
                "type": impl.type or "",
                "system": impl.system or "",
                "description": desc,
            })
        
        # 调用小 LLM 进行筛选
        selected_ids = _call_selector_llm(query, candidates_list, "impl_id", limit)
        logger.info(f"[search_implementations] 快速模型选中: {selected_ids}")
        
        # 根据选中的 ID 构造结果
        id_to_impl = {impl.impl_id: impl for impl in implementations}
        candidates = []
        for iid in selected_ids:
            if iid in id_to_impl:
                impl = id_to_impl[iid]
                candidates.append({
                    "impl_id": impl.impl_id,
                    "name": impl.name,
                    "type": impl.type or "",
                    "system": impl.system or "",
                    "description": impl.description or "",
                })
        
        if not candidates:
            return json.dumps({
                "candidates": [],
                "message": f"在 {len(implementations)} 个实现/接口中未找到与 '{query}' 相关的结果",
                "total_count": len(implementations),
                "system_filter": system,
            }, ensure_ascii=False)
        
        return json.dumps({
            "query": query,
            "system_filter": system,
            "total_count": len(implementations),
            "matched_count": len(candidates),
            "candidates": candidates,
        }, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"[search_implementations] 查询失败: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    finally:
        db.close()


class SearchDataResourcesInput(BaseModel):
    """search_data_resources 工具输入参数"""
    query: str = Field(..., description="对数据资源的自然语言描述，如 '用户资料表'、'订单记录'")
    system: Optional[str] = Field(default=None, description="可选，所属系统过滤")
    limit: int = Field(default=5, description="最多返回的候选数量", ge=1, le=20)


@tool(args_schema=SearchDataResourcesInput)
def search_data_resources(query: str, system: Optional[str] = None, limit: int = 5) -> str:
    """根据自然语言描述查找数据资源（库表或其他数据节点）。
    例如'用户资料表'、'月卡记录表'。
    返回最匹配的候选列表，包含 resource_id、名称等信息。
    """
    db = SessionLocal()
    try:
        q = db.query(DataResource)
        if system:
            q = q.filter(DataResource.system == system)
        resources = q.all()
        
        if not resources:
            return json.dumps({
                "candidates": [],
                "message": "暂无匹配的数据资源" + (f"（系统: {system}）" if system else "")
            }, ensure_ascii=False)
        
        # 构造候选列表（JSON 格式）
        candidates_list = []
        for res in resources:
            desc = res.description[:80] + "..." if res.description and len(res.description) > 80 else (res.description or "")
            candidates_list.append({
                "resource_id": res.resource_id,
                "name": res.name,
                "type": res.type or "",
                "system": res.system or "",
                "description": desc,
            })
        
        # 调用小 LLM 进行筛选
        selected_ids = _call_selector_llm(query, candidates_list, "resource_id", limit)
        logger.info(f"[search_data_resources] 快速模型选中: {selected_ids}")
        
        # 根据选中的 ID 构造结果
        id_to_resource = {res.resource_id: res for res in resources}
        candidates = []
        for rid in selected_ids:
            if rid in id_to_resource:
                res = id_to_resource[rid]
                candidates.append({
                    "resource_id": res.resource_id,
                    "name": res.name,
                    "type": res.type or "",
                    "system": res.system or "",
                    "description": res.description or "",
                })
        
        if not candidates:
            return json.dumps({
                "candidates": [],
                "message": f"在 {len(resources)} 个数据资源中未找到与 '{query}' 相关的结果",
                "total_count": len(resources),
                "system_filter": system,
            }, ensure_ascii=False)
        
        return json.dumps({
            "query": query,
            "system_filter": system,
            "total_count": len(resources),
            "matched_count": len(candidates),
            "candidates": candidates,
        }, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"[search_data_resources] 查询失败: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    finally:
        db.close()


class SearchStepsInput(BaseModel):
    """search_steps 工具输入参数"""
    query: str = Field(..., description="对业务步骤的自然语言描述，如：'风控审核步骤'、'支付成功后的回调处理'")
    limit: int = Field(default=5, description="最多返回的候选数量", ge=1, le=20)


@tool(args_schema=SearchStepsInput)
def search_steps(query: str, limit: int = 5) -> str:
    """根据自然语言描述查找业务步骤。
    用于当用户提到某个步骤但没有给出 step_id 时。
    返回最匹配的候选列表，包含 step_id、名称等信息。
    """
    db = SessionLocal()
    try:
        steps = db.query(Step).all()
        
        if not steps:
            return json.dumps({
                "candidates": [],
                "message": "暂无步骤数据"
            }, ensure_ascii=False)
        
        # 构造候选列表（JSON 格式）
        candidates_list = []
        for s in steps:
            desc = s.description[:80] + "..." if s.description and len(s.description) > 80 else (s.description or "")
            candidates_list.append({
                "step_id": s.step_id,
                "name": s.name,
                "step_type": s.step_type or "",
                "description": desc,
            })
        
        # 调用小 LLM 进行筛选
        selected_ids = _call_selector_llm(query, candidates_list, "step_id", limit)
        logger.info(f"[search_steps] 快速模型选中: {selected_ids}")
        
        # 根据选中的 ID 构造结果
        id_to_step = {s.step_id: s for s in steps}
        candidates = []
        for sid in selected_ids:
            if sid in id_to_step:
                s = id_to_step[sid]
                candidates.append({
                    "step_id": s.step_id,
                    "name": s.name,
                    "description": s.description or "",
                    "step_type": s.step_type or "",
                })
        
        if not candidates:
            return json.dumps({
                "candidates": [],
                "message": f"在 {len(steps)} 个步骤中未找到与 '{query}' 相关的结果",
                "total_count": len(steps),
            }, ensure_ascii=False)
        
        return json.dumps({
            "query": query,
            "total_count": len(steps),
            "matched_count": len(candidates),
            "candidates": candidates,
        }, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"[search_steps] 查询失败: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    finally:
        db.close()


# ============================================================
# 上下文类工具
# ============================================================

class GetBusinessContextInput(BaseModel):
    """get_business_context 工具输入参数"""
    process_ids: List[str] = Field(..., description="业务流程的唯一标识列表，支持批量查询多个 process_id")


@tool(args_schema=GetBusinessContextInput)
def get_business_context(process_ids: List[str]) -> str:
    """获取指定业务流程的完整上下文信息（支持批量查询）。
    包括流程步骤、涉及的实现/接口、数据资源访问等。
    用于深入了解一个或多个业务流程的详细结构。
    """
    try:
        results = []
        errors = []
        
        for process_id in process_ids:
            context = _get_business_context(process_id)
            if context:
                results.append({"process_id": process_id, "context": context})
            else:
                errors.append(f"未找到 process_id={process_id}")
        
        return json.dumps({
            "results": results,
            "total": len(results),
            "errors": errors if errors else None
        }, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"[get_business_context] 查询失败: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


class GetImplementationContextInput(BaseModel):
    """get_implementation_context 工具输入参数"""
    impl_ids: List[str] = Field(..., description="实现/接口的唯一标识列表，支持批量查询多个 impl_id")


@tool(args_schema=GetImplementationContextInput)
def get_implementation_context(impl_ids: List[str]) -> str:
    """获取指定实现/接口的上下文信息（支持批量查询）。
    包括该接口所属系统、访问的数据资源、调用的其他接口等。
    用于了解一个或多个接口的技术细节和依赖关系。
    """
    try:
        results = []
        errors = []
        
        for impl_id in impl_ids:
            context = _get_implementation_context(impl_id)
            if context:
                results.append({"impl_id": impl_id, "context": context})
            else:
                errors.append(f"未找到 impl_id={impl_id}")
        
        return json.dumps({
            "results": results,
            "total": len(results),
            "errors": errors if errors else None
        }, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"[get_implementation_context] 查询失败: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


class GetImplementationBusinessUsagesInput(BaseModel):
    """get_implementation_business_usages 工具输入参数"""
    impl_ids: List[str] = Field(..., description="实现/接口的唯一标识列表，支持批量查询多个 impl_id")


@tool(args_schema=GetImplementationBusinessUsagesInput)
def get_implementation_business_usages(impl_ids: List[str]) -> str:
    """查询指定实现/接口在各业务流程中的使用情况（支持批量查询）。
    返回每个实现被哪些业务流程、哪些步骤使用的汇总信息。
    """
    try:
        results = []
        errors = []
        
        for impl_id in impl_ids:
            context = _get_implementation_context(impl_id)
            if not context:
                errors.append(f"未找到 impl_id={impl_id}")
                continue

            process_usages = context.get("process_usages", []) or []
            process_map = {}

            for usage in process_usages:
                process = usage.get("process") or {}
                step = usage.get("step") or {}
                process_id = process.get("process_id")
                if not process_id:
                    continue

                entry = process_map.setdefault(process_id, {
                    "process": process,
                    "steps": [],
                })

                step_id = step.get("step_id")
                if step_id and all(s.get("step_id") != step_id for s in entry["steps"]):
                    entry["steps"].append(step)

            results.append({
                "impl_id": impl_id,
                "implementation": context.get("implementation"),
                "business_usages": list(process_map.values()),
                "total_businesses": len(process_map),
            })

        return json.dumps({
            "results": results,
            "total": len(results),
            "errors": errors if errors else None
        }, ensure_ascii=False, default=str)

    except Exception as e:
        logger.error(f"[get_implementation_business_usages] 查询失败: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


class GetResourceContextInput(BaseModel):
    """get_resource_context 工具输入参数"""
    resource_ids: List[str] = Field(..., description="数据资源的唯一标识列表，支持批量查询多个 resource_id")


@tool(args_schema=GetResourceContextInput)
def get_resource_context(resource_ids: List[str]) -> str:
    """获取指定数据资源的上下文信息（支持批量查询）。
    包括哪些接口访问了这个资源、以什么方式访问等。
    用于了解一个或多个数据表/资源的使用情况。
    """
    try:
        results = []
        errors = []
        
        for resource_id in resource_ids:
            context = _get_resource_context(resource_id)
            if context:
                results.append({"resource_id": resource_id, "context": context})
            else:
                errors.append(f"未找到 resource_id={resource_id}")
        
        return json.dumps({
            "results": results,
            "total": len(results),
            "errors": errors if errors else None
        }, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"[get_resource_context] 查询失败: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


class GetResourceBusinessUsagesInput(BaseModel):
    """get_resource_business_usages 工具输入参数"""
    resource_ids: List[str] = Field(..., description="数据资源的唯一标识列表，支持批量查询多个 resource_id")


@tool(args_schema=GetResourceBusinessUsagesInput)
def get_resource_business_usages(resource_ids: List[str]) -> str:
    """查询指定数据资源在各业务流程中的使用情况（支持批量查询）。
    返回每个数据资源被哪些业务流程、哪些步骤和实现使用的汇总信息。
    """
    try:
        results = []
        errors = []
        
        for resource_id in resource_ids:
            data = _get_resource_usages(resource_id)
            if not data:
                errors.append(f"未找到 resource_id={resource_id}")
                continue

            usages = data.get("usages", []) or []
            process_map = {}

            for usage in usages:
                process = usage.get("process") or {}
                step = usage.get("step") or {}
                implementation = usage.get("implementation") or {}
                access = usage.get("access") or {}

                process_id = process.get("process_id") or access.get("process_id")
                if not process_id:
                    continue

                entry = process_map.setdefault(process_id, {
                    "process": process,
                    "steps": [],
                    "implementations": [],
                })

                step_id = step.get("step_id")
                if step_id and all(s.get("step_id") != step_id for s in entry["steps"]):
                    entry["steps"].append(step)

                impl_id = implementation.get("impl_id")
                if impl_id and all(i.get("impl_id") != impl_id for i in entry["implementations"]):
                    entry["implementations"].append(implementation)

            results.append({
                "resource_id": resource_id,
                "resource": data.get("resource"),
                "business_usages": list(process_map.values()),
                "total_businesses": len(process_map),
            })

        return json.dumps({
            "results": results,
            "total": len(results),
            "errors": errors if errors else None
        }, ensure_ascii=False, default=str)

    except Exception as e:
        logger.error(f"[get_resource_business_usages] 查询失败: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============================================================
# 图拓扑类工具
# ============================================================

class GetNeighborsInput(BaseModel):
    """get_neighbors 工具输入参数"""
    node_ids: List[str] = Field(..., description="节点 ID 列表（可以是 process_id / impl_id / resource_id），支持批量查询")
    depth: int = Field(default=1, description="遍历深度，默认 1", ge=1, le=3)


@tool(args_schema=GetNeighborsInput)
def get_neighbors(node_ids: List[str], depth: int = 1) -> str:
    """获取指定节点的邻居节点（支持批量查询）。
    返回与这些节点直接或间接相连的节点列表。
    用于探索图结构、发现关联实体。
    """
    try:
        # get_neighborhood 期望 start_nodes 为 [{"type": "xxx", "id": "yyy"}, ...] 格式
        # 由于无法确定 node_id 的具体类型，尝试所有可能的类型
        start_nodes = []
        for node_id in node_ids:
            start_nodes.extend([
                {"type": "business", "id": node_id},
                {"type": "implementation", "id": node_id},
                {"type": "resource", "id": node_id},
            ])
        
        result = get_neighborhood(start_nodes, depth)
        if not result:
            return json.dumps({
                "node_ids": node_ids,
                "neighbors": [],
                "message": f"未找到节点或这些节点没有邻居"
            }, ensure_ascii=False)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"[get_neighbors] 查询失败: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


class GetPathInput(BaseModel):
    """get_path_between_entities 工具输入参数"""
    source_id: str = Field(..., description="起点节点 ID")
    target_id: str = Field(..., description="终点节点 ID")
    max_depth: int = Field(default=5, description="最大路径长度", ge=1, le=10)


@tool(args_schema=GetPathInput)
def get_path_between_entities(source_id: str, target_id: str, max_depth: int = 5) -> str:
    """查找两个实体之间的路径。
    返回从起点到终点的最短路径及经过的节点和关系。
    用于分析实体间的依赖链路和数据流向。
    """
    from backend.app.db.neo4j_client import get_neo4j_driver
    
    try:
        driver = get_neo4j_driver()
        with driver.session() as session:
            # 使用 shortestPath 查找最短路径
            result = session.run("""
                MATCH path = shortestPath(
                    (source {id: $source_id})-[*1..$max_depth]-(target {id: $target_id})
                )
                RETURN path,
                       [n in nodes(path) | {id: n.id, name: n.name, labels: labels(n)}] as nodes,
                       [r in relationships(path) | {type: type(r), start: startNode(r).id, end: endNode(r).id}] as relationships
            """, source_id=source_id, target_id=target_id, max_depth=max_depth)
            
            record = result.single()
            if not record:
                return json.dumps({
                    "source_id": source_id,
                    "target_id": target_id,
                    "path_found": False,
                    "message": f"在深度 {max_depth} 内未找到从 {source_id} 到 {target_id} 的路径"
                }, ensure_ascii=False)
            
            return json.dumps({
                "source_id": source_id,
                "target_id": target_id,
                "path_found": True,
                "path_length": len(record["nodes"]) - 1,
                "nodes": record["nodes"],
                "relationships": record["relationships"],
            }, ensure_ascii=False)
            
    except Exception as e:
        logger.error(f"[get_path_between_entities] 查询失败: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============================================================
# 工具列表导出
# ============================================================

def get_all_chat_tools():
    """获取所有 Chat 工具列表"""
    return [
        search_businesses,
        search_implementations,
        search_data_resources,
        search_steps,
        get_business_context,
        get_implementation_context,
        get_implementation_business_usages,
        get_resource_context,
        get_resource_business_usages,
        get_neighbors,
        get_path_between_entities,
        search_code_context,
        list_directory,
        read_file,
        read_file_range,
    ]


if __name__ == "__main__":
    # 测试工具（项目路径已在 AceCodeEngineMcp 中配置）
    print(read_file.invoke(("vehicle-owner-server\\owner-center\\owner-center-api\\src\\main\\java\\com\\keytop\\yongce\\owner\\api\\service\fix\\FixCloseParkService.java")))

"""LangChain Chat 工具集

基于 LangChain @tool 装饰器实现的 8 个工具函数：
- 实体发现类（3个）：search_businesses, search_implementations, search_data_resources
- 上下文类（3个）：get_business_context, get_implementation_context, get_resource_context
- 图拓扑类（2个）：get_neighbors, get_path_between_entities

实体发现采用"候选列表 + 小LLM选择"方案。
"""

import json
from typing import Optional, List

from langchain_core.tools import tool
from pydantic import BaseModel, Field
import litellm

from backend.app.db.sqlite import SessionLocal
from backend.app.models.resource_graph import (
    Business,
    Implementation,
    DataResource,
)
from backend.app.services.graph_service import (
    get_business_context as _get_business_context,
    get_implementation_context as _get_implementation_context,
    get_resource_context as _get_resource_context,
    get_neighborhood,
)
from backend.app.llm.base import get_litellm_config
from backend.app.core.logger import logger


# ============================================================
# 小 LLM 实体选择器
# ============================================================

ENTITY_SELECTOR_PROMPT = """你是一个实体匹配助手。根据用户的查询描述，从候选列表中选择最相关的实体。

## 用户查询
{query}

## 候选列表
{candidates}

## 任务
请分析用户查询，从候选列表中选择最相关的实体（最多选择 {limit} 个）。
只返回你认为相关的实体，如果没有相关的可以返回空列表。

## 输出格式
请严格按 JSON 格式返回选中的实体 ID 列表，例如：
{{"selected_ids": ["id1", "id2"]}}

只输出 JSON，不要有其他内容。"""


def _call_selector_llm(query: str, candidates_text: str, limit: int = 5) -> List[str]:
    """调用小 LLM 进行实体选择"""
    db = SessionLocal()
    try:
        config = get_litellm_config(db)
        
        prompt = ENTITY_SELECTOR_PROMPT.format(
            query=query,
            candidates=candidates_text,
            limit=limit,
        )
        
        logger.debug(f"[EntitySelector] 调用模型: {config.model}, base: {config.api_base}")
        
        response = litellm.completion(
            model=config.model,
            api_key=config.api_key,
            api_base=config.api_base,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200,
        )
        
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
        
        # 构造候选列表文本
        lines = []
        for b in businesses:
            desc = b.description[:80] + "..." if b.description and len(b.description) > 80 else (b.description or "无描述")
            channel = f"[{b.channel}]" if b.channel else ""
            lines.append(f"- ID: {b.process_id} | 名称: {b.name} {channel} | 描述: {desc}")
        candidates_text = "\n".join(lines)
        
        # 调用小 LLM 进行筛选
        selected_ids = _call_selector_llm(query, candidates_text, limit)
        logger.info(f"[search_businesses] 小LLM选中: {selected_ids}")
        
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
        
        # 构造候选列表文本
        lines = []
        for impl in implementations:
            desc = impl.description[:80] + "..." if impl.description and len(impl.description) > 80 else (impl.description or "无描述")
            sys_info = f"[{impl.system}]" if impl.system else ""
            type_info = f"({impl.type})" if impl.type else ""
            lines.append(f"- ID: {impl.impl_id} | 名称: {impl.name} {sys_info} {type_info} | 描述: {desc}")
        candidates_text = "\n".join(lines)
        
        # 调用小 LLM 进行筛选
        selected_ids = _call_selector_llm(query, candidates_text, limit)
        logger.info(f"[search_implementations] 小LLM选中: {selected_ids}")
        
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
        
        # 构造候选列表文本
        lines = []
        for res in resources:
            desc = res.description[:80] + "..." if res.description and len(res.description) > 80 else (res.description or "无描述")
            sys_info = f"[{res.system}]" if res.system else ""
            type_info = f"({res.type})" if res.type else ""
            lines.append(f"- ID: {res.resource_id} | 名称: {res.name} {sys_info} {type_info} | 描述: {desc}")
        candidates_text = "\n".join(lines)
        
        # 调用小 LLM 进行筛选
        selected_ids = _call_selector_llm(query, candidates_text, limit)
        logger.info(f"[search_data_resources] 小LLM选中: {selected_ids}")
        
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


# ============================================================
# 上下文类工具
# ============================================================

class GetBusinessContextInput(BaseModel):
    """get_business_context 工具输入参数"""
    process_id: str = Field(..., description="业务流程的唯一标识 (process_id)")


@tool(args_schema=GetBusinessContextInput)
def get_business_context(process_id: str) -> str:
    """获取指定业务流程的完整上下文信息。
    包括流程步骤、涉及的实现/接口、数据资源访问等。
    用于深入了解某个业务流程的详细结构。
    """
    try:
        context = _get_business_context(process_id)
        if not context:
            return json.dumps({
                "error": f"未找到 process_id={process_id} 的业务流程"
            }, ensure_ascii=False)
        return json.dumps(context, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"[get_business_context] 查询失败: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


class GetImplementationContextInput(BaseModel):
    """get_implementation_context 工具输入参数"""
    impl_id: str = Field(..., description="实现/接口的唯一标识 (impl_id)")


@tool(args_schema=GetImplementationContextInput)
def get_implementation_context(impl_id: str) -> str:
    """获取指定实现/接口的上下文信息。
    包括该接口所属系统、访问的数据资源、调用的其他接口等。
    用于了解某个接口的技术细节和依赖关系。
    """
    try:
        context = _get_implementation_context(impl_id)
        if not context:
            return json.dumps({
                "error": f"未找到 impl_id={impl_id} 的实现/接口"
            }, ensure_ascii=False)
        return json.dumps(context, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"[get_implementation_context] 查询失败: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


class GetResourceContextInput(BaseModel):
    """get_resource_context 工具输入参数"""
    resource_id: str = Field(..., description="数据资源的唯一标识 (resource_id)")


@tool(args_schema=GetResourceContextInput)
def get_resource_context(resource_id: str) -> str:
    """获取指定数据资源的上下文信息。
    包括哪些接口访问了这个资源、以什么方式访问等。
    用于了解某个数据表/资源的使用情况。
    """
    try:
        context = _get_resource_context(resource_id)
        if not context:
            return json.dumps({
                "error": f"未找到 resource_id={resource_id} 的数据资源"
            }, ensure_ascii=False)
        return json.dumps(context, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"[get_resource_context] 查询失败: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============================================================
# 图拓扑类工具
# ============================================================

class GetNeighborsInput(BaseModel):
    """get_neighbors 工具输入参数"""
    node_id: str = Field(..., description="节点 ID（可以是 process_id / impl_id / resource_id）")
    depth: int = Field(default=1, description="遍历深度，默认 1", ge=1, le=3)


@tool(args_schema=GetNeighborsInput)
def get_neighbors(node_id: str, depth: int = 1) -> str:
    """获取指定节点的邻居节点。
    返回与该节点直接或间接相连的节点列表。
    用于探索图结构、发现关联实体。
    """
    try:
        # get_neighborhood 期望 start_nodes 为 [{"type": "xxx", "id": "yyy"}, ...] 格式
        # 由于无法确定 node_id 的具体类型，尝试所有可能的类型
        start_nodes = [
            {"type": "business", "id": node_id},
            {"type": "implementation", "id": node_id},
            {"type": "resource", "id": node_id},
        ]
        result = get_neighborhood(start_nodes, depth)
        if not result:
            return json.dumps({
                "node_id": node_id,
                "neighbors": [],
                "message": f"未找到节点 {node_id} 或该节点没有邻居"
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
        get_business_context,
        get_implementation_context,
        get_resource_context,
        get_neighbors,
        get_path_between_entities,
    ]

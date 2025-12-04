"""实体发现类工具

提供基于自然语言的实体模糊搜索能力：
- search_businesses: 搜索业务流程
- search_implementations: 搜索实现/接口
- search_data_resources: 搜索数据资源
- search_steps: 搜索业务步骤
"""

import json
from typing import Optional, List

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.app.db.sqlite import SessionLocal
from backend.app.models.resource_graph import Business, Step, Implementation, DataResource
from backend.app.core.logger import logger
from ._common import call_selector_llm


# ============================================================
# search_businesses
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
        selected_ids = call_selector_llm(query, candidates_list, "process_id", limit)
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


# ============================================================
# search_implementations
# ============================================================

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
        selected_ids = call_selector_llm(query, candidates_list, "impl_id", limit)
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


# ============================================================
# search_data_resources
# ============================================================

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
        selected_ids = call_selector_llm(query, candidates_list, "resource_id", limit)
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


# ============================================================
# search_steps
# ============================================================

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
        selected_ids = call_selector_llm(query, candidates_list, "step_id", limit)
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

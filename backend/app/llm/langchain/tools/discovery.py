"""实体发现类工具

提供基于自然语言的实体模糊搜索能力：
- search_businesses: 搜索业务流程
- search_implementations: 搜索实现/接口
- search_data_resources: 搜索数据资源
- search_steps: 搜索业务步骤

## 搜索流程（两阶段筛选）

1. **SQL 预过滤阶段**：
   - 从用户 query 提取关键词
   - 用 SQL LIKE 在 name/description 上过滤
   - 将几百条候选缩减到 ≤50 条

2. **LLM 精排阶段**：
   - 将预过滤后的候选（精简字段）交给小模型
   - 小模型根据语义相关性选出 Top N

这种设计解决了大数据量场景下小模型 token 超限的问题。
"""

import json
from typing import Optional, List

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from sqlalchemy import or_

from backend.app.db.sqlite import SessionLocal
from backend.app.models.resource_graph import Business, Step, Implementation, DataResource
from backend.app.core.logger import logger
from ._common import call_selector_llm, extract_keywords


# ============================================================
# 常量配置
# ============================================================

# SQL 预过滤后的最大候选数量（过滤后超过此数则截断）
MAX_CANDIDATES_AFTER_FILTER = 50

# 预过滤无结果时的随机采样数量（让模型看看有什么可选的）
FALLBACK_SAMPLE_SIZE = 20


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
        # ========== 阶段1: SQL 预过滤 ==========
        # 从 query 提取关键词，用 LIKE 过滤，减少候选数量
        keywords = extract_keywords(query)
        
        q = db.query(Business)
        if keywords:
            # 构造 OR 条件：任一关键词匹配 name 或 description
            conditions = []
            for kw in keywords:
                conditions.append(Business.name.contains(kw))
                conditions.append(Business.description.contains(kw))
            q = q.filter(or_(*conditions))
        
        businesses = q.limit(MAX_CANDIDATES_AFTER_FILTER).all()
        
        # Fallback: 预过滤无结果时，尝试只用第一个关键词，或随机采样
        if not businesses and keywords:
            logger.debug(f"[search_businesses] 预过滤无结果，尝试放宽条件")
            q = db.query(Business).filter(
                or_(Business.name.contains(keywords[0]), Business.description.contains(keywords[0]))
            )
            businesses = q.limit(MAX_CANDIDATES_AFTER_FILTER).all()
        
        if not businesses:
            # 仍无结果，随机采样让模型看看有什么
            logger.debug(f"[search_businesses] 放宽条件仍无结果，随机采样")
            businesses = db.query(Business).limit(FALLBACK_SAMPLE_SIZE).all()
        
        if not businesses:
            return json.dumps({
                "candidates": [],
                "message": "暂无业务流程数据"
            }, ensure_ascii=False)
        
        # ========== 阶段2: LLM 精排 ==========
        # 构造精简的候选列表（只传 id + name，减少 token）
        candidates_list = []
        for b in businesses:
            candidates_list.append({
                "process_id": b.process_id,
                "name": b.name,
            })
        
        # 调用小 LLM 进行语义精排
        logger.info(f"[search_businesses] 预过滤后候选数={len(candidates_list)}, keywords={keywords}")
        selected_ids = call_selector_llm(query, candidates_list, "process_id", limit)
        logger.info(f"[search_businesses] LLM 精排选中: {selected_ids}")
        
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
        # ========== 阶段1: SQL 预过滤 ==========
        keywords = extract_keywords(query)
        
        q = db.query(Implementation)
        if system:
            q = q.filter(Implementation.system == system)
        
        if keywords:
            # 任一关键词匹配 name 或 description
            conditions = []
            for kw in keywords:
                conditions.append(Implementation.name.contains(kw))
                conditions.append(Implementation.description.contains(kw))
            q = q.filter(or_(*conditions))
        
        implementations = q.limit(MAX_CANDIDATES_AFTER_FILTER).all()
        
        # Fallback: 预过滤无结果
        if not implementations and keywords:
            logger.debug(f"[search_implementations] 预过滤无结果，尝试放宽条件")
            q = db.query(Implementation)
            if system:
                q = q.filter(Implementation.system == system)
            q = q.filter(or_(
                Implementation.name.contains(keywords[0]),
                Implementation.description.contains(keywords[0])
            ))
            implementations = q.limit(MAX_CANDIDATES_AFTER_FILTER).all()
        
        if not implementations:
            logger.debug(f"[search_implementations] 放宽条件仍无结果，随机采样")
            q = db.query(Implementation)
            if system:
                q = q.filter(Implementation.system == system)
            implementations = q.limit(FALLBACK_SAMPLE_SIZE).all()
        
        if not implementations:
            return json.dumps({
                "candidates": [],
                "message": "暂无匹配的实现/接口数据" + (f"（系统: {system}）" if system else "")
            }, ensure_ascii=False)
        
        # ========== 阶段2: LLM 精排 ==========
        # 精简字段：只传 id + name + system（system 有助于区分同名接口）
        candidates_list = []
        for impl in implementations:
            candidates_list.append({
                "impl_id": impl.impl_id,
                "name": impl.name,
                "system": impl.system or "",
            })
        
        logger.info(f"[search_implementations] 预过滤后候选数={len(candidates_list)}, keywords={keywords}")
        selected_ids = call_selector_llm(query, candidates_list, "impl_id", limit)
        logger.info(f"[search_implementations] LLM 精排选中: {selected_ids}")
        
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
        # ========== 阶段1: SQL 预过滤 ==========
        keywords = extract_keywords(query)
        
        q = db.query(DataResource)
        if system:
            q = q.filter(DataResource.system == system)
        
        if keywords:
            conditions = []
            for kw in keywords:
                conditions.append(DataResource.name.contains(kw))
                conditions.append(DataResource.description.contains(kw))
            q = q.filter(or_(*conditions))
        
        resources = q.limit(MAX_CANDIDATES_AFTER_FILTER).all()
        
        # Fallback: 预过滤无结果
        if not resources and keywords:
            logger.debug(f"[search_data_resources] 预过滤无结果，尝试放宽条件")
            q = db.query(DataResource)
            if system:
                q = q.filter(DataResource.system == system)
            q = q.filter(or_(
                DataResource.name.contains(keywords[0]),
                DataResource.description.contains(keywords[0])
            ))
            resources = q.limit(MAX_CANDIDATES_AFTER_FILTER).all()
        
        if not resources:
            logger.debug(f"[search_data_resources] 放宽条件仍无结果，随机采样")
            q = db.query(DataResource)
            if system:
                q = q.filter(DataResource.system == system)
            resources = q.limit(FALLBACK_SAMPLE_SIZE).all()
        
        if not resources:
            return json.dumps({
                "candidates": [],
                "message": "暂无匹配的数据资源" + (f"（系统: {system}）" if system else "")
            }, ensure_ascii=False)
        
        # ========== 阶段2: LLM 精排 ==========
        # 精简字段：只传 id + name
        candidates_list = []
        for res in resources:
            candidates_list.append({
                "resource_id": res.resource_id,
                "name": res.name,
            })
        
        logger.info(f"[search_data_resources] 预过滤后候选数={len(candidates_list)}, keywords={keywords}")
        selected_ids = call_selector_llm(query, candidates_list, "resource_id", limit)
        logger.info(f"[search_data_resources] LLM 精排选中: {selected_ids}")
        
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
        # ========== 阶段1: SQL 预过滤 ==========
        keywords = extract_keywords(query)
        
        q = db.query(Step)
        if keywords:
            conditions = []
            for kw in keywords:
                conditions.append(Step.name.contains(kw))
                conditions.append(Step.description.contains(kw))
            q = q.filter(or_(*conditions))
        
        steps = q.limit(MAX_CANDIDATES_AFTER_FILTER).all()
        
        # Fallback: 预过滤无结果
        if not steps and keywords:
            logger.debug(f"[search_steps] 预过滤无结果，尝试放宽条件")
            q = db.query(Step).filter(or_(
                Step.name.contains(keywords[0]),
                Step.description.contains(keywords[0])
            ))
            steps = q.limit(MAX_CANDIDATES_AFTER_FILTER).all()
        
        if not steps:
            logger.debug(f"[search_steps] 放宽条件仍无结果，随机采样")
            steps = db.query(Step).limit(FALLBACK_SAMPLE_SIZE).all()
        
        if not steps:
            return json.dumps({
                "candidates": [],
                "message": "暂无步骤数据"
            }, ensure_ascii=False)
        
        # ========== 阶段2: LLM 精排 ==========
        # 精简字段：只传 id + name
        candidates_list = []
        for s in steps:
            candidates_list.append({
                "step_id": s.step_id,
                "name": s.name,
            })
        
        logger.info(f"[search_steps] 预过滤后候选数={len(candidates_list)}, keywords={keywords}")
        selected_ids = call_selector_llm(query, candidates_list, "step_id", limit)
        logger.info(f"[search_steps] LLM 精排选中: {selected_ids}")
        
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

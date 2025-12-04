"""上下文获取类工具

根据实体 ID 获取详细上下文信息：
- get_business_context: 获取业务流程上下文
- get_implementation_context: 获取实现/接口上下文
- get_resource_context: 获取数据资源上下文
"""

import json
from typing import List

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.app.services.graph_service import (
    get_business_context as _get_business_context,
    get_implementation_context as _get_implementation_context,
    get_resource_context as _get_resource_context,
)
from backend.app.core.logger import logger


# ============================================================
# get_business_context
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


# ============================================================
# get_implementation_context
# ============================================================

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


# ============================================================
# get_resource_context
# ============================================================

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

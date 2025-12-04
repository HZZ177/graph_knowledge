"""影响面分析类工具

反向查询实现/资源被哪些业务使用：
- get_implementation_business_usages: 查询接口被哪些业务使用
- get_resource_business_usages: 查询数据资源被哪些业务使用
"""

import json
from typing import List

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.app.services.graph_service import (
    get_implementation_context as _get_implementation_context,
    get_resource_usages as _get_resource_usages,
)
from backend.app.core.logger import logger


# ============================================================
# get_implementation_business_usages
# ============================================================

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


# ============================================================
# get_resource_business_usages
# ============================================================

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

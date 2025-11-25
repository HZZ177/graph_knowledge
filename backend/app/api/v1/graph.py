from fastapi import APIRouter, Query, Body

from backend.app.core.utils import success_response, error_response
from backend.app.core.logger import logger
from backend.app.schemas.graph import GraphNeighborhoodRequest, GraphPathRequest
from ...services.graph_service import (
    get_business_context,
    list_businesses,
    get_resource_usages,
    get_resource_context,
    get_implementation_context,
    get_system_usages,
    get_neighborhood,
    find_path,
)


router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/business/context")
async def get_business_context_endpoint(process_id: str = Query(...)) -> dict:
    """获取指定流程在图数据库中的上下文信息。"""
    logger.info(f"获取业务流程上下文 process_id={process_id}")
    try:
        data = get_business_context(process_id)
        logger.info(
            f"获取业务流程上下文成功 process_id={process_id}, steps={len(data.get('steps', []))}"
        )
        return success_response(data=data)
    except ValueError:
        logger.warning(f"获取业务流程上下文失败，流程不存在 process_id={process_id}")
        return error_response(message="Process not found")
    except Exception as exc:  # pragma: no cover  # 防御性兜底
        logger.error(f"获取业务流程上下文异常 process_id={process_id}, error={exc}")
        return error_response(message=str(exc))


@router.get("/business/list")
async def list_businesses_endpoint(
    channel: str | None = Query(None),
    name_contains: str | None = Query(None),
    uses_system: str | None = Query(None),
    uses_resource: str | None = Query(None),
) -> dict:
    """按条件列出业务流程，数据来自 Neo4j。"""
    logger.info(
        f"列出业务流程 channel={channel}, name_contains={name_contains}, uses_system={uses_system}, uses_resource={uses_resource}"
    )
    try:
        items = list_businesses(
            channel=channel,
            name_contains=name_contains,
            uses_system=uses_system,
            uses_resource=uses_resource,
        )
        logger.info(f"列出业务流程完成 count={len(items)}")
        return success_response(data=items)
    except Exception as exc:  # pragma: no cover  # 防御性兜底
        logger.error(f"列出业务流程异常 error={exc}")
        return error_response(message=str(exc))


@router.get("/resource/usages")
async def get_resource_usages_endpoint(resource_id: str = Query(...)) -> dict:
    """查询指定数据资源在各流程中的使用情况。"""
    logger.info(f"查询数据资源使用情况 resource_id={resource_id}")
    try:
        data = get_resource_usages(resource_id)
        logger.info(
            f"查询数据资源使用情况成功 resource_id={resource_id}, usages={len(data.get('usages', []))}"
        )
        return success_response(data=data)
    except ValueError:
        logger.warning(f"查询数据资源使用情况失败，资源不存在 resource_id={resource_id}")
        return error_response(message="DataResource not found")
    except Exception as exc:  # pragma: no cover  # 防御性兜底
        logger.error(f"查询数据资源使用情况异常 resource_id={resource_id}, error={exc}")
        return error_response(message=str(exc))


@router.get("/resource/context")
async def get_resource_context_endpoint(resource_id: str = Query(...)) -> dict:
    """围绕指定数据资源返回相关业务、步骤与实现的子图上下文。"""
    logger.info(f"获取数据资源上下文 resource_id={resource_id}")
    try:
        data = get_resource_context(resource_id)
        logger.info(
            f"获取数据资源上下文成功 resource_id={resource_id}, businesses={len(data.get('businesses', []))}, steps={len(data.get('steps', []))}, implementations={len(data.get('implementations', []))}"
        )
        return success_response(data=data)
    except ValueError:
        logger.warning(f"获取数据资源上下文失败，资源不存在 resource_id={resource_id}")
        return error_response(message="DataResource not found")
    except Exception as exc:  # pragma: no cover  # 防御性兜底
        logger.error(f"获取数据资源上下文异常 resource_id={resource_id}, error={exc}")
        return error_response(message=str(exc))


@router.get("/implementation/context")
async def get_implementation_context_endpoint(impl_id: str = Query(...)) -> dict:
    """获取某个实现在哪些流程和步骤中被使用，以及其上下游依赖。"""
    logger.info(f"获取实现上下文 impl_id={impl_id}")
    try:
        data = get_implementation_context(impl_id)
        logger.info(
            f"获取实现上下文成功 impl_id={impl_id}, process_usages={len(data.get('process_usages', []))}, resources={len(data.get('resources', []))}"
        )
        return success_response(data=data)
    except ValueError:
        logger.warning(f"获取实现上下文失败，实现不存在 impl_id={impl_id}")
        return error_response(message="Implementation not found")
    except Exception as exc:  # pragma: no cover  # 防御性兜底
        logger.error(f"获取实现上下文异常 impl_id={impl_id}, error={exc}")
        return error_response(message=str(exc))


@router.get("/system/usages")
async def get_system_usages_endpoint(system: str = Query(...)) -> dict:
    """查询某个系统在图中的使用情况（通过实现节点聚合）。"""
    logger.info(f"查询系统使用情况 system={system}")
    try:
        data = get_system_usages(system)
        logger.info(
            f"查询系统使用情况完成 system={system}, usages={len(data.get('usages', []))}"
        )
        return success_response(data=data)
    except Exception as exc:  # pragma: no cover  # 防御性兜底
        logger.error(f"查询系统使用情况异常 system={system}, error={exc}")
        return error_response(message=str(exc))


@router.post("/neighborhood")
async def get_neighborhood_endpoint(payload: GraphNeighborhoodRequest = Body(...)) -> dict:
    """从若干起点节点出发，返回限定深度与关系类型的局部邻域子图。"""
    logger.info(
        f"查询图邻域 start_nodes={len(payload.start_nodes)}, depth={payload.depth}, relationship_types={payload.relationship_types}"
    )
    try:
        data = get_neighborhood(
            start_nodes=[ref.dict() for ref in payload.start_nodes],
            depth=payload.depth,
            relationship_types=payload.relationship_types,
        )
        logger.info(
            f"查询图邻域完成 nodes={len(data.get('nodes', []))}, relationships={len(data.get('relationships', []))}"
        )
        return success_response(data=data)
    except ValueError as exc:
        logger.warning(f"查询图邻域参数错误: {exc}")
        return error_response(message=str(exc))
    except Exception as exc:  # pragma: no cover  # 防御性兜底
        logger.error(f"查询图邻域异常 error={exc}")
        return error_response(message=str(exc))


@router.post("/path")
async def find_path_endpoint(payload: GraphPathRequest = Body(...)) -> dict:
    """在图中查找两个节点之间的最短路径（限定最大深度与关系类型）。"""
    logger.info(
        f"查询图最短路径 start={payload.start}, end={payload.end}, max_depth={payload.max_depth}, relationship_types={payload.relationship_types}"
    )
    try:
        data = find_path(
            start=payload.start.dict(),
            end=payload.end.dict(),
            max_depth=payload.max_depth,
            relationship_types=payload.relationship_types,
        )
        logger.info(
            f"查询图最短路径完成 nodes={len(data.get('nodes', []))}, relationships={len(data.get('relationships', []))}"
        )
        return success_response(data=data)
    except ValueError as exc:
        logger.warning(f"查询图最短路径参数错误: {exc}")
        return error_response(message=str(exc))
    except Exception as exc:  # pragma: no cover  # 防御性兜底
        logger.error(f"查询图最短路径异常 error={exc}")
        return error_response(message=str(exc))

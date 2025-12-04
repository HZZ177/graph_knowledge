"""图拓扑类工具

基于 Neo4j 图数据库的拓扑查询：
- get_neighbors: 获取节点的邻居
- get_path_between_entities: 查找两个实体之间的路径
"""

import json
from typing import List

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.app.services.graph_service import get_neighborhood
from backend.app.core.logger import logger


# ============================================================
# get_neighbors
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


# ============================================================
# get_path_between_entities
# ============================================================

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

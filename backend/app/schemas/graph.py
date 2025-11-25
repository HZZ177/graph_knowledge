from typing import List, Literal, Optional

from pydantic import BaseModel


class GraphNodeRef(BaseModel):
    """图中节点引用，用于标识业务、步骤、实现或数据资源等节点。"""

    type: Literal["business", "step", "implementation", "resource"]
    id: str


class GraphNeighborhoodRequest(BaseModel):
    """图邻域查询请求体。

    从多个起点节点出发，在限定深度和关系类型范围内返回局部子图。
    """

    start_nodes: List[GraphNodeRef]
    depth: int = 1
    relationship_types: Optional[List[str]] = None


class GraphPathRequest(BaseModel):
    """图最短路径查询请求体。

    在图中查找起点和终点节点之间的最短路径，可限定最大深度和关系类型。
    """

    start: GraphNodeRef
    end: GraphNodeRef
    max_depth: int = 5
    relationship_types: Optional[List[str]] = None

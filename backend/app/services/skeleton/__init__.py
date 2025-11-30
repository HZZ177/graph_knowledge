"""Skeleton 服务模块

基于 CrewAI 多Agent协作的业务骨架生成服务。
"""

from backend.app.services.skeleton.skeleton_service import (
    generate_skeleton,
    convert_skeleton_to_canvas,
)

__all__ = [
    "generate_skeleton",
    "convert_skeleton_to_canvas",
]

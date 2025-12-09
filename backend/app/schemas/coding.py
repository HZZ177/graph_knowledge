"""Coding 模块 Schema 定义

用于对接 Coding 平台 API，获取需求文档等信息。
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ========== 请求 ==========

class IssueRequest(BaseModel):
    """事项查询请求"""
    project_name: str = "yongcepingtaipro2.0"  # 项目名称
    issue_code: int  # 事项编号


class ProjectListRequest(BaseModel):
    """项目列表查询请求"""
    page_number: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)
    project_name: Optional[str] = "yongcepingtaipro2.0"  # 可选：按项目名称筛选


class IterationListRequest(BaseModel):
    """迭代列表查询请求"""
    project_name: str = "yongcepingtaipro2.0" # 项目名称（必填）
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    keywords: Optional[str] = ""  # 可选：关键词搜索


class IssueListRequest(BaseModel):
    """事项列表查询请求"""
    project_name: str = "yongcepingtaipro2.0"   # 项目名称
    iteration_code: int  # 迭代 Code
    issue_type: str = "REQUIREMENT"  # 事项类型：REQUIREMENT/DEFECT/MISSION/SUB_TASK
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    keyword: Optional[str] = ""  # 可选：关键词搜索


# ========== 数据模型 ==========

class IssueDetail(BaseModel):
    """事项详情"""
    name: str  # 需求名称
    code: int  # 需求 code
    description: str  # 需求详情


class ProjectInfo(BaseModel):
    """项目信息"""
    id: int
    name: str  # 项目标识名（用于 API 调用）
    display_name: str  # 项目显示名称
    description: Optional[str] = ""
    icon: Optional[str] = ""
    status: int = 1
    archived: bool = False
    created_at: int = 0
    updated_at: int = 0


class ProjectListResponse(BaseModel):
    """项目列表响应"""
    page_number: int
    page_size: int
    total_count: int
    project_list: List[ProjectInfo]


class IterationInfo(BaseModel):
    """迭代信息"""
    id: int
    code: int  # 迭代 Code（用于查询事项）
    name: str  # 迭代名称
    status: str  # 状态：WAIT_PROCESS/PROCESSING/COMPLETED
    goal: Optional[str] = ""  # 迭代目标
    start_at: int = 0
    end_at: int = 0
    wait_process_count: int = 0  # 待处理事项数
    processing_count: int = 0  # 进行中事项数
    completed_count: int = 0  # 已完成事项数
    completed_percent: float = 0.0


class IterationListResponse(BaseModel):
    """迭代列表响应"""
    page: int
    page_size: int
    total_page: int
    total_row: int
    iterations: List[IterationInfo]


class IssueInfo(BaseModel):
    """事项信息（列表项）"""
    id: int
    code: int  # 事项 Code（用于获取详情）
    name: str  # 事项名称
    type: str  # 事项类型：REQUIREMENT/DEFECT/MISSION/SUB_TASK
    priority: str  # 优先级
    status_name: str  # 状态名称
    status_type: str  # 状态类型：TODO/PROCESSING/COMPLETED
    iteration_id: int = 0
    iteration_name: Optional[str] = ""
    assignee_names: List[str] = []  # 处理人列表
    created_at: int = 0
    updated_at: int = 0


class IssueListResponse(BaseModel):
    """事项列表响应"""
    total_count: int
    issues: List[IssueInfo]

"""Coding 模块 Schema 定义

用于对接 Coding 平台 API，获取需求文档等信息。
"""

from pydantic import BaseModel


# ========== 请求 ==========

class IssueRequest(BaseModel):
    """事项查询请求"""
    project_name: str  # 项目名称
    issue_code: int  # 事项编号


# ========== 数据模型 ==========

class IssueDetail(BaseModel):
    """事项详情"""
    name: str  # 需求名称
    code: int  # 需求 code
    description: str  # 需求详情

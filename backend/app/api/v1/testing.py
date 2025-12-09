"""需求分析测试助手 API

提供测试会话管理的 REST API。
"""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.db.sqlite import get_db
from backend.app.services import testing_service
from backend.app.core.utils import success_response, error_response
from backend.app.core.logger import logger


router = APIRouter(prefix="/testing", tags=["testing"])


# ============================================================
# 请求/响应模型
# ============================================================

class CreateSessionRequest(BaseModel):
    """创建测试会话请求"""
    project_name: str = Field(..., description="Coding 项目名称")
    requirement_id: str = Field(..., description="需求 ID")
    requirement_name: str = Field(..., description="需求名称")


class StartWorkflowRequest(BaseModel):
    """启动工作流请求（WebSocket 初始消息）"""
    session_id: str = Field(..., description="测试会话 ID")
    requirement_id: str = Field(..., description="需求 ID")
    project_name: str = Field(..., description="项目名称")


# ============================================================
# REST API 端点
# ============================================================

@router.post("/sessions")
async def create_session(
    request: CreateSessionRequest,
    db: Session = Depends(get_db),
):
    """创建测试会话
    
    创建一个新的测试会话，返回 session_id。
    后续使用 WebSocket 连接执行工作流。
    """
    try:
        session_id = await testing_service.create_testing_session(
            db=db,
            project_name=request.project_name,
            requirement_id=request.requirement_id,
            requirement_name=request.requirement_name,
        )
        return success_response(data={
            "session_id": session_id,
        })
    except Exception as e:
        logger.error(f"[TestingAPI] 创建会话失败: {e}")
        return error_response(message=f"创建会话失败: {str(e)}")


@router.get("/sessions")
async def list_sessions(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """获取测试会话列表"""
    try:
        sessions = await testing_service.list_testing_sessions(
            db=db,
            limit=limit,
            offset=offset,
        )
        return success_response(data={
            "sessions": sessions,
            "total": len(sessions),
        })
    except Exception as e:
        logger.error(f"[TestingAPI] 获取会话列表失败: {e}")
        return error_response(message=f"获取会话列表失败: {str(e)}")


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: Session = Depends(get_db),
):
    """获取测试会话详情"""
    try:
        session = await testing_service.get_testing_session(db, session_id)
        if not session:
            return error_response(message="会话不存在", code=404)
        
        return success_response(data={
            "id": session.id,
            "title": session.title,
            "project_name": session.project_name,
            "requirement_id": session.requirement_id,
            "status": session.status,
            "current_phase": session.current_phase,
            "thread_id_analysis": session.thread_id_analysis,
            "thread_id_plan": session.thread_id_plan,
            "thread_id_generate": session.thread_id_generate,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        })
    except Exception as e:
        logger.error(f"[TestingAPI] 获取会话详情失败: {e}")
        return error_response(message=f"获取会话详情失败: {str(e)}")


@router.get("/sessions/{session_id}/results")
async def get_session_results(
    session_id: str,
    db: Session = Depends(get_db),
):
    """获取测试结果
    
    返回所有阶段的摘要内容（需求分析、测试方案、测试用例）。
    """
    try:
        results = await testing_service.get_testing_results(db, session_id)
        return success_response(data=results)
    except Exception as e:
        logger.error(f"[TestingAPI] 获取测试结果失败: {e}")
        return error_response(message=f"获取测试结果失败: {str(e)}")

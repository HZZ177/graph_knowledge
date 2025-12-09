"""智能测试助手 API

提供测试用例生成相关的 REST API 和 WebSocket 端点。
"""

import json
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
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


# ============================================================
# WebSocket 端点
# ============================================================

@router.websocket("/generate")
async def testing_generate(
    websocket: WebSocket,
    db: Session = Depends(get_db),
):
    """测试用例生成 WebSocket 端点
    
    客户端连接后发送配置消息，服务端执行三阶段工作流并流式推送进度。
    
    客户端消息格式：
    {
        "session_id": "xxx",
        "requirement_id": "12345",
        "project_name": "yongcepingtaipro2.0"
    }
    
    服务端消息类型：
    - start: 工作流开始
    - stream: LLM 流式输出
    - tool_start: 工具调用开始
    - tool_end: 工具调用结束
    - phase_changed: 阶段切换
    - result: 工作流完成
    - error: 错误
    """
    await websocket.accept()
    logger.info("[TestingAPI] WebSocket 连接已建立")
    
    try:
        # 接收初始配置
        config_text = await websocket.receive_text()
        config = json.loads(config_text)
        
        session_id = config.get("session_id")
        requirement_id = config.get("requirement_id")
        project_name = config.get("project_name")
        requirement_name = config.get("requirement_name", "")  # 需求标题
        
        if not all([session_id, requirement_id, project_name]):
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "缺少必要参数: session_id, requirement_id, project_name",
            }, ensure_ascii=False))
            await websocket.close()
            return
        
        logger.info(f"[TestingAPI] 开始生成测试用例: session={session_id}, requirement={requirement_id}, name={requirement_name}")
        
        # 执行工作流
        await testing_service.run_testing_workflow(
            db=db,
            session_id=session_id,
            requirement_id=requirement_id,
            project_name=project_name,
            requirement_name=requirement_name,
            websocket=websocket,
        )
        
    except WebSocketDisconnect:
        logger.info("[TestingAPI] WebSocket 连接断开")
    except json.JSONDecodeError as e:
        logger.error(f"[TestingAPI] JSON 解析失败: {e}")
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"JSON 解析失败: {str(e)}",
            }, ensure_ascii=False))
        except:
            pass
    except Exception as e:
        logger.error(f"[TestingAPI] WebSocket 错误: {e}")
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": str(e),
            }, ensure_ascii=False))
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass

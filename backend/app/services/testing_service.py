"""需求分析测试助手服务 - 查询函数

保留测试会话的查询功能，工作流执行已移至 testing_orchestrator.py。

重构说明：
- create_testing_session, run_testing_orchestrator: 移至 testing_orchestrator.py
- 本文件只保留查询和结果获取函数
"""

import json
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from backend.app.models.chat import Conversation, TestSessionAnalysis
from backend.app.core.logger import logger


async def get_testing_session(db: Session, session_id: str) -> Optional[Conversation]:
    """获取测试会话"""
    return db.query(Conversation).filter(
        Conversation.id == session_id,
        Conversation.agent_type == "intelligent_testing"
    ).first()


async def list_testing_sessions(
    db: Session,
    limit: int = 20,
    offset: int = 0,
) -> list:
    """获取测试会话列表"""
    sessions = db.query(Conversation).filter(
        Conversation.agent_type == "intelligent_testing"
    ).order_by(
        Conversation.updated_at.desc()
    ).offset(offset).limit(limit).all()
    
    return [
        {
            "id": s.id,
            "title": s.title,
            "project_name": s.project_name,
            "requirement_id": s.requirement_id,
            "status": s.status,
            "current_phase": s.current_phase,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in sessions
    ]


async def get_testing_results(db: Session, session_id: str) -> Dict[str, Any]:
    """获取测试结果
    
    返回所有阶段的摘要内容。
    """
    results = {
        "session_id": session_id,
        "requirement_summary": None,
        "test_plan": None,
        "test_cases": None,
    }
    
    records = db.query(TestSessionAnalysis).filter(
        TestSessionAnalysis.session_id == session_id
    ).all()
    
    for record in records:
        try:
            content = json.loads(record.content)
            results[record.analysis_type] = content
        except json.JSONDecodeError:
            results[record.analysis_type] = record.content
    
    return results


__all__ = [
    "get_testing_session",
    "list_testing_sessions",
    "get_testing_results",
]

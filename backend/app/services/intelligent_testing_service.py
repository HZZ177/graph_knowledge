"""需求分析测试助手服务

复用 chat_service 的流式执行核心，管理三阶段工作流：
1. 需求分析（analysis）
2. 方案生成（plan）
3. 用例生成（generate）

关键设计：
- 阶段切换由编排器控制，不依赖 AI 调用 transition_phase 工具
- 每个阶段复用 stream_agent_with_events 核心函数
- 阶段间通过数据库摘要传递信息
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.models.chat import Conversation, TestSessionAnalysis
from backend.app.core.logger import logger


# ============================================================
# 阶段配置
# ============================================================

PHASE_CONFIG = {
    "analysis": {
        "name": "需求分析",
        "next_phase": "plan",
        "summary_type": "requirement_summary",
    },
    "plan": {
        "name": "方案生成",
        "next_phase": "generate",
        "summary_type": "test_plan",
    },
    "generate": {
        "name": "用例生成",
        "next_phase": "completed",
        "summary_type": "test_cases",
    },
}


# ============================================================
# 工具集获取
# ============================================================

def get_phase_tools(phase: str) -> List:
    """获取指定阶段的工具集"""
    from backend.app.llm.langchain.tools.testing import (
        create_task_board,
        update_task_status,
        save_phase_summary,
        get_phase_summary,
        get_coding_issue_detail,
    )
    from backend.app.llm.langchain.tools import get_all_chat_tools
    
    # 基础工具（所有阶段都有）
    base_tools = [
        create_task_board,
        update_task_status,
        save_phase_summary,
        get_phase_summary,
    ]
    
    if phase == "analysis":
        # 阶段1：需求分析，需要代码搜索和知识图谱工具
        return base_tools + [get_coding_issue_detail] + get_all_chat_tools()
    elif phase == "plan":
        # 阶段2：方案生成，只需要基础工具
        return base_tools
    elif phase == "generate":
        # 阶段3：用例生成，只需要基础工具
        return base_tools
    else:
        return base_tools


# ============================================================
# 数据库操作
# ============================================================

async def get_phase_summary_from_db(session_id: str, analysis_type: str) -> str:
    """从数据库读取阶段摘要（异步版本）"""
    from backend.app.db.sqlite import SessionLocal
    
    db = SessionLocal()
    try:
        record = db.query(TestSessionAnalysis).filter(
            TestSessionAnalysis.session_id == session_id,
            TestSessionAnalysis.analysis_type == analysis_type
        ).first()
        return record.content if record else ""
    finally:
        db.close()


def get_phase_summary_sync(session_id: str, analysis_type: str) -> str:
    """从数据库读取阶段摘要（同步版本，供 configs.py 调用）"""
    from backend.app.db.sqlite import SessionLocal
    
    db = SessionLocal()
    try:
        record = db.query(TestSessionAnalysis).filter(
            TestSessionAnalysis.session_id == session_id,
            TestSessionAnalysis.analysis_type == analysis_type
        ).first()
        
        result = record.content if record else ""
        logger.info(f"[Testing] get_phase_summary_sync: session_id={session_id}, type={analysis_type}, found={bool(record)}, content_len={len(result)}")
        
        # 如果找不到，列出该 session 所有的摘要
        if not record:
            all_records = db.query(TestSessionAnalysis).filter(
                TestSessionAnalysis.session_id == session_id
            ).all()
            logger.warning(f"[Testing] 未找到摘要，该 session 已有的摘要类型: {[r.analysis_type for r in all_records]}")
        
        return result
    finally:
        db.close()


async def update_session_status(
    db: Session,
    session_id: str,
    status: str,
    current_phase: Optional[str] = None,
    phase_thread_id: Optional[str] = None,
):
    """更新会话状态
    
    Args:
        db: 数据库会话
        session_id: 会话 ID
        status: 状态
        current_phase: 当前阶段
        phase_thread_id: 阶段对应的 thread_id（用于历史恢复）
    """
    conv = db.query(Conversation).filter(
        Conversation.id == session_id,
        Conversation.agent_type == "intelligent_testing"
    ).first()
    if conv:
        conv.status = status
        if current_phase:
            conv.current_phase = current_phase
            # 保存阶段对应的 thread_id
            if phase_thread_id:
                if current_phase == "analysis":
                    conv.thread_id_analysis = phase_thread_id
                elif current_phase == "plan":
                    conv.thread_id_plan = phase_thread_id
                elif current_phase == "generate":
                    conv.thread_id_generate = phase_thread_id
        conv.updated_at = datetime.now(timezone.utc)
        db.commit()


async def create_testing_session(
    db: Session,
    project_name: str,
    requirement_id: str,
    requirement_name: str,
    session_id: Optional[str] = None,
) -> str:
    """创建测试会话
    
    Args:
        db: 数据库会话
        project_name: Coding 项目名称
        requirement_id: 需求 ID
        requirement_name: 需求名称
        session_id: 可选，指定会话 ID；为空则自动生成
        
    Returns:
        session_id: 新创建的会话 ID
    """
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # 创建 Conversation 记录
    conv = Conversation(
        id=session_id,
        title=f"需求#{requirement_id} {requirement_name[:30]}",
        agent_type="intelligent_testing",
        project_name=project_name,
        requirement_id=requirement_id,
        requirement_name=requirement_name,  # 保存需求标题
        status="pending",
        current_phase="analysis",
    )
    db.add(conv)
    db.commit()
    
    logger.info(f"[IntelligentTesting] 创建测试会话: session={session_id}, requirement={requirement_id}")
    return session_id

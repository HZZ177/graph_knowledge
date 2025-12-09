"""智能测试助手服务

提供测试用例生成的核心业务逻辑：
- 创建测试会话
- 执行三阶段工作流
- WebSocket 流式输出
"""

import json
import uuid
import time
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from starlette.websockets import WebSocket

from backend.app.models.chat import Conversation, TestSessionAnalysis
from backend.app.llm.langchain.testing_graph import (
    create_testing_graph,
    get_initial_state,
    TestingState,
)
from backend.app.core.logger import logger


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
        status="pending",
        current_phase="analysis",
        thread_id_analysis=str(uuid.uuid4()),
        thread_id_plan=str(uuid.uuid4()),
        thread_id_generate=str(uuid.uuid4()),
    )
    db.add(conv)
    db.commit()
    
    logger.info(f"[TestingService] 创建测试会话: session={session_id}, requirement={requirement_id}")
    return session_id


async def get_testing_session(db: Session, session_id: str) -> Optional[Conversation]:
    """获取测试会话"""
    return db.query(Conversation).filter(
        Conversation.id == session_id,
        Conversation.agent_type == "intelligent_testing"
    ).first()


async def update_session_status(
    db: Session,
    session_id: str,
    status: str,
    current_phase: Optional[str] = None,
):
    """更新会话状态"""
    conv = await get_testing_session(db, session_id)
    if conv:
        conv.status = status
        if current_phase:
            conv.current_phase = current_phase
        conv.updated_at = datetime.now(timezone.utc)
        db.commit()


async def run_testing_workflow(
    db: Session,
    session_id: str,
    requirement_id: str,
    project_name: str,
    requirement_name: str,
    websocket: WebSocket,
):
    """执行测试助手工作流
    
    使用 LangGraph 状态机执行三阶段工作流，并通过 WebSocket 实时推送进度。
    
    Args:
        db: 数据库会话
        session_id: 测试会话 ID
        requirement_id: 需求 ID
        project_name: 项目名称
        requirement_name: 需求标题
        websocket: WebSocket 连接
    """
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    
    request_id = str(uuid.uuid4())
    logger.info(f"[TestingService] 开始工作流: session={session_id}, requirement={requirement_id}")
    
    # 更新状态为进行中
    await update_session_status(db, session_id, "analysis", "analysis")
    
    # 发送开始消息
    await websocket.send_text(json.dumps({
        "type": "start",
        "request_id": request_id,
        "session_id": session_id,
    }, ensure_ascii=False))
    
    try:
        # 创建 checkpointer
        async with AsyncSqliteSaver.from_conn_string("llm_checkpoints.db") as checkpointer:
            # 创建状态图
            graph = create_testing_graph(checkpointer=checkpointer)
            
            # 初始状态
            initial_state = get_initial_state(
                session_id=session_id,
                requirement_id=requirement_id,
                project_name=project_name,
                requirement_name=requirement_name,
            )
            
            config = {
                "configurable": {"thread_id": session_id},
                "recursion_limit": 150,
            }
            
            # 用于追踪工具调用
            tool_placeholder_id = 0
            tool_batch_id = 0
            tool_call_to_placeholder: Dict[str, Dict[str, Any]] = {}
            current_phase = "analysis"
            
            # 使用 astream_events 流式执行
            async for event in graph.astream_events(initial_state, config, version="v2"):
                event_type = event.get("event")
                event_name = event.get("name", "")
                
                # ===== LLM 流式输出事件 =====
                if event_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        await websocket.send_text(json.dumps({
                            "type": "stream",
                            "content": chunk.content,
                        }, ensure_ascii=False))
                
                # ===== LLM 结束事件（可能包含工具调用）=====
                elif event_type == "on_chat_model_end":
                    output = event.get("data", {}).get("output")
                    tool_calls = getattr(output, "tool_calls", []) if output else []
                    
                    if tool_calls:
                        tool_batch_id += 1
                        batch_size = len(tool_calls)
                        
                        for idx, tc in enumerate(tool_calls):
                            tool_name = tc.get("name", "unknown")
                            tool_call_id = tc.get("id", "")
                            tool_args = tc.get("args", {})
                            tool_placeholder_id += 1
                            
                            # 记录映射
                            tool_call_to_placeholder[tool_call_id] = {
                                "placeholder_id": tool_placeholder_id,
                                "tool_name": tool_name,
                                "tool_args": tool_args,
                                "start_time": time.time(),
                                "batch_id": tool_batch_id,
                                "batch_size": batch_size,
                                "batch_index": idx,
                            }
                            
                            # 发送工具占位符（用于前端渲染工具卡片）
                            placeholder = f"<!--TOOL:{tool_name}:{tool_placeholder_id}-->"
                            await websocket.send_text(json.dumps({
                                "type": "stream",
                                "content": placeholder,
                            }, ensure_ascii=False))
                            
                            # 发送 tool_start
                            await websocket.send_text(json.dumps({
                                "type": "tool_start",
                                "tool_name": tool_name,
                                "tool_id": tool_placeholder_id,
                                "tool_input": tool_args,
                                "batch_id": tool_batch_id,
                                "batch_size": batch_size,
                                "batch_index": idx,
                            }, ensure_ascii=False))
                
                # ===== 工具开始事件 =====
                elif event_type == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_input = event.get("data", {}).get("input", {})
                    run_id = event.get("run_id", "")
                    
                    tool_call_to_placeholder[f"run_{run_id}"] = {
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "start_time": time.time(),
                    }
                
                # ===== 工具结束事件 =====
                elif event_type == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    tool_output = event.get("data", {}).get("output", "")
                    run_id = event.get("run_id", "")
                    
                    # 获取运行时信息
                    run_info = tool_call_to_placeholder.pop(f"run_{run_id}", {})
                    tool_input = run_info.get("tool_input", {})
                    start_time = run_info.get("start_time", time.time())
                    elapsed = time.time() - start_time
                    
                    # 查找 placeholder 信息
                    placeholder_id = None
                    batch_id = None
                    batch_size = 1
                    batch_index = 0
                    
                    for tc_id, info in list(tool_call_to_placeholder.items()):
                        if not tc_id.startswith("run_") and info.get("tool_name") == tool_name:
                            placeholder_id = info.get("placeholder_id")
                            batch_id = info.get("batch_id")
                            batch_size = info.get("batch_size", 1)
                            batch_index = info.get("batch_index", 0)
                            del tool_call_to_placeholder[tc_id]
                            break
                    
                    # 生成摘要
                    input_summary, output_summary = _generate_tool_summaries(
                        tool_name, tool_input, str(tool_output)
                    )
                    
                    await websocket.send_text(json.dumps({
                        "type": "tool_end",
                        "tool_name": tool_name,
                        "tool_id": placeholder_id,
                        "input_summary": input_summary,
                        "output_summary": output_summary,
                        "elapsed": round(elapsed, 2),
                        "batch_id": batch_id,
                        "batch_size": batch_size,
                        "batch_index": batch_index,
                    }, ensure_ascii=False))
                    
                    # 检测阶段切换
                    if tool_name == "transition_phase":
                        try:
                            to_phase = tool_input.get("to_phase", "")
                            if to_phase:
                                current_phase = to_phase
                                await update_session_status(db, session_id, to_phase, to_phase)
                                await websocket.send_text(json.dumps({
                                    "type": "phase_changed",
                                    "phase": to_phase,
                                }, ensure_ascii=False))
                        except Exception as e:
                            logger.warning(f"[TestingService] 阶段切换处理失败: {e}")
                
                # ===== 节点结束事件（检测阶段切换）=====
                elif event_type == "on_chain_end":
                    output = event.get("data", {}).get("output", {})
                    if isinstance(output, dict) and "current_phase" in output:
                        new_phase = output["current_phase"]
                        if new_phase != current_phase:
                            current_phase = new_phase
                            await update_session_status(db, session_id, new_phase, new_phase)
                            await websocket.send_text(json.dumps({
                                "type": "phase_changed",
                                "phase": new_phase,
                            }, ensure_ascii=False))
        
        # 更新最终状态
        await update_session_status(db, session_id, "completed", "completed")
        
        # 发送完成消息
        await websocket.send_text(json.dumps({
            "type": "result",
            "request_id": request_id,
            "session_id": session_id,
            "status": "completed",
        }, ensure_ascii=False))
        
        logger.info(f"[TestingService] 工作流完成: session={session_id}")
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"[TestingService] 工作流失败: {e}\n{error_traceback}")
        
        # 更新状态为失败
        await update_session_status(db, session_id, "failed")
        
        await websocket.send_text(json.dumps({
            "type": "error",
            "request_id": request_id,
            "session_id": session_id,
            "error": str(e),
        }, ensure_ascii=False))


def _generate_tool_summaries(tool_name: str, tool_input: dict, tool_output: str) -> tuple:
    """生成工具摘要
    
    针对测试助手的特定工具生成友好的摘要信息。
    """
    input_summary = ""
    output_summary = ""
    
    # 任务看板工具
    if tool_name == "create_task_board":
        phase = tool_input.get("phase", "")
        tasks = tool_input.get("tasks", [])
        input_summary = f"阶段: {phase}"
        output_summary = f"创建 {len(tasks)} 个任务"
    
    elif tool_name == "update_task_status":
        task_id = tool_input.get("task_id", "")
        status = tool_input.get("status", "")
        input_summary = f"任务: {task_id}"
        output_summary = f"状态: {status}"
    
    elif tool_name == "transition_phase":
        from_phase = tool_input.get("from_phase", "")
        to_phase = tool_input.get("to_phase", "")
        input_summary = f"{from_phase} → {to_phase}"
        output_summary = "阶段切换完成"
    
    elif tool_name == "save_phase_summary":
        analysis_type = tool_input.get("analysis_type", "")
        input_summary = f"类型: {analysis_type}"
        output_summary = "摘要已保存"
    
    elif tool_name == "get_phase_summary":
        analysis_type = tool_input.get("analysis_type", "")
        input_summary = f"类型: {analysis_type}"
        if tool_output:
            output_summary = f"读取成功 ({len(tool_output)} 字符)"
        else:
            output_summary = "无数据"
    
    elif tool_name == "get_coding_issue_detail":
        project = tool_input.get("project_name", "")
        code = tool_input.get("issue_code", "")
        input_summary = f"需求: {project}#{code}"
        try:
            data = json.loads(tool_output)
            if "name" in data:
                output_summary = f"获取成功: {data['name'][:30]}"
            elif "error" in data:
                output_summary = f"获取失败"
        except:
            output_summary = "执行完成"
    
    # 默认处理
    if not input_summary and tool_input:
        first_key = next(iter(tool_input.keys()), None)
        if first_key:
            first_val = str(tool_input[first_key])
            input_summary = f"{first_key}: {first_val[:30]}"
    
    if not output_summary:
        output_summary = "执行完成"
    
    return input_summary, output_summary


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

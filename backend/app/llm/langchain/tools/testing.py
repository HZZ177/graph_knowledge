"""需求分析测试助手工具集

提供测试助手专用的工具函数：
- 任务管理工具（create_task_board, update_task_status）
- 摘要管理工具（save_phase_summary, get_phase_summary）
- Coding 查询工具（get_coding_issue_detail）
"""

import json
import uuid
from typing import List, Optional
from datetime import datetime, timezone

from langchain_core.tools import tool

from backend.app.core.logger import logger


# ============================================================
# 任务管理工具（前端通过 tool_start/tool_end 事件监听）
# ============================================================

@tool
def create_task_board(session_id: str, phase: str, tasks: List[dict]) -> str:
    """创建任务看板
    
    当开始一个新阶段时，调用此工具创建该阶段的任务列表。
    前端会监听此工具的 tool_start 事件，从 tool_input 中获取任务列表并展示。
    任务会被持久化到数据库，支持历史恢复。
    
    **重要**：session_id 必须完整复制，不能截断！格式为 UUID（36字符）。
    
    Args:
        session_id: 测试会话 ID（必须是完整的 UUID，36字符）
        phase: 当前阶段 (analysis/plan/generate)
        tasks: 任务列表，每个任务包含:
            - title: 任务标题 (如 "解析需求文档")
            - scope: 任务范围 (可选，如 "requirement", "business", "code")
    
    Returns:
        确认消息，包含生成的任务 ID 映射
    
    Example:
        create_task_board(
            session_id="571c124c-953f-43dd-a4c7-64eb578c7176",  # 完整36字符UUID
            phase="analysis",
            tasks=[
                {"title": "解析需求文档", "scope": "requirement"},
                {"title": "分析业务流程", "scope": "business"},
                {"title": "代码逻辑分析", "scope": "code"}
            ]
        )
    """
    from backend.app.db.sqlite import SessionLocal
    from backend.app.models.chat import TestSessionTask
    
    # 验证 session_id 格式
    try:
        uuid.UUID(session_id)
    except ValueError:
        error_msg = f"错误：session_id 格式不正确！你传递的是 '{session_id}'（{len(session_id)}字符），但有效的 UUID 应该是36字符。请使用完整的会话ID重新调用此工具。"
        logger.error(f"[Testing] {error_msg}")
        return error_msg
    
    # 为每个任务生成唯一 ID
    task_id_map = {}
    for i, task in enumerate(tasks):
        if 'id' not in task or not task['id']:
            task['id'] = f"{phase}_{str(uuid.uuid4())[:8]}"
        task_id_map[task['title']] = task['id']
    
    logger.info(f"[Testing] 创建任务看板: session={session_id}, phase={phase}, tasks={len(tasks)}, ids={list(task_id_map.values())}")
    
    # 入库任务
    db = SessionLocal()
    try:
        # 先删除该阶段的旧任务（支持重新生成）
        db.query(TestSessionTask).filter(
            TestSessionTask.session_id == session_id,
            TestSessionTask.phase == phase
        ).delete(synchronize_session=False)
        
        # 插入新任务
        for i, task in enumerate(tasks):
            db_task = TestSessionTask(
                id=task['id'],
                session_id=session_id,
                phase=phase,
                title=task.get('title', ''),
                scope=task.get('scope'),
                status='pending',
                progress=0,
                sort_order=i,
            )
            db.add(db_task)
        
        db.commit()
        logger.info(f"[Testing] 任务入库成功: session={session_id}, phase={phase}, count={len(tasks)}")
    except Exception as e:
        db.rollback()
        logger.error(f"[Testing] 任务入库失败: {e}")
    finally:
        db.close()
    
    # 返回任务 ID 映射，方便 AI 后续更新任务状态
    id_list = [f"- {title}: {tid}" for title, tid in task_id_map.items()]
    return f"任务看板已创建，阶段: {phase}，共 {len(tasks)} 个任务。\n任务ID映射（更新状态时使用）:\n" + "\n".join(id_list)


@tool
def update_task_status(
    completed_task_id: str = "", 
    started_task_id: str = "",
    result: str = ""
) -> str:
    """更新任务状态（支持同时完成一个任务并开始另一个任务）
    
    可以在一次调用中同时：
    1. 将某个任务标记为已完成
    2. 将另一个任务标记为进行中
    
    这样可以减少工具调用次数。两个参数都是可选的。
    
    Args:
        completed_task_id: 刚完成的任务ID（可为空）
        started_task_id: 开始执行的任务ID（可为空）
        result: 完成任务的结果摘要
    
    Returns:
        确认消息
    
    Example:
        # 任务ID由 create_task_board 返回，格式为 {phase}_{uuid[:8]}
        # 例如: analysis_abc12345, plan_def67890
        
        # 开始第一个任务
        update_task_status(started_task_id="analysis_abc12345")
        
        # 完成任务1，开始任务2
        update_task_status(completed_task_id="analysis_abc12345", started_task_id="analysis_def67890", result="提取5个功能点")
        
        # 完成最后一个任务
        update_task_status(completed_task_id="analysis_ghi11111", result="完成代码分析")
    """
    from backend.app.db.sqlite import SessionLocal
    from backend.app.models.chat import TestSessionTask
    
    logger.info(f"[Testing] 更新任务状态: completed={completed_task_id}, started={started_task_id}")
    
    messages = []
    
    db = SessionLocal()
    try:
        # 更新完成的任务
        if completed_task_id:
            task = db.query(TestSessionTask).filter(TestSessionTask.id == completed_task_id).first()
            if task:
                task.status = "completed"
                task.progress = 100
                if result:
                    task.result = result
                task.updated_at = datetime.now(timezone.utc)
                messages.append(f"任务 {completed_task_id} 已完成")
                logger.info(f"[Testing] 任务完成: {completed_task_id}")
            else:
                logger.warning(f"[Testing] 任务不存在: {completed_task_id}")
        
        # 更新开始的任务
        if started_task_id:
            task = db.query(TestSessionTask).filter(TestSessionTask.id == started_task_id).first()
            if task:
                task.status = "in_progress"
                task.progress = 0
                task.updated_at = datetime.now(timezone.utc)
                messages.append(f"任务 {started_task_id} 已开始")
                logger.info(f"[Testing] 任务开始: {started_task_id}")
            else:
                logger.warning(f"[Testing] 任务不存在: {started_task_id}")
        
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[Testing] 任务状态更新失败: {e}")
        return f"更新失败: {str(e)}"
    finally:
        db.close()
    
    return "; ".join(messages) if messages else "无更新"


# NOTE: transition_phase 工具已删除
# 阶段切换现在由 testing_orchestrator.py 编排器控制
# 前端阶段切换依赖 WebSocket 的 phase_changed 消息，编排器会自动发送


# ============================================================
# 摘要管理工具
# ============================================================

@tool
def save_phase_summary(
    session_id: str, 
    analysis_type: str, 
    content: str
) -> str:
    """保存阶段摘要到数据库
    
    每个阶段结束时，调用此工具将关键信息压缩成结构化摘要存入数据库。
    下个阶段开始时会读取此摘要，避免传递全量历史消息导致 Token 爆炸。
    
    **重要**：session_id 必须完整复制，不能截断！格式为 UUID（36字符）。
    
    Args:
        session_id: 测试会话 ID（必须是完整的 UUID，36字符，如 "571c124c-953f-43dd-a4c7-64eb578c7176"）
        analysis_type: 摘要类型，可选值:
            - requirement_summary: 需求分析摘要（阶段1输出）
            - test_plan: 测试方案（阶段2输出）
            - test_cases: 测试用例集（阶段3输出）
        content: JSON 格式的摘要内容
    
    Returns:
        确认消息
    
    Example:
        save_phase_summary(
            session_id="571c124c-953f-43dd-a4c7-64eb578c7176",  # 完整36字符UUID
            analysis_type="requirement_summary",
            content=json.dumps({
                "requirement": {"id": "12345", "title": "月卡开通功能"},
                "business_flow": [...],
                "code_logic": {...},
                "test_focus": {...}
            }, ensure_ascii=False)
        )
    """
    from backend.app.db.sqlite import SessionLocal
    from backend.app.models.chat import TestSessionAnalysis
    
    # 验证 session_id 格式
    try:
        uuid.UUID(session_id)
    except ValueError:
        error_msg = f"错误：session_id 格式不正确！你传递的是 '{session_id}'（{len(session_id)}字符），但有效的 UUID 应该是36字符。请检查并使用完整的会话ID重新调用此工具。"
        logger.error(f"[Testing] {error_msg}")
        return error_msg
    
    # 确定阶段
    phase_map = {
        "requirement_summary": "analysis",
        "test_plan": "plan",
        "test_cases": "generate",
    }
    phase = phase_map.get(analysis_type, "unknown")
    
    db = SessionLocal()
    try:
        # 检查是否已存在
        existing = db.query(TestSessionAnalysis).filter(
            TestSessionAnalysis.session_id == session_id,
            TestSessionAnalysis.analysis_type == analysis_type
        ).first()
        
        if existing:
            # 更新
            existing.content = content
            existing.updated_at = datetime.now(timezone.utc)
            logger.info(f"[Testing] 更新摘要: session={session_id}, type={analysis_type}")
        else:
            # 新建
            record = TestSessionAnalysis(
                id=str(uuid.uuid4()),
                session_id=session_id,
                phase=phase,
                analysis_type=analysis_type,
                content=content,
            )
            db.add(record)
            logger.info(f"[Testing] 保存摘要: session={session_id}, type={analysis_type}")
        
        db.commit()
        return f"摘要已保存: {analysis_type}"
    except Exception as e:
        db.rollback()
        logger.error(f"[Testing] 保存摘要失败: {e}")
        return f"保存摘要失败: {str(e)}"
    finally:
        db.close()


@tool
def get_phase_summary(session_id: str, analysis_type: str) -> str:
    """获取阶段摘要
    
    从数据库读取上阶段保存的摘要，用于注入到当前阶段的 Context。
    
    Args:
        session_id: 测试会话 ID
        analysis_type: 摘要类型 (requirement_summary/test_plan/test_cases)
    
    Returns:
        JSON 格式的摘要内容，如果不存在返回空字符串
    """
    from backend.app.db.sqlite import SessionLocal
    from backend.app.models.chat import TestSessionAnalysis
    
    db = SessionLocal()
    try:
        record = db.query(TestSessionAnalysis).filter(
            TestSessionAnalysis.session_id == session_id,
            TestSessionAnalysis.analysis_type == analysis_type
        ).first()
        
        if record:
            logger.info(f"[Testing] 读取摘要: session={session_id}, type={analysis_type}, len={len(record.content)}")
            return record.content
        else:
            logger.warning(f"[Testing] 摘要不存在: session={session_id}, type={analysis_type}")
            return ""
    finally:
        db.close()


# ============================================================
# Coding 查询工具
# ============================================================

@tool
def get_coding_issue_detail(project_name: str, issue_code: int) -> str:
    """获取 Coding 需求详情（结构化格式，保留图片位置）
    
    从 Coding 平台获取需求详情，解析为结构化数据，保持文本和图片的位置关系。
    图片使用真实 URL，避免 Token 爆炸。
    
    Args:
        project_name: Coding 项目名称
        issue_code: 需求编号
    
    Returns:
        JSON 格式的结构化需求详情，包含:
            - name: 需求名称
            - code: 需求编号
            - content_blocks: 内容块数组，按原始顺序保持文本和图片的位置关系
              - type: "text" 或 "image"
              - content: 文本内容（text）或 图片 URL（image）
              - alt: 图片描述（仅 image 类型）
              - index: 图片序号（仅 image 类型，从 1 开始）
    """
    import asyncio
    import re
    from backend.app.services.coding_service import coding_service
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # 获取需求详情
            issue = loop.run_until_complete(
                coding_service.get_issue_detail(project_name, issue_code)
            )
            
            # 获取图片 URL 并替换
            file_urls = loop.run_until_complete(
                coding_service.get_issue_file_urls(project_name, issue_code)
            )
            
            # 替换图片地址为真实 URL
            description = coding_service._replace_images_with_urls(
                issue.description, file_urls
            )
            
            # 解析 Markdown，提取文本和图片，保持顺序
            content_blocks = []
            lines = description.split('\n')
            text_buffer = []
            image_index = 0
            
            for line in lines:
                # 检查是否是图片行
                img_match = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', line.strip())
                if img_match:
                    # 先保存之前累积的文本
                    if text_buffer:
                        content_blocks.append({
                            "type": "text",
                            "content": '\n'.join(text_buffer)
                        })
                        text_buffer = []
                    
                    # 保存图片信息（使用 URL，不转 base64）
                    alt_text = img_match.group(1)
                    img_url = img_match.group(2)
                    image_index += 1
                    
                    content_blocks.append({
                        "type": "image",
                        "url": img_url,
                        "alt": alt_text or f"需求图片{image_index}",
                        "index": image_index
                    })
                else:
                    text_buffer.append(line)
            
            # 保存最后的文本
            if text_buffer:
                content_blocks.append({
                    "type": "text",
                    "content": '\n'.join(text_buffer)
                })
            
            result = {
                "name": issue.name,
                "code": issue.code,
                "content_blocks": content_blocks,
                "total_images": image_index,
                "total_text_blocks": len([b for b in content_blocks if b["type"] == "text"]),
            }
            
            logger.info(f"[Testing] 获取结构化需求: {project_name}#{issue_code} - {issue.name}, "
                       f"图片={result['total_images']}, 文本块={result['total_text_blocks']}")
            return json.dumps(result, ensure_ascii=False)
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"[Testing] 获取结构化需求失败: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============================================================
# 工具集导出
# ============================================================

def get_testing_tools_phase1():
    """获取阶段1（需求分析）的工具集
    
    包含全量工具：任务管理 + 摘要管理 + Coding查询 + 代码搜索 + 知识图谱
    """
    from backend.app.llm.langchain.tools import get_all_chat_tools
    
    # 基础知识库工具（代码搜索、知识图谱等）
    base_tools = get_all_chat_tools()
    
    # 测试专用工具（不再包含 transition_phase，阶段切换由编排器控制）
    testing_tools = [
        create_task_board,
        update_task_status,
        save_phase_summary,
        get_phase_summary,
        get_coding_issue_detail,
    ]
    
    return testing_tools + base_tools


def get_testing_tools_phase2():
    """获取阶段2（方案生成）的工具集
    
    精简工具：任务管理 + 摘要管理（不需要代码搜索）
    """
    return [
        create_task_board,
        update_task_status,
        save_phase_summary,
        get_phase_summary,
    ]


def get_testing_tools_phase3():
    """获取阶段3（用例生成）的工具集
    
    精简工具：任务管理 + 摘要管理
    """
    return [
        create_task_board,
        update_task_status,
        save_phase_summary,
        get_phase_summary,
    ]


def get_all_testing_tools():
    """获取所有测试工具（用于 Agent 配置）"""
    return get_testing_tools_phase1()

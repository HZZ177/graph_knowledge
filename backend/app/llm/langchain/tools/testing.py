"""智能测试助手工具集

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
def create_task_board(phase: str, tasks: List[dict]) -> str:
    """创建任务看板
    
    当开始一个新阶段时，调用此工具创建该阶段的任务列表。
    前端会监听此工具的 tool_start 事件，从 tool_input 中获取任务列表并展示。
    
    Args:
        phase: 当前阶段 (analysis/plan/generate)
        tasks: 任务列表，每个任务包含:
            - id: 任务唯一标识 (如 "task_1")
            - title: 任务标题 (如 "解析需求文档")
            - scope: 任务范围 (如 "requirement", "business", "code")
    
    Returns:
        确认消息
    
    Example:
        create_task_board(
            phase="analysis",
            tasks=[
                {"id": "task_1", "title": "解析需求文档", "scope": "requirement"},
                {"id": "task_2", "title": "分析业务流程: 月卡开通", "scope": "business"},
                {"id": "task_3", "title": "代码逻辑分析: MonthCardService", "scope": "code"}
            ]
        )
    """
    logger.info(f"[Testing] 创建任务看板: phase={phase}, tasks={len(tasks)}")
    return f"任务看板已创建，阶段: {phase}，共 {len(tasks)} 个任务"


@tool
def update_task_status(
    task_id: str, 
    status: str, 
    progress: int = 0, 
    result: str = ""
) -> str:
    """更新任务状态
    
    更新指定任务的执行状态。前端会监听此工具的事件，更新对应任务的 UI 状态。
    
    Args:
        task_id: 任务ID (如 "task_1")
        status: 任务状态，可选值:
            - in_progress: 进行中
            - completed: 已完成
            - failed: 失败
            - skipped: 跳过
        progress: 进度百分比 (0-100)，仅 in_progress 状态有效
        result: 任务结果摘要，用于展示任务完成后的关键信息
    
    Returns:
        确认消息
    
    Example:
        # 开始任务
        update_task_status(task_id="task_1", status="in_progress", progress=0)
        
        # 更新进度
        update_task_status(task_id="task_1", status="in_progress", progress=50)
        
        # 完成任务
        update_task_status(task_id="task_1", status="completed", result="提取5个功能点")
    """
    logger.info(f"[Testing] 更新任务状态: task_id={task_id}, status={status}, progress={progress}")
    return f"任务 {task_id} 状态已更新为 {status}"


@tool
def transition_phase(
    session_id: str,
    from_phase: str,
    to_phase: str,
    summary: str = ""
) -> str:
    """切换工作流阶段
    
    当一个阶段完成时，调用此工具标记阶段切换。前端会更新时间线 UI。
    
    **重要：切换阶段前必须先调用 save_phase_summary 保存摘要！**
    
    Args:
        session_id: 测试会话 ID
        from_phase: 当前阶段 (analysis/plan/generate)
        to_phase: 目标阶段 (plan/generate/completed)
        summary: 阶段完成摘要
    
    Returns:
        确认消息，或错误消息（如果摘要未保存）
    """
    from backend.app.db.sqlite import SessionLocal
    from backend.app.models.chat import TestSessionAnalysis
    
    # 检查摘要是否已保存
    phase_to_summary_type = {
        "analysis": "requirement_summary",
        "plan": "test_plan",
        "generate": "test_cases",
    }
    
    expected_summary_type = phase_to_summary_type.get(from_phase)
    if expected_summary_type:
        db = SessionLocal()
        try:
            record = db.query(TestSessionAnalysis).filter(
                TestSessionAnalysis.session_id == session_id,
                TestSessionAnalysis.analysis_type == expected_summary_type
            ).first()
            
            if not record or not record.content:
                logger.warning(f"[Testing] 阶段切换被阻止: 摘要未保存! session={session_id}, expected={expected_summary_type}")
                return f"错误：无法切换阶段！请先调用 save_phase_summary 保存 {expected_summary_type} 摘要。session_id={session_id}"
        finally:
            db.close()
    
    logger.info(f"[Testing] 阶段切换: {from_phase} -> {to_phase}, session={session_id}")
    return f"阶段切换完成: {from_phase} -> {to_phase}"


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
    
    Args:
        session_id: 测试会话 ID
        analysis_type: 摘要类型，可选值:
            - requirement_summary: 需求分析摘要（阶段1输出）
            - test_plan: 测试方案（阶段2输出）
            - test_cases: 测试用例集（阶段3输出）
        content: JSON 格式的摘要内容
    
    Returns:
        确认消息
    
    Example:
        save_phase_summary(
            session_id="xxx",
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
    
    # 测试专用工具
    testing_tools = [
        create_task_board,
        update_task_status,
        transition_phase,
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
        transition_phase,
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
        transition_phase,
        save_phase_summary,
        get_phase_summary,
    ]


def get_all_testing_tools():
    """获取所有测试工具（用于 Agent 配置）"""
    return get_testing_tools_phase1()

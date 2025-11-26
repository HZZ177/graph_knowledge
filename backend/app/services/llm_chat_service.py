"""LLM Chat 相关服务

包含：
- 非流式基于流程上下文的问答
- 基于 CrewAI 1.6.0 原生 streaming 的流式问答
"""

import uuid
from typing import Any, Dict, Optional, AsyncGenerator

from sqlalchemy.orm import Session
from crewai import Agent, Task, Crew

from backend.app.llm.base import get_crewai_llm
from backend.app.llm.streaming import StreamMessage, iter_crew_text_stream
from backend.app.services.graph_service import get_business_context
from backend.app.core.logger import logger


def answer_question_with_process_context(
    db: Session,
    question: str,
    process_id: Optional[str] = None,
) -> Dict[str, Any]:
    """基于流程上下文 + CrewAI 进行问答（非流式）。

    返回结构: {"answer": str, "process_id": str | None}
    """

    llm = get_crewai_llm(db)

    context: Dict[str, Any] | None = None
    if process_id is not None:
        try:
            context = get_business_context(process_id)
        except ValueError:
            # 如果流程不存在，直接给出友好提示
            answer = f"当前暂不支持流程 {process_id} 的详细说明。你问了: {question}"
            return {"answer": answer, "process_id": process_id}

    # 将流程上下文压缩成适合 prompt 的字符串
    context_str = "无" if not context else str(context)

    system_prompt = "你是业务流程知识助手，回答问题时参考给定的流程上下文，用清晰的中文回答。"

    analyst = Agent(
        role="Process Analyst",
        goal="根据给定流程上下文，回答用户关于该流程或相关系统/数据资源的问题",
        backstory=system_prompt,
        llm=llm,
    )

    task_description = (
        f"用户问题：{question}\n"
        f"流程上下文：{context_str}\n"
        "请基于以上信息给出结构化、清晰的中文回答，如果上下文不足以回答，请明确说明。"
    )

    qa_task = Task(
        description=task_description,
        agent=analyst,
        expected_output="一段清晰的中文回答，描述流程的关键步骤、涉及系统和数据资源，并回答用户问题。",
    )

    crew = Crew(
        agents=[analyst],
        tasks=[qa_task],
        verbose=False,
    )

    result = crew.kickoff()

    return {
        "answer": str(result),
        "process_id": process_id,
    }


async def streaming_chat_with_context(
    db: Session,
    question: str,
    process_id: Optional[str] = None,
) -> AsyncGenerator[StreamMessage, None]:
    """流式问答，基于流程上下文 + CrewAI 1.6.0 原生 streaming。

    Args:
        db: 数据库会话
        question: 用户问题
        process_id: 流程ID（可选）

    Yields:
        StreamMessage: 流式消息（start / chunk / done / error）
    """

    request_id = str(uuid.uuid4())
    full_response = ""

    # 获取 LLM 实例
    llm = get_crewai_llm(db)

    # 获取流程上下文
    context: Dict[str, object] | None = None
    if process_id is not None:
        try:
            context = get_business_context(process_id)
        except ValueError:
            yield StreamMessage(
                type="error",
                error=f"流程 {process_id} 不存在",
                request_id=request_id,
            )
            return

    context_str = "无" if not context else str(context)

    # 构建 CrewAI 任务
    system_prompt = "你是业务流程知识助手，回答问题时参考给定的流程上下文，用清晰的中文回答。"

    analyst = Agent(
        role="Process Analyst",
        goal="根据给定流程上下文，回答用户关于该流程或相关系统/数据资源的问题",
        backstory=system_prompt,
        llm=llm,
    )

    task_description = (
        f"用户问题：{question}\n"
        f"流程上下文：{context_str}\n"
        "请基于以上信息给出结构化、清晰的中文回答，如果上下文不足以回答，请明确说明。"
    )

    qa_task = Task(
        description=task_description,
        agent=analyst,
        expected_output="一段清晰的中文回答，描述流程的关键步骤、涉及系统和数据资源，并回答用户问题。",
    )

    crew = Crew(
        agents=[analyst],
        tasks=[qa_task],
        verbose=False,
        stream=True,
    )

    # 发送开始消息
    yield StreamMessage(type="start", request_id=request_id)

    try:
        # 迭代 CrewAI 1.6.0 的 streaming 输出
        async for chunk_text in iter_crew_text_stream(crew):
            if not chunk_text:
                continue

            full_response += chunk_text
            yield StreamMessage(
                type="chunk",
                content=chunk_text,
                request_id=request_id,
            )

        # 发送完成消息
        metadata = {
            "full_response": full_response,
            "process_id": process_id,
        }
        yield StreamMessage(
            type="done",
            request_id=request_id,
            metadata=metadata,
        )

        logger.info(f"[StreamingChat] 流式问答完成，响应长度: {len(full_response)}")

    except Exception as e:  # noqa: BLE001
        logger.error(f"[StreamingChat] 流式问答失败: {e}", exc_info=True)
        yield StreamMessage(
            type="error",
            error=str(e),
            request_id=request_id,
        )

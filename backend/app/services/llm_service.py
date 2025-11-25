from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from crewai import Agent, Task, Crew, Process

from backend.app.llm.base import get_crewai_llm
from backend.app.services.graph_service import get_business_context


def answer_question_with_process_context(
    db: Session,
    question: str,
    process_id: Optional[str] = None,
) -> Dict[str, Any]:
    """基于流程上下文 + crewai 进行问答。

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
        verbose=True
    )

    result = crew.kickoff()

    return {
        "answer": str(result),
        "process_id": process_id,
    }

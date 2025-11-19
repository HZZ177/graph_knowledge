from typing import Any, Dict, Optional

from .graph_query_service import get_process_context


def answer_question(question: str, process_id: Optional[str] = None) -> Dict[str, Any]:
    pid = process_id or "c_open_card"
    try:
        context = get_process_context(pid)
    except ValueError:
        answer = f"当前暂不支持流程 {pid} 的详细说明。你问了: {question}"
        return {"answer": answer, "process_id": pid}

    process = context.get("process", {})
    steps = context.get("steps", [])
    step_names = [str(item.get("step", {}).get("name", "")) for item in steps]
    step_names = [name for name in step_names if name]

    if step_names:
        summary = "；".join(step_names)
        prefix = f"这是关于流程「{process.get('name', pid)}」的示例说明。该流程大致包含以下步骤：{summary}。"
    else:
        prefix = f"这是关于流程「{process.get('name', pid)}」的示例说明。"

    answer = f"{prefix} 你问了: {question}"
    return {"answer": answer, "process_id": pid}

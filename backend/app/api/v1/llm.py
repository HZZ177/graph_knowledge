from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from backend.app.db.sqlite import get_db
from backend.app.schemas.llm import ChatRequest, ChatResponse
from backend.app.services.llm_service import answer_question_with_process_context
from backend.app.core.utils import success_response, error_response


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/ask", response_model=ChatResponse, summary="基于流程上下文的 LLM 问答接口")
async def chat(
    req: ChatRequest = Body(...),
    db: Session = Depends(get_db),
) -> dict:
    try:
        result = answer_question_with_process_context(
            db=db,
            question=req.question,
            process_id=req.process_id,
        )
        data = ChatResponse(
            answer=result["answer"],
            process_id=result.get("process_id"),
        )
        return success_response(data=data)
    except Exception as exc:
        return error_response(message=str(exc))

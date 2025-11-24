from __future__ import annotations

import uuid

from fastapi import Request

from backend.app.core.logger import trace_id_var


async def trace_id_middleware(request: Request, call_next):
    """为每个请求管理 traceId，并写入日志上下文和响应头。

    - 优先使用请求头中的 X-Trace-Id
    - 如果没有，则自动生成一个 UUID
    - 将 traceId 写入 loguru 的 ContextVar（trace_id_var）
    - 将 traceId 写入响应头，方便前端和排查问题
    """
    trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex
    token = trace_id_var.set(trace_id)
    try:
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response
    finally:
        trace_id_var.reset(token)

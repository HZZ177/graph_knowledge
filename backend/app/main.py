import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1 import (
    processes,
    llm_chat,
    llm_skeleton,
    graph,
    resource_nodes,
    canvas,
    health,
    llm_models,
)

from backend.app.db.sqlite import Base, engine, SessionLocal
from backend.app.db.init_db import init_db
from backend.app.core.middleware import trace_id_middleware
from backend.app.models import ai_models, conversation  # noqa: F401  确保 ai_models, conversations 表被创建
from backend.mcp.ace_code_engine import warmup_ace_mcp


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan handler: 初始化数据库并预热 AceMCP。"""

    # startup
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        init_db(db)
    finally:
        db.close()

    # 预热 AceCodeEngine MCP 客户端，降低首次调用时的冷启动开销
    warmup_ace_mcp()

    # yield 控制应用的存活周期；目前没有特殊的 shutdown 逻辑
    yield


app = FastAPI(title="Graph Knowledge Backend", lifespan=lifespan)

# 简单 CORS 设置，方便本地前端联调
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(trace_id_middleware)

app.include_router(processes.router, prefix="/api/v1")
app.include_router(llm_chat.router, prefix="/api/v1")
app.include_router(llm_skeleton.router, prefix="/api/v1")
app.include_router(graph.router, prefix="/api/v1")
app.include_router(resource_nodes.router, prefix="/api/v1")
app.include_router(canvas.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")
app.include_router(llm_models.router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        app="main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        access_log=False  # 禁用uvicorn访问日志，避免与自定义中间件重复
    )
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1 import (
    processes,
    llm,
    graph,
    resource_nodes,
    canvas,
    health,
    llm_models,
    skeleton,
)

from backend.app.db.sqlite import Base, engine, SessionLocal
from backend.app.db.init_db import init_db
from backend.app.core.middleware import trace_id_middleware
from backend.app.models import ai_models  # noqa: F401  确保 ai_models 表被创建

app = FastAPI(title="Graph Knowledge Backend")

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
app.include_router(llm.router, prefix="/api/v1")
app.include_router(graph.router, prefix="/api/v1")
app.include_router(resource_nodes.router, prefix="/api/v1")
app.include_router(canvas.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")
app.include_router(llm_models.router, prefix="/api/v1")
app.include_router(skeleton.router, prefix="/api/v1")


@app.on_event("startup")
def on_startup() -> None:
    """初始化 sqlite 表结构并将 SAMPLE_DATA 导入为基础数据。"""

    # 创建所有模型对应的表
    Base.metadata.create_all(bind=engine)

    # 如果是首次启动，则用 SAMPLE_DATA 初始化数据
    db = SessionLocal()
    try:
        init_db(db)
    finally:
        db.close()


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
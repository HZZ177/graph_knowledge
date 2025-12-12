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
    files,
    coding,
    testing,
    doc_center,
)
from backend.app.core.file_path import storage_yml_path

from backend.app.db.sqlite import Base, engine, SessionLocal
from backend.app.db.init_db import init_db
from backend.app.core.middleware import trace_id_middleware
from backend.app.core.logger import logger
from backend.app.models import ai_models, chat as chat_models, doc_center as doc_center_models  # noqa: F401  确保表被创建
from backend.mcp.ace_code_engine import warmup_ace_mcp
from backend.app.llm.langchain.registry import AgentRegistry
from backend.app.core.ripgrep import ensure_ripgrep_installed

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan handler: 初始化数据库、预热 MCP 和 Agent。"""

    # startup
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        init_db(db)
        
        # 可选：预热关键 Agent（减少首次请求延迟）
        # 如果 LLM 未配置，跳过预热，不阻断启动
        try:
            registry = AgentRegistry.get_instance()
            registry.warmup("knowledge_qa", db)
            logger.info("[Lifespan] Agent 预热完成")
        except Exception as e:
            logger.warning(f"[Lifespan] Agent 预热跳过（LLM 可能未配置）: {e}")
        
        # 预热 LightRAG（永策Pro智能助手）
        try:
            from backend.app.services.lightrag_service import LightRAGService
            await LightRAGService.warmup(db)
        except Exception as e:
            logger.warning(f"[Lifespan] LightRAG 预热跳过: {e}")
        
        # 重置卡在 running 状态的索引任务（服务非正常退出时可能遗留）
        try:
            from backend.app.services.lightrag_index_service import LightRAGIndexService
            reset_count = LightRAGIndexService.reset_stale_tasks(db)
            if reset_count > 0:
                logger.info(f"[Lifespan] 重置了 {reset_count} 个卡住的索引任务")
        except Exception as e:
            logger.warning(f"[Lifespan] 索引任务重置失败: {e}")
    finally:
        db.close()

    # 预热 AceCodeEngine MCP 客户端，降低首次调用时的冷启动开销
    warmup_ace_mcp()

    # 确保 ripgrep 已安装（用于 grep_code 工具）
    ensure_ripgrep_installed()

    # 初始化文件存储服务
    try:
        from backend.app.services.storage import init_storage_service
        init_storage_service(storage_yml_path)
        logger.info("[Lifespan] 文件存储服务初始化完成")
    except Exception as e:
        logger.warning(f"[Lifespan] 文件存储服务初始化失败（如不使用文件上传功能可忽略）: {e}")

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
app.include_router(files.router, prefix="/api/v1")
app.include_router(coding.router, prefix="/api/v1")
app.include_router(testing.router, prefix="/api/v1")
app.include_router(doc_center.router, prefix="/api/v1")


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
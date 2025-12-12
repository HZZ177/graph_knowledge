"""
LightRAG 索引服务

提供以下功能：
1. 索引任务队列管理
2. 后台索引处理（基于 APScheduler）
3. 进度追踪和状态持久化
4. WebSocket 进度推送

参考 test/lightrag_demo.py 的实现
"""

import os
import re
import asyncio
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.core.logger import logger
from backend.app.db.sqlite import SessionLocal
from backend.app.models.doc_center import DocCenterDocument, DocCenterIndexTask


# ============== 配置（复用 lightrag_demo 和 lightrag_service）==============

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# Neo4j 配置
NEO4J_URI = "neo4j+s://c6010ae0.databases.neo4j.io"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "GMaCBUonUoHZCYcqa8mBho_FAjVBnykTlEdgpMKLdZU"

# LightRAG 配置
LIGHTRAG_WORKING_DIR = str(_PROJECT_ROOT / "test" / "lightrag_data")
LIGHTRAG_WORKSPACE = "opdoc"

# LLM 配置
LLM_API_KEY = "sk-z7HUcbUoz6yVKBnEPrMiXnrljTmzmRNpHBL224MqgFoOxoux"
LLM_BASE_URL = "https://88996.cloud/v1"
LLM_MODEL = "gemini-2.5-flash"

# Embedding 配置
EMBEDDING_API_KEY = "sk-vxyvdnryevgolxatlsqilklzpiyfadxpkkqpvsagrgvuzavi"
EMBEDDING_BASE_URL = "https://api.siliconflow.cn/v1"
EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-8B"
EMBEDDING_DIM = 4096


# ============== 索引阶段定义 ==============

INDEX_PHASES = {
    "preparing": {"weight": 5, "name": "准备中"},
    "chunking": {"weight": 5, "name": "文档分块"},
    "entity_extraction": {"weight": 40, "name": "实体抽取"},
    "relation_extraction": {"weight": 25, "name": "关系抽取"},
    "embedding": {"weight": 15, "name": "向量化"},
    "storage": {"weight": 10, "name": "存储"},
}

PHASE_ORDER = list(INDEX_PHASES.keys())


def calculate_overall_progress(current_phase: str, phase_progress: int) -> int:
    """计算总体进度百分比"""
    if current_phase not in PHASE_ORDER:
        return 0

    # 已完成阶段的权重
    completed_weight = sum(
        INDEX_PHASES[p]["weight"] for p in PHASE_ORDER
        if PHASE_ORDER.index(p) < PHASE_ORDER.index(current_phase)
    )

    # 当前阶段的部分进度
    current_weight = INDEX_PHASES.get(current_phase, {}).get("weight", 0)
    current_progress = current_weight * phase_progress / 100

    return int(completed_weight + current_progress)


# ============== LightRAG 索引器（复用 lightrag_demo 逻辑）==============

class LightRAGIndexer:
    """LightRAG 索引器，封装文档索引逻辑"""

    def __init__(self):
        self.rag = None
        self.embedding_stats = {}
        self._progress_callback: Optional[Callable] = None
        self._setup_env()

    def _setup_env(self):
        """设置环境变量"""
        os.environ["NEO4J_URI"] = NEO4J_URI
        os.environ["NEO4J_USERNAME"] = NEO4J_USERNAME
        os.environ["NEO4J_PASSWORD"] = NEO4J_PASSWORD
        os.environ["OPENAI_API_KEY"] = LLM_API_KEY
        os.makedirs(LIGHTRAG_WORKING_DIR, exist_ok=True)

    def set_progress_callback(self, callback: Callable):
        """设置进度回调函数"""
        self._progress_callback = callback

    async def _report_progress(self, phase: str, phase_progress: int, detail: str = ""):
        """报告进度"""
        overall = calculate_overall_progress(phase, phase_progress)
        if self._progress_callback:
            await self._progress_callback(phase, phase_progress, overall, detail)

    async def initialize(self):
        """初始化 LightRAG"""
        logger.info("[LightRAGIndexer] 正在初始化...")

        try:
            from lightrag import LightRAG
            from lightrag.llm.openai import openai_complete_if_cache, openai_embed
            from lightrag.utils import EmbeddingFunc
            from lightrag.kg.shared_storage import initialize_pipeline_status
            import numpy as np

            # 自定义 LLM 函数
            async def llm_func(prompt, system_prompt=None, history_messages=[], **kwargs):
                return await openai_complete_if_cache(
                    model=LLM_MODEL,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    history_messages=history_messages,
                    api_key=LLM_API_KEY,
                    base_url=LLM_BASE_URL,
                    **kwargs
                )

            # Embedding 统计
            self.embedding_stats = {
                "total_texts": 0,
                "phase": "",
                "phase_total": 0,
                "phase_done": 0,
            }

            # 自定义 Embedding 函数
            async def embedding_func(texts: list[str]) -> np.ndarray:
                stats = self.embedding_stats
                stats["total_texts"] += len(texts)
                stats["phase_done"] += len(texts)

                result = await openai_embed(
                    texts,
                    model=EMBEDDING_MODEL,
                    api_key=EMBEDDING_API_KEY,
                    base_url=EMBEDDING_BASE_URL,
                )
                return result

            # 创建 LightRAG 实例
            self.rag = LightRAG(
                working_dir=LIGHTRAG_WORKING_DIR,
                llm_model_func=llm_func,
                embedding_func=EmbeddingFunc(
                    embedding_dim=EMBEDDING_DIM,
                    max_token_size=8192,
                    func=embedding_func,
                ),
                graph_storage="Neo4JStorage",
                vector_storage="NanoVectorDBStorage",
                kv_storage="JsonKVStorage",
                doc_status_storage="JsonDocStatusStorage",
                workspace=LIGHTRAG_WORKSPACE,
                chunk_token_size=1200,
                chunk_overlap_token_size=100,
                embedding_batch_num=8,
                embedding_func_max_async=1,
                llm_model_max_async=6,
                addon_params={"language": "Chinese"},
            )

            await self.rag.initialize_storages()
            await initialize_pipeline_status()

            logger.info("[LightRAGIndexer] 初始化成功")

        except Exception as e:
            logger.error(f"[LightRAGIndexer] 初始化失败: {e}")
            raise

    async def index_document(self, file_path: str, doc_title: str) -> Dict[str, Any]:
        """
        索引单个文档

        Args:
            file_path: 本地文件路径
            doc_title: 文档标题

        Returns:
            {success: bool, stats: {...}, error: str}
        """
        if not self.rag:
            await self.initialize()

        logger.info(f"[LightRAGIndexer] 开始索引: {doc_title}")

        # 重置统计
        self.embedding_stats = {
            "total_texts": 0,
            "phase": "",
            "phase_total": 0,
            "phase_done": 0,
        }

        try:
            # 读取文件
            await self._report_progress("preparing", 0, "读取文件...")
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")

            text = path.read_text(encoding="utf-8")
            if not text:
                raise ValueError("文件内容为空")

            await self._report_progress("preparing", 100, f"文件读取完成，{len(text)} 字符")

            # 添加文档标识
            doc_content = f"[文档名称: {doc_title}]\n\n{text}"

            # 启动进度监听
            start_time = time.time()
            from lightrag.kg.shared_storage import get_namespace_data, get_pipeline_status_lock

            async def monitor_progress():
                try:
                    pipeline_status = await get_namespace_data("pipeline_status")
                    pipeline_status_lock = get_pipeline_status_lock()
                    last_message = ""

                    while True:
                        await asyncio.sleep(0.5)
                        async with pipeline_status_lock:
                            current_message = pipeline_status.get("latest_message", "")
                            if current_message and current_message != last_message:
                                # 解析阶段信息
                                match = re.search(
                                    r'Phase (\d+): Processing (\d+) (entities|relations)',
                                    current_message
                                )
                                if match:
                                    phase_num = match.group(1)
                                    total = int(match.group(2))
                                    phase_type = match.group(3)

                                    if phase_type == "entities":
                                        phase = "entity_extraction"
                                    else:
                                        phase = "relation_extraction"

                                    self.embedding_stats["phase"] = phase
                                    self.embedding_stats["phase_total"] = total
                                    self.embedding_stats["phase_done"] = 0

                                    await self._report_progress(phase, 0, f"处理 {total} 个{phase_type}")

                                elif "Completed merging" in current_message:
                                    await self._report_progress("storage", 50, "合并存储中...")

                                last_message = current_message
                except asyncio.CancelledError:
                    pass

            monitor_task = asyncio.create_task(monitor_progress())

            try:
                # 执行索引
                await self._report_progress("chunking", 0, "分块处理中...")
                await self.rag.ainsert(doc_content, file_paths=[file_path])

                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass

                elapsed = time.time() - start_time
                await self._report_progress("storage", 100, f"索引完成，耗时 {elapsed:.1f}s")

                logger.info(f"[LightRAGIndexer] 索引成功: {doc_title}, 耗时 {elapsed:.1f}s")

                return {
                    "success": True,
                    "stats": {
                        "total_embeddings": self.embedding_stats["total_texts"],
                        "elapsed_seconds": elapsed,
                    },
                    "error": None,
                }

            except Exception as e:
                monitor_task.cancel()
                raise

        except Exception as e:
            logger.error(f"[LightRAGIndexer] 索引失败: {e}")
            return {
                "success": False,
                "stats": {},
                "error": str(e),
            }

    async def close(self):
        """关闭连接"""
        if self.rag:
            try:
                await self.rag.finalize_storages()
                logger.info("[LightRAGIndexer] 连接已关闭")
            except:
                pass


# ============== 索引任务服务 ==============

class LightRAGIndexService:
    """LightRAG 索引任务服务"""

    _indexer: Optional[LightRAGIndexer] = None
    _is_running: bool = False
    _current_task_id: Optional[str] = None
    _progress_subscribers: Dict[str, Callable] = {}

    @classmethod
    def get_indexer(cls) -> LightRAGIndexer:
        """获取索引器单例"""
        if cls._indexer is None:
            cls._indexer = LightRAGIndexer()
        return cls._indexer

    @classmethod
    def subscribe_progress(cls, subscriber_id: str, callback: Callable):
        """订阅进度更新"""
        cls._progress_subscribers[subscriber_id] = callback

    @classmethod
    def unsubscribe_progress(cls, subscriber_id: str):
        """取消订阅"""
        cls._progress_subscribers.pop(subscriber_id, None)

    @classmethod
    async def _broadcast_progress(
        cls,
        task_id: str,
        document_id: str,
        phase: str,
        phase_progress: int,
        overall_progress: int,
        detail: str
    ):
        """广播进度给所有订阅者"""
        message = {
            "task_id": task_id,
            "document_id": document_id,
            "phase": phase,
            "phase_name": INDEX_PHASES.get(phase, {}).get("name", phase),
            "phase_progress": phase_progress,
            "overall_progress": overall_progress,
            "detail": detail,
        }
        for callback in cls._progress_subscribers.values():
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
            except Exception as e:
                logger.warning(f"[IndexService] 进度回调失败: {e}")

    @classmethod
    def create_task(cls, db: Session, document_id: str, priority: int = 0) -> DocCenterIndexTask:
        """创建索引任务"""
        # 检查是否已有待处理任务
        existing = db.query(DocCenterIndexTask).filter(
            DocCenterIndexTask.document_id == document_id,
            DocCenterIndexTask.status.in_(["pending", "running"])
        ).first()

        if existing:
            logger.info(f"[IndexService] 文档已有待处理任务: {document_id}")
            return existing

        task = DocCenterIndexTask(
            id=uuid4().hex,
            document_id=document_id,
            status="pending",
            priority=priority,
        )
        db.add(task)

        # 更新文档状态
        doc = db.query(DocCenterDocument).filter(DocCenterDocument.id == document_id).first()
        if doc:
            doc.index_status = "queued"
            doc.index_error = None

        db.commit()
        logger.info(f"[IndexService] 创建任务: task_id={task.id}, doc_id={document_id}")
        return task

    @classmethod
    def get_pending_tasks(cls, db: Session, limit: int = 10) -> List[DocCenterIndexTask]:
        """获取待处理任务（按优先级排序）"""
        return db.query(DocCenterIndexTask).filter(
            DocCenterIndexTask.status == "pending"
        ).order_by(
            DocCenterIndexTask.priority.desc(),
            DocCenterIndexTask.created_at.asc()
        ).limit(limit).all()

    @classmethod
    def get_task_by_id(cls, db: Session, task_id: str) -> Optional[DocCenterIndexTask]:
        """获取任务"""
        return db.query(DocCenterIndexTask).filter(DocCenterIndexTask.id == task_id).first()

    @classmethod
    async def process_task(cls, task_id: str) -> Dict[str, Any]:
        """处理单个索引任务"""
        db = SessionLocal()
        try:
            task = cls.get_task_by_id(db, task_id)
            if not task:
                return {"success": False, "error": "任务不存在"}

            doc = db.query(DocCenterDocument).filter(
                DocCenterDocument.id == task.document_id
            ).first()
            if not doc:
                return {"success": False, "error": "文档不存在"}

            if not doc.local_path or not Path(doc.local_path).exists():
                task.status = "failed"
                task.error_message = "本地文件不存在，请先同步文档"
                doc.index_status = "failed"
                doc.index_error = task.error_message
                db.commit()
                return {"success": False, "error": task.error_message}

            # 更新状态为运行中
            task.status = "running"
            task.started_at = datetime.utcnow()
            doc.index_status = "indexing"
            doc.index_started_at = datetime.utcnow()
            db.commit()

            cls._current_task_id = task_id

            # 设置进度回调
            indexer = cls.get_indexer()

            async def progress_callback(phase, phase_progress, overall_progress, detail):
                # 更新数据库
                nonlocal task, doc
                task.current_phase = phase
                task.phase_progress = phase_progress
                task.overall_progress = overall_progress
                doc.index_phase = phase
                doc.index_phase_detail = detail
                doc.index_progress = overall_progress
                db.commit()

                # 广播给订阅者
                await cls._broadcast_progress(
                    task_id, doc.id, phase, phase_progress, overall_progress, detail
                )

            indexer.set_progress_callback(progress_callback)

            # 执行索引
            result = await indexer.index_document(doc.local_path, doc.title)

            # 更新最终状态
            if result["success"]:
                task.status = "completed"
                task.finished_at = datetime.utcnow()
                task.overall_progress = 100
                doc.index_status = "indexed"
                doc.index_progress = 100
                doc.index_finished_at = datetime.utcnow()
                doc.index_error = None

                if result.get("stats"):
                    doc.chunk_count = result["stats"].get("total_embeddings", 0)
            else:
                task.status = "failed"
                task.finished_at = datetime.utcnow()
                task.error_message = result.get("error", "未知错误")
                doc.index_status = "failed"
                doc.index_error = task.error_message

            db.commit()
            cls._current_task_id = None

            return result

        except Exception as e:
            logger.error(f"[IndexService] 任务处理异常: {e}")
            try:
                task = db.query(DocCenterIndexTask).filter(DocCenterIndexTask.id == task_id).first()
                if task:
                    task.status = "failed"
                    task.error_message = str(e)
                doc = db.query(DocCenterDocument).filter(
                    DocCenterDocument.id == task.document_id
                ).first()
                if doc:
                    doc.index_status = "failed"
                    doc.index_error = str(e)
                db.commit()
            except:
                pass
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    @classmethod
    async def process_queue(cls):
        """处理任务队列（可被定时调用）"""
        if cls._is_running:
            logger.debug("[IndexService] 队列处理已在运行中")
            return

        cls._is_running = True
        logger.info("[IndexService] 开始处理任务队列")

        try:
            db = SessionLocal()
            pending_tasks = cls.get_pending_tasks(db, limit=1)
            db.close()

            for task in pending_tasks:
                logger.info(f"[IndexService] 处理任务: {task.id}")
                await cls.process_task(task.id)

        except Exception as e:
            logger.error(f"[IndexService] 队列处理异常: {e}")
        finally:
            cls._is_running = False

    @classmethod
    def get_queue_status(cls, db: Session) -> Dict[str, Any]:
        """获取队列状态"""
        pending_count = db.query(DocCenterIndexTask).filter(
            DocCenterIndexTask.status == "pending"
        ).count()

        running_task = db.query(DocCenterIndexTask).filter(
            DocCenterIndexTask.status == "running"
        ).first()

        return {
            "is_running": cls._is_running,
            "pending_count": pending_count,
            "current_task_id": cls._current_task_id,
            "current_task": {
                "id": running_task.id,
                "document_id": running_task.document_id,
                "phase": running_task.current_phase,
                "progress": running_task.overall_progress,
            } if running_task else None,
        }

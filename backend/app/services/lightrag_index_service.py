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
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from uuid import uuid4


# ============== LightRAG 日志配置（桥接到 loguru） ==============

class InterceptHandler(logging.Handler):
    """将标准 logging 桥接到 loguru"""
    
    def emit(self, record):
        # 获取对应的 loguru 级别
        try:
            from backend.app.core.logger import logger as loguru_logger
            level = loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        
        # 获取调用者信息
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        
        # 输出到 loguru（添加来源标识）
        from backend.app.core.logger import logger as loguru_logger
        loguru_logger.opt(depth=depth, exception=record.exc_info).log(
            level, f"[{record.name}] {record.getMessage()}"
        )

def _setup_logging_bridge():
    """设置日志桥接"""
    # 需要桥接的 logger
    loggers_to_bridge = [
        ("lightrag", logging.DEBUG),
        ("httpx", logging.DEBUG),
        ("openai", logging.DEBUG),
        ("neo4j", logging.INFO),
    ]
    
    # 降低噪音
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    handler = InterceptHandler()
    
    for logger_name, level in loggers_to_bridge:
        target_logger = logging.getLogger(logger_name)
        target_logger.setLevel(level)
        # 避免重复添加
        if not any(isinstance(h, InterceptHandler) for h in target_logger.handlers):
            target_logger.addHandler(handler)
            # 禁止向上传播，避免重复输出
            target_logger.propagate = False

# 模块加载时设置桥接
_setup_logging_bridge()

from sqlalchemy.orm import Session

from backend.app.core.logger import logger
from backend.app.db.sqlite import SessionLocal
from backend.app.db.neo4j_client import (
    DEFAULT_NEO4J_URI,
    DEFAULT_NEO4J_USER,
    DEFAULT_NEO4J_PASSWORD,
)
from backend.app.models.doc_center import DocCenterDocument, DocCenterIndexTask
from backend.app.services.ai_model_service import AIModelService
from backend.app.core.lightrag_config import (
    LIGHTRAG_WORKING_DIR,
    LIGHTRAG_WORKSPACE,
    EMBEDDING_MODEL,
    EMBEDDING_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_DIM,
    CHUNK_TOKEN_SIZE,
    CHUNK_OVERLAP_TOKEN_SIZE,
    EMBEDDING_BATCH_NUM,
    EMBEDDING_FUNC_MAX_ASYNC,
    LLM_MODEL_MAX_ASYNC,
    KV_STORAGE,
    VECTOR_STORAGE,
    GRAPH_STORAGE,
    DOC_STATUS_STORAGE,
)


# ============== 三阶段进度数据结构 ==============

from dataclasses import dataclass, field


@dataclass
class IndexProgress:
    """索引进度数据（两阶段）
    
    阶段1: 提取阶段 - LLM 分块 + 提取实体/关系
    阶段2: 图谱构建 - 合并 Phase1(entities) + Phase2(relations)
    
    进度追踪策略：
    - 从 "Chunk X of Y extracted N Ent + M Rel" 日志累计总数
    - 用 embedding_func 调用次数追踪图谱构建进度
    """
    # 阶段1: 提取阶段
    extraction_progress: int = 0
    # 阶段2: 图谱构建（entities + relations 合并）
    # 从 chunk 日志累计的总数
    entities_total: int = 0
    relations_total: int = 0
    # 图谱构建进度（通过 embedding 调用次数追踪）
    graph_build_done: int = 0
    # 兼容前端显示：按比例分配给 entities_done 和 relations_done
    entities_done: int = 0
    relations_done: int = 0
    # 当前阶段: extraction | graph_building | completed
    current_phase: str = "extraction"
    
    @property
    def graph_build_total(self) -> int:
        """entities + relations 总数"""
        return self.entities_total + self.relations_total
    
    @property
    def graph_build_progress(self) -> int:
        """图谱构建进度百分比"""
        total = self.graph_build_total
        if total == 0:
            return 0
        return min(100, int(self.graph_build_done / total * 100))
    
    def to_dict(self) -> dict:
        return {
            "current_phase": self.current_phase,
            "extraction_progress": self.extraction_progress,
            # 图谱构建阶段（合并 entities + relations）
            "graph_build_total": self.graph_build_total,
            "graph_build_done": self.graph_build_done,
            "graph_build_progress": self.graph_build_progress,
            # 详情：实体和关系的总数
            "entities_total": self.entities_total,
            "relations_total": self.relations_total,
        }


# ============== LightRAG 索引器（复用 lightrag_demo 逻辑）==============

class LightRAGIndexer:
    """LightRAG 索引器，封装文档索引逻辑
    
    配置策略：
    - LLM：复用系统配置的小任务模型（task model）
    - Neo4j：复用系统统一配置
    - Embedding：暂时硬编码
    
    进度监控（三阶段）：
    1. extraction: LLM分块+提取
    2. entities: Phase 1 - 实体处理
    3. relations: Phase 2 - 关系处理
    """

    def __init__(self, db: Session):
        self.rag = None
        self._progress = IndexProgress()
        self._progress_callback: Optional[Callable] = None
        self._db = db
        self._llm_config = None
        self._setup_env()

    def _setup_env(self):
        """设置环境变量（复用系统配置）"""
        # Neo4j 配置 - 复用 neo4j_client
        os.environ["NEO4J_URI"] = DEFAULT_NEO4J_URI
        os.environ["NEO4J_USERNAME"] = DEFAULT_NEO4J_USER
        os.environ["NEO4J_PASSWORD"] = DEFAULT_NEO4J_PASSWORD
        
        # LLM 配置 - 复用系统的小任务模型
        try:
            self._llm_config = AIModelService.get_task_llm_config(self._db)
            os.environ["OPENAI_API_KEY"] = self._llm_config.api_key
            logger.info(f"[LightRAGIndexer] 使用 LLM 配置: model={self._llm_config.model_name}")
        except RuntimeError as e:
            logger.error(f"[LightRAGIndexer] 获取 LLM 配置失败: {e}")
            raise
        
        os.makedirs(LIGHTRAG_WORKING_DIR, exist_ok=True)

    def set_progress_callback(self, callback: Callable[[IndexProgress], Any]):
        """设置进度回调函数
        
        Args:
            callback: 回调函数，接收 IndexProgress 参数
        """
        self._progress_callback = callback

    async def _report_progress(self):
        """报告当前进度"""
        if self._progress_callback:
            await self._progress_callback(self._progress)

    def _setup_lightrag_log_handler(self):
        """设置 LightRAG 日志处理器，捕获 Phase 信息更新进度"""
        indexer = self
        
        class ProgressLogHandler(logging.Handler):
            """捕获 LightRAG 日志并解析进度信息
            
            进度追踪策略：
            1. 从 "Chunk X of Y extracted N Ent + M Rel" 日志累计 entities 和 relations 总数
            2. 从 "Merging stage" 进入图谱构建阶段
            3. embedding_func 调用次数追踪图谱构建进度（在 embedding_func 中实现）
            """
            
            def emit(self, record):
                try:
                    message = self.format(record)
                    
                    # 解析 "Chunk X of Y extracted N Ent + M Rel chunk-xxx"
                    # 累计 entities 和 relations 总数
                    chunk_match = re.search(
                        r'Chunk (\d+) of (\d+) extracted (\d+) Ent \+ (\d+) Rel',
                        message
                    )
                    if chunk_match:
                        chunk_done = int(chunk_match.group(1))
                        chunk_total = int(chunk_match.group(2))
                        ent_count = int(chunk_match.group(3))
                        rel_count = int(chunk_match.group(4))
                        
                        # 累计总数
                        indexer._progress.entities_total += ent_count
                        indexer._progress.relations_total += rel_count
                        
                        # 更新提取进度（10-90%）
                        progress = 10 + int((chunk_done / max(chunk_total, 1)) * 80)
                        indexer._progress.extraction_progress = min(progress, 90)
                        
                        logger.debug(
                            f"[LightRAGIndexer:LogHandler] Chunk {chunk_done}/{chunk_total}: "
                            f"+{ent_count} Ent, +{rel_count} Rel, "
                            f"累计: {indexer._progress.entities_total} Ent, {indexer._progress.relations_total} Rel"
                        )
                        return
                    
                    # 解析 Extracting stage X/Y（备用，chunk 日志更准确）
                    extract_match = re.search(r'Extracting stage (\d+)/(\d+)', message)
                    if extract_match:
                        done = int(extract_match.group(1))
                        total = int(extract_match.group(2))
                        progress = 10 + int((done / max(total, 1)) * 80)
                        indexer._progress.extraction_progress = min(progress, 90)
                        return
                    
                    # 解析 Merging stage - 进入图谱构建阶段
                    merge_match = re.search(r'Merging stage (\d+)/(\d+)', message)
                    if merge_match:
                        indexer._progress.extraction_progress = 100
                        indexer._progress.current_phase = "graph_building"
                        indexer._progress.graph_build_done = 0  # 重置图谱构建进度
                        logger.info(
                            f"[LightRAGIndexer:LogHandler] 进入图谱构建阶段: "
                            f"{indexer._progress.entities_total} 实体, {indexer._progress.relations_total} 关系"
                        )
                        return
                    
                    # 检测完成
                    if "Completed merging" in message:
                        indexer._progress.current_phase = "completed"
                        indexer._progress.extraction_progress = 100
                        # 完成时同步 done 到 total
                        indexer._progress.entities_done = indexer._progress.entities_total
                        indexer._progress.relations_done = indexer._progress.relations_total
                    
                except Exception as e:
                    pass  # 日志处理不应影响主流程
        
        # 获取 LightRAG logger 并添加 handler
        lightrag_logger = logging.getLogger("lightrag")
        
        # 检查是否已添加过
        handler_exists = any(
            isinstance(h, ProgressLogHandler) 
            for h in lightrag_logger.handlers
        )
        if not handler_exists:
            handler = ProgressLogHandler()
            handler.setLevel(logging.INFO)
            lightrag_logger.addHandler(handler)
            logger.info("[LightRAGIndexer] 已添加进度日志处理器")

    async def initialize(self):
        """初始化 LightRAG"""
        logger.info("[LightRAGIndexer] 正在初始化...")

        try:
            from lightrag import LightRAG
            from lightrag.llm.openai import openai_complete_if_cache, openai_embed
            from lightrag.utils import EmbeddingFunc
            from lightrag.kg.shared_storage import initialize_pipeline_status
            import numpy as np

            # 自定义 LLM 函数（复用系统配置）
            llm_config = self._llm_config
            
            # 处理 base_url
            base_url = llm_config.base_url
            if llm_config.provider_type == "custom_gateway" and llm_config.gateway_endpoint:
                base_url = llm_config.gateway_endpoint.rstrip("/")
                # LightRAG 会自动追加 /chat/completions
                if base_url.endswith("/chat/completions"):
                    base_url = base_url[:-17]
                elif base_url.endswith("/chat/completions/"):
                    base_url = base_url[:-18]
                if not base_url.endswith("/v1"):
                    base_url = base_url + "/v1"
            
            async def llm_func(prompt, system_prompt=None, history_messages=[], **kwargs):
                return await openai_complete_if_cache(
                    model=llm_config.model_name,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    history_messages=history_messages,
                    api_key=llm_config.api_key,
                    base_url=base_url,
                    **kwargs
                )

            # 自定义 Embedding 函数（带进度追踪和速率限制）
            _last_embed_time = {"value": 0}
            
            async def embedding_func(texts: list[str]) -> np.ndarray:
                # 速率限制：确保两次调用间隔至少 2.5 秒
                import time as _time
                now = _time.time()
                elapsed = now - _last_embed_time["value"]
                if elapsed < 2.5:
                    await asyncio.sleep(2.5 - elapsed)
                _last_embed_time["value"] = _time.time()
                
                # 图谱构建阶段：追踪 embedding 调用次数
                progress = self._progress
                if progress.current_phase == "graph_building":
                    batch_size = len(texts)
                    progress.graph_build_done += batch_size
                    
                    logger.debug(
                        f"[Embedding] 图谱构建: {progress.graph_build_done}/{progress.graph_build_total} "
                        f"({progress.graph_build_progress}%)"
                    )
                
                # 触发进度回调
                await self._report_progress()
                
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
                workspace=LIGHTRAG_WORKSPACE,
                llm_model_func=llm_func,
                embedding_func=EmbeddingFunc(
                    embedding_dim=EMBEDDING_DIM,
                    max_token_size=8192,
                    func=embedding_func,
                ),
                graph_storage=GRAPH_STORAGE,
                vector_storage=VECTOR_STORAGE,
                kv_storage=KV_STORAGE,
                doc_status_storage=DOC_STATUS_STORAGE,
                chunk_token_size=CHUNK_TOKEN_SIZE,
                chunk_overlap_token_size=CHUNK_OVERLAP_TOKEN_SIZE,
                embedding_batch_num=EMBEDDING_BATCH_NUM,
                embedding_func_max_async=EMBEDDING_FUNC_MAX_ASYNC,
                llm_model_max_async=LLM_MODEL_MAX_ASYNC,
                addon_params={"language": "Chinese"},
            )

            await self.rag.initialize_storages()
            await initialize_pipeline_status()
            
            # 设置日志处理器来捕获 Phase 信息
            self._setup_lightrag_log_handler()

            logger.info("[LightRAGIndexer] 初始化成功")

        except Exception as e:
            logger.error(f"[LightRAGIndexer] 初始化失败: {e}")
            raise

    async def _cleanup_lightrag_queue_documents(self) -> int:
        if not self.rag:
            return 0

        from lightrag.base import DocStatus

        total_deleted = 0
        for status in (DocStatus.PENDING, DocStatus.PROCESSING, DocStatus.FAILED):
            docs = await self.rag.doc_status.get_docs_by_status(status)
            if not docs:
                continue
            logger.info(
                f"[LightRAGIndexer] 清理残留文档: status={status.value}, count={len(docs)}"
            )
            for doc_id in list(docs.keys()):
                await self.rag.adelete_by_doc_id(doc_id)
                total_deleted += 1

        if total_deleted:
            logger.info(f"[LightRAGIndexer] 清理残留文档完成: deleted={total_deleted}")
        return total_deleted

    async def _validate_track_result(self, track_id: str) -> None:
        if not self.rag:
            raise RuntimeError("LightRAG 未初始化")

        from lightrag.base import DocStatus

        docs_by_track = await self.rag.aget_docs_by_track_id(track_id)
        if not docs_by_track:
            raise Exception(f"LightRAG 未找到 track_id 对应的文档状态: track_id={track_id}")

        for doc_id, status_obj in docs_by_track.items():
            raw_status = getattr(status_obj, "status", None)
            try:
                doc_status = raw_status if isinstance(raw_status, DocStatus) else DocStatus(str(raw_status))
            except Exception:
                doc_status = str(raw_status)

            error_msg = getattr(status_obj, "error_msg", None)
            if doc_status not in (DocStatus.PROCESSED, DocStatus.PREPROCESSED):
                raise Exception(
                    f"LightRAG 文档处理失败: doc_id={doc_id}, status={doc_status}, error={error_msg}"
                )

            if error_msg:
                raise Exception(
                    f"LightRAG 文档处理失败: doc_id={doc_id}, status={doc_status}, error={error_msg}"
                )

    async def index_document(self, content: str, doc_title: str, source_url: str = None) -> Dict[str, Any]:
        """
        索引单个文档

        Args:
            content: 文档内容（Markdown文本）
            doc_title: 文档标题
            source_url: 文档来源URL（用于生成 reference_id）

        Returns:
            {success: bool, stats: {...}, error: str}
        """
        if not self.rag:
            await self.initialize()

        logger.info(f"[LightRAGIndexer] 开始索引: {doc_title}")

        # 重置进度
        self._progress = IndexProgress()

        try:
            # 检查内容
            if not content:
                raise ValueError("文档内容为空")

            # 阶段1: 提取阶段开始
            self._progress.current_phase = "extraction"
            self._progress.extraction_progress = 10
            await self._report_progress()

            # 添加文档标识
            doc_content = f"[文档名称: {doc_title}]\n\n{content}"

            await self._cleanup_lightrag_queue_documents()

            # 启动进度监听（解析 LightRAG 的 Phase 信息）
            start_time = time.time()
            from lightrag.kg.shared_storage import get_namespace_data, get_pipeline_status_lock

            # 用于记录是否检测到错误
            detected_error = {"has_error": False, "message": ""}
            
            async def monitor_progress():
                """监听 LightRAG 的 pipeline_status 和日志处理器更新的进度"""
                try:
                    pipeline_status = await get_namespace_data("pipeline_status")
                    pipeline_status_lock = get_pipeline_status_lock()
                    last_message = ""
                    last_progress_snapshot = None

                    while True:
                        await asyncio.sleep(0.3)
                        
                        # 定期报告进度（日志处理器可能已更新 _progress）
                        current_snapshot = (
                            self._progress.extraction_progress,
                            self._progress.current_phase,
                            self._progress.entities_done,
                            self._progress.relations_done,
                        )
                        if current_snapshot != last_progress_snapshot:
                            await self._report_progress()
                            last_progress_snapshot = current_snapshot
                        
                        async with pipeline_status_lock:
                            current_message = pipeline_status.get("latest_message", "")
                            if current_message and current_message != last_message:
                                # 输出所有 LightRAG 消息（对齐 demo 的详细日志）
                                logger.info(f"[LightRAG:Pipeline] {current_message}")
                                
                                # 检测错误消息
                                if "failed" in current_message.lower() and "merging" not in current_message.lower():
                                    detected_error["has_error"] = True
                                    detected_error["message"] = current_message
                                
                                # 检测 pipeline stopped（通常意味着出错）
                                if "pipeline stopped" in current_message.lower():
                                    detected_error["has_error"] = True
                                    if not detected_error["message"]:
                                        detected_error["message"] = current_message
                                
                                # 检测提取阶段进度
                                # 格式: "Extracting entities from chunks: X/Y"
                                extract_match = re.search(
                                    r'Extracting.*?(\d+)/(\d+)',
                                    current_message
                                )
                                if extract_match:
                                    done = int(extract_match.group(1))
                                    total = int(extract_match.group(2))
                                    # 提取阶段进度 10-90%
                                    progress = 10 + int((done / max(total, 1)) * 80)
                                    self._progress.extraction_progress = min(progress, 90)
                                    await self._report_progress()
                                
                                # 检测缓存跳过（文档已索引）
                                # 格式: "Document xxx already indexed, skipping"
                                if "already indexed" in current_message.lower() or "skipping" in current_message.lower():
                                    logger.info(f"[LightRAGIndexer] 检测到缓存跳过，标记为完成")
                                    self._progress.extraction_progress = 100
                                    self._progress.current_phase = "completed"
                                    await self._report_progress()
                                
                                # 解析 "Chunk X of Y extracted N Ent + M Rel"
                                # 累计 entities 和 relations 总数
                                chunk_match = re.search(
                                    r'Chunk (\d+) of (\d+) extracted (\d+) Ent \+ (\d+) Rel',
                                    current_message
                                )
                                if chunk_match:
                                    chunk_done = int(chunk_match.group(1))
                                    chunk_total = int(chunk_match.group(2))
                                    ent_count = int(chunk_match.group(3))
                                    rel_count = int(chunk_match.group(4))
                                    
                                    # 累计总数
                                    self._progress.entities_total += ent_count
                                    self._progress.relations_total += rel_count
                                    
                                    # 更新提取进度
                                    progress = 10 + int((chunk_done / max(chunk_total, 1)) * 80)
                                    self._progress.extraction_progress = min(progress, 90)
                                    await self._report_progress()
                                
                                # 解析 Merging stage - 进入图谱构建阶段
                                merge_stage_match = re.search(r'Merging stage (\d+)/(\d+)', current_message)
                                if merge_stage_match:
                                    self._progress.extraction_progress = 100
                                    self._progress.current_phase = "graph_building"
                                    self._progress.graph_build_done = 0
                                    logger.info(
                                        f"[LightRAGIndexer] 进入图谱构建阶段: "
                                        f"{self._progress.entities_total} 实体, {self._progress.relations_total} 关系"
                                    )
                                    await self._report_progress()

                                # 检测合并完成
                                if "Completed merging" in current_message:
                                    self._progress.current_phase = "completed"
                                    self._progress.extraction_progress = 100
                                    # 完成时同步 done 到 total
                                    self._progress.entities_done = self._progress.entities_total
                                    self._progress.relations_done = self._progress.relations_total
                                    await self._report_progress()

                                last_message = current_message
                except asyncio.CancelledError:
                    pass

            monitor_task = asyncio.create_task(monitor_progress())

            try:
                # 执行索引
                file_paths = [source_url] if source_url else None
                track_id = await self.rag.ainsert(doc_content, file_paths=file_paths)
                
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass
                
                # 检查是否检测到错误
                if detected_error["has_error"]:
                    logger.warning(
                        f"[LightRAGIndexer] pipeline_status 检测到错误消息(仅记录，不作为最终判定): {detected_error['message']}"
                    )

                try:
                    await self._validate_track_result(track_id)
                except Exception as track_error:
                    track_error_text = str(track_error)
                    if "未找到 track_id 对应的文档状态" in track_error_text:
                        from lightrag.base import DocStatus

                        existing_doc_data = None
                        if source_url:
                            existing_doc_data = await self.rag.doc_status.get_doc_by_file_path(source_url)

                        if existing_doc_data is None:
                            try:
                                from lightrag.utils import compute_mdhash_id, sanitize_text_for_encoding

                                doc_id = compute_mdhash_id(
                                    sanitize_text_for_encoding(doc_content),
                                    prefix="doc-",
                                )
                                existing_doc_data = await self.rag.doc_status.get_by_id(doc_id)
                            except Exception:
                                existing_doc_data = None

                        if existing_doc_data:
                            raw_status = existing_doc_data.get("status")
                            existing_error_msg = existing_doc_data.get("error_msg")
                            if raw_status in (DocStatus.PROCESSED.value, DocStatus.PREPROCESSED.value) and not existing_error_msg:
                                elapsed = time.time() - start_time
                                self._progress.current_phase = "completed"
                                self._progress.extraction_progress = 100
                                await self._report_progress()
                                logger.info(
                                    f"[LightRAGIndexer] 文档已存在于 LightRAG，跳过重复索引: {doc_title}, 耗时 {elapsed:.1f}s"
                                )
                                return {
                                    "success": True,
                                    "stats": None,
                                    "skipped": True,
                                    "error": None,
                                }

                    raise

                elapsed = time.time() - start_time
                
                # 标记完成
                self._progress.current_phase = "completed"
                self._progress.extraction_progress = 100
                await self._report_progress()

                logger.info(f"[LightRAGIndexer] 索引成功: {doc_title}, 耗时 {elapsed:.1f}s")

                return {
                    "success": True,
                    "stats": {
                        "entities_total": self._progress.entities_total,
                        "relations_total": self._progress.relations_total,
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
    def reset_stale_tasks(cls, db: Session) -> int:
        """清理未完成的任务（服务启动时调用）
        
        当服务重启时，清理所有 running 和 pending 状态的任务，
        避免旧任务堆积影响新的索引请求。
        
        Returns:
            清理的任务数量
        """
        # 查找所有未完成的任务（running 和 pending）
        stale_tasks = db.query(DocCenterIndexTask).filter(
            DocCenterIndexTask.status.in_(["running", "pending"])
        ).all()
        
        reset_count = 0
        for task in stale_tasks:
            # 重置对应文档的状态
            doc = db.query(DocCenterDocument).filter(
                DocCenterDocument.id == task.document_id
            ).first()
            if doc:
                doc.index_status = "pending"
                doc.index_error = None
                doc.extraction_progress = 0
                doc.entities_total = 0
                doc.entities_done = 0
                doc.relations_total = 0
                doc.relations_done = 0
            
            # 删除任务
            db.delete(task)
            reset_count += 1
            logger.info(f"[IndexService] 清理未完成任务: task_id={task.id}, doc_id={task.document_id}, status={task.status}")
        
        if reset_count > 0:
            db.commit()
            logger.info(f"[IndexService] 共清理 {reset_count} 个未完成任务")
        
        return reset_count

    @classmethod
    def get_indexer(cls, db: Session) -> LightRAGIndexer:
        """获取索引器单例
        
        Args:
            db: 数据库会话，用于获取 LLM 配置
        """
        if cls._indexer is None:
            cls._indexer = LightRAGIndexer(db)
        return cls._indexer
    
    @classmethod
    def invalidate_indexer(cls):
        """清除索引器单例（用于配置变更后重建）"""
        cls._indexer = None

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
        progress: IndexProgress
    ):
        """广播进度给所有订阅者（三阶段进度数据）"""
        message = {
            "task_id": task_id,
            "document_id": document_id,
            **progress.to_dict(),
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
    def cancel_task(cls, db: Session, document_id: str) -> Dict[str, Any]:
        """取消排队中的索引任务
        
        只能取消 pending 状态的任务，running 状态的任务无法取消
        """
        task = db.query(DocCenterIndexTask).filter(
            DocCenterIndexTask.document_id == document_id,
            DocCenterIndexTask.status == "pending"
        ).first()
        
        if not task:
            return {"success": False, "error": "没有找到排队中的任务"}
        
        # 重置文档状态
        doc = db.query(DocCenterDocument).filter(
            DocCenterDocument.id == document_id
        ).first()
        if doc:
            doc.index_status = "pending"
            doc.index_error = None
        
        # 删除任务
        db.delete(task)
        db.commit()
        
        logger.info(f"[IndexService] 取消任务: task_id={task.id}, doc_id={document_id}")
        return {"success": True, "task_id": task.id}

    @classmethod
    async def stop_running_task(cls, db: Session, document_id: str) -> Dict[str, Any]:
        """停止正在运行的索引任务
        
        通过设置 LightRAG 的 cancellation_requested 标志来请求停止
        """
        # 检查是否有正在运行的任务
        task = db.query(DocCenterIndexTask).filter(
            DocCenterIndexTask.document_id == document_id,
            DocCenterIndexTask.status == "running"
        ).first()
        
        if not task:
            return {"success": False, "error": "没有找到正在运行的任务"}
        
        try:
            from lightrag.kg.shared_storage import get_namespace_data, get_pipeline_status_lock
            
            pipeline_status = await get_namespace_data("pipeline_status")
            pipeline_status_lock = get_pipeline_status_lock()
            
            async with pipeline_status_lock:
                if not pipeline_status.get("busy", False):
                    return {"success": False, "error": "索引服务未在运行"}
                
                # 设置取消标志
                pipeline_status["cancellation_requested"] = True
                logger.info(f"[IndexService] 请求停止任务: task_id={task.id}, doc_id={document_id}")
            
            return {"success": True, "task_id": task.id}
        except Exception as e:
            logger.error(f"[IndexService] 停止任务失败: {e}")
            return {"success": False, "error": str(e)}

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

            if not doc.content:
                logger.warning(f"[IndexService] 文档内容为空: doc_id={doc.id}")
                task.status = "failed"
                task.error_message = "文档内容为空，请先同步文档"
                doc.index_status = "failed"
                doc.index_error = task.error_message
                db.commit()
                return {"success": False, "error": task.error_message}

            logger.info(f"[IndexService] 文档内容长度: {len(doc.content)} 字符")

            # 更新状态为运行中
            task.status = "running"
            task.started_at = datetime.utcnow()
            doc.index_status = "indexing"
            doc.index_started_at = datetime.utcnow()
            db.commit()

            cls._current_task_id = task_id

            # 设置进度回调
            indexer = cls.get_indexer(db)

            async def progress_callback(progress: IndexProgress):
                # 更新数据库（三阶段进度）
                nonlocal task, doc
                doc.extraction_progress = progress.extraction_progress
                doc.entities_total = progress.entities_total
                doc.entities_done = progress.entities_done
                doc.relations_total = progress.relations_total
                doc.relations_done = progress.relations_done
                db.commit()

                # 广播给订阅者（三阶段进度数据）
                await cls._broadcast_progress(task_id, doc.id, progress)

            indexer.set_progress_callback(progress_callback)

            # 执行索引（直接使用数据库中的 content）
            logger.info(f"[IndexService] 开始执行索引: title={doc.title}")
            try:
                result = await indexer.index_document(doc.content, doc.title, doc.source_url)
                logger.info(f"[IndexService] 索引完成: result={result}")
            except Exception as index_error:
                logger.error(f"[IndexService] 索引执行异常: {index_error}", exc_info=True)
                raise

            # 更新最终状态
            if result["success"]:
                task.status = "completed"
                task.finished_at = datetime.utcnow()
                doc.index_status = "indexed"
                doc.extraction_progress = 100
                doc.index_finished_at = datetime.utcnow()
                doc.index_error = None

                if result.get("stats"):
                    doc.entity_count = result["stats"].get("entities_total", 0)
                    doc.relation_count = result["stats"].get("relations_total", 0)
                
                # 广播最终完成状态给前端
                final_progress = IndexProgress(
                    current_phase="completed",
                    extraction_progress=100,
                    entities_total=doc.entity_count or 0,
                    entities_done=doc.entity_count or 0,
                    relations_total=doc.relation_count or 0,
                    relations_done=doc.relation_count or 0,
                )
                await cls._broadcast_progress(task_id, doc.id, final_progress)
            else:
                task.status = "failed"
                task.finished_at = datetime.utcnow()
                task.error_message = result.get("error", "未知错误")
                doc.index_status = "failed"
                doc.index_error = task.error_message
                
                # 广播失败状态给前端
                fail_progress = IndexProgress(current_phase="failed", extraction_progress=0)
                await cls._broadcast_progress(task_id, doc.id, fail_progress)

            db.commit()
            cls._current_task_id = None

            return result

        except Exception as e:
            import traceback
            logger.error(f"[IndexService] 任务处理异常: {e}\n{traceback.format_exc()}")
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
            # 循环处理直到队列为空
            while True:
                db = SessionLocal()
                pending_tasks = cls.get_pending_tasks(db, limit=1)
                db.close()
                
                if not pending_tasks:
                    logger.info("[IndexService] 队列已清空")
                    break
                
                task = pending_tasks[0]
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

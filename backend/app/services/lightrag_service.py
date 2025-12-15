"""LightRAG 服务封装

为永策Pro智能助手提供企业知识库检索能力。
支持混合检索模式（向量 + 知识图谱），涵盖永策Pro项目的全量文档。

配置说明：
- LLM：复用系统激活的 AI 模型配置
- Embedding：暂时硬编码（后续可迁移到数据库配置）
- Neo4j：复用系统的 neo4j_client 配置
"""

import os
import re
import json
import asyncio
import logging
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session
from starlette.websockets import WebSocket
from functools import partial

from lightrag import LightRAG, QueryParam
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.rerank import cohere_rerank
from lightrag.utils import EmbeddingFunc

from backend.app.services.ai_model_service import AIModelService
from backend.app.db.neo4j_client import (
    DEFAULT_NEO4J_URI,
    DEFAULT_NEO4J_USER,
    DEFAULT_NEO4J_PASSWORD,
)
from backend.app.core.logger import logger
from backend.app.core.lightrag_config import (
    LIGHTRAG_WORKING_DIR,
    LIGHTRAG_WORKSPACE,
    EMBEDDING_MODEL,
    EMBEDDING_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_DIM,
    RERANK_MODEL,
    RERANK_API_KEY,
    RERANK_BASE_URL,
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


class LightRAGService:
    """LightRAG 服务单例
    
    封装 LightRAG 实例的创建和查询，提供统一的操作文档检索接口。
    
    配置策略：
    - LLM：从数据库获取当前激活的 AI 模型配置
    - Embedding：硬编码配置（未来可扩展到数据库）
    - Neo4j：复用系统统一配置
    """
    
    _instance: Optional[LightRAG] = None
    _db_session: Optional[Session] = None
    
    # 进度推送上下文（类变量，用于跨异步任务传递）
    _progress_websocket: Optional[WebSocket] = None
    _progress_tool_id: Optional[int] = None
    _progress_tool_name: Optional[str] = None
    
    @classmethod
    async def get_instance(cls, db: Session) -> LightRAG:
        """获取 LightRAG 单例实例（懒加载）
        
        Args:
            db: 数据库会话，用于获取 LLM 配置
        
        Returns:
            已初始化的 LightRAG 实例
        """
        if cls._instance is None:
            logger.info("[LightRAG] 开始初始化 LightRAG 实例...")
            cls._db_session = db
            cls._instance = await cls._create_instance(db)
            logger.info("[LightRAG] LightRAG 实例初始化完成")
        return cls._instance
    
    @classmethod
    async def _create_instance(cls, db: Session) -> LightRAG:
        """创建并初始化 LightRAG 实例
        
        Args:
            db: 数据库会话
        
        Returns:
            配置好的 LightRAG 实例
        """
        # 获取 LLM 配置（优先使用小任务模型，未配置则 fallback 到主力模型）
        try:
            task_model = AIModelService.get_task_active_model(db)
            llm_config = AIModelService.get_task_llm_config(db)
            if task_model:
                logger.info(f"[LightRAG] 使用小任务 LLM 配置: model={llm_config.model_name}")
            else:
                logger.info(f"[LightRAG] 未配置小任务模型，fallback 使用主力 LLM: model={llm_config.model_name}")
        except RuntimeError as e:
            logger.error(f"[LightRAG] 获取 LLM 配置失败: {e}")
            raise
        
        # 设置 Neo4j 环境变量（LightRAG 内部需要）
        os.environ["NEO4J_URI"] = DEFAULT_NEO4J_URI
        os.environ["NEO4J_USERNAME"] = DEFAULT_NEO4J_USER
        os.environ["NEO4J_PASSWORD"] = DEFAULT_NEO4J_PASSWORD
        os.environ["OPENAI_API_KEY"] = llm_config.api_key  # LightRAG 要求必须设置
        
        logger.info(f"[LightRAG] Neo4j 配置: uri={DEFAULT_NEO4J_URI}, workspace={LIGHTRAG_WORKSPACE}")
        
        # 确保工作目录存在
        os.makedirs(LIGHTRAG_WORKING_DIR, exist_ok=True)
        
        # 自定义 LLM 函数（复用系统配置）
        async def llm_func(prompt, system_prompt=None, history_messages=[], **kwargs):
            # 处理 base_url：LightRAG 的 openai_complete_if_cache 会自动加 /chat/completions
            base_url = llm_config.base_url
            
            # 自定义网关模式
            if llm_config.provider_type == "custom_gateway" and llm_config.gateway_endpoint:
                base_url = llm_config.gateway_endpoint.rstrip("/")
                
                # LightRAG 会自动追加 /chat/completions，因此如果 endpoint 已经包含了该路径，需要移除
                if base_url.endswith("/chat/completions"):
                    base_url = base_url[:-17]  # len("/chat/completions") == 17
                elif base_url.endswith("/chat/completions/"):
                    base_url = base_url[:-18]
                
                # 确保以 /v1 结尾（但不包含 /chat/completions）
                if not base_url.endswith("/v1"):
                    base_url = base_url + "/v1"
            
            return await openai_complete_if_cache(
                model=llm_config.model_name,
                prompt=prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                api_key=llm_config.api_key,
                base_url=base_url,
                **kwargs
            )
        
        # 自定义 Embedding 函数（使用统一配置）
        async def embedding_func(texts: list[str]):
            logger.debug(f"[LightRAG] Embedding: {len(texts)} texts, model={EMBEDDING_MODEL}")
            
            # 🔥 主动推送 Embedding 进度
            ws = cls._progress_websocket
            tool_id = cls._progress_tool_id
            tool_name = cls._progress_tool_name
            if ws and tool_id is not None:
                try:
                    loop = asyncio.get_running_loop()
                    # 根据文本数量调整描述
                    if len(texts) == 1:
                        detail = "正在分析文本语义..."
                    else:
                        detail = f"正在处理 {len(texts)} 段内容..."
                    
                    asyncio.run_coroutine_threadsafe(
                        cls._send_progress(ws, tool_name, tool_id, "embedding", detail),
                        loop
                    )
                except RuntimeError:
                    pass
            
            return await openai_embed(
                texts,
                model=EMBEDDING_MODEL,
                api_key=EMBEDDING_API_KEY,
                base_url=EMBEDDING_BASE_URL,
            )
        
        # 配置 Rerank 函数（硅基流动平台，兼容 Cohere API）
        rerank_func = partial(
            cohere_rerank,
            model=RERANK_MODEL,
            api_key=RERANK_API_KEY,
            base_url=RERANK_BASE_URL,
        )
        logger.info(f"[LightRAG] Rerank 配置: model={RERANK_MODEL}")
        
        # 配置 LightRAG 的内部日志级别
        cls._configure_lightrag_logging()
        
        # 创建 LightRAG 实例
        rag = LightRAG(
            working_dir=LIGHTRAG_WORKING_DIR,
            workspace=LIGHTRAG_WORKSPACE,
            
            # LLM 配置
            llm_model_func=llm_func,
            
            # Embedding 配置
            embedding_func=EmbeddingFunc(
                embedding_dim=EMBEDDING_DIM,
                max_token_size=8192,
                func=embedding_func,
            ),
            
            # Rerank 配置
            rerank_model_func=rerank_func,
            
            # 存储配置
            graph_storage=GRAPH_STORAGE,
            vector_storage=VECTOR_STORAGE,
            kv_storage=KV_STORAGE,
            doc_status_storage=DOC_STATUS_STORAGE,
            
            # 性能参数
            chunk_token_size=CHUNK_TOKEN_SIZE,
            chunk_overlap_token_size=CHUNK_OVERLAP_TOKEN_SIZE,
            embedding_batch_num=EMBEDDING_BATCH_NUM,
            embedding_func_max_async=EMBEDDING_FUNC_MAX_ASYNC,
            llm_model_max_async=LLM_MODEL_MAX_ASYNC,
            
            # 语言配置
            addon_params={
                "language": "Chinese",
            },
        )
        
        # 初始化存储
        await rag.initialize_storages()
        
        # 初始化 pipeline 状态（重要！）
        try:
            from lightrag.kg.shared_storage import initialize_pipeline_status
            await initialize_pipeline_status()
            logger.debug("[LightRAG] Pipeline 状态初始化完成")
        except ImportError:
            logger.warning("[LightRAG] 无法导入 initialize_pipeline_status，跳过")
        except Exception as e:
            logger.warning(f"[LightRAG] Pipeline 状态初始化失败: {e}")
        
        logger.info(
            f"[LightRAG] 存储初始化完成: "
            f"working_dir={LIGHTRAG_WORKING_DIR}, "
            f"workspace={LIGHTRAG_WORKSPACE}, "
            f"llm={llm_config.model_name}, "
            f"embedding={EMBEDDING_MODEL}, "
            f"rerank={RERANK_MODEL}"
        )
        
        return rag
    
    @classmethod
    def _configure_lightrag_logging(cls):
        """配置 LightRAG 内部日志，使其输出到我们的 logger
        
        LightRAG 内部使用标准的 logging 模块，我们将其日志
        桥接到系统的 loguru logger，同时解析阶段信息用于进度追踪。
        """
        # 获取 LightRAG 的 logger
        lightrag_logger = logging.getLogger("lightrag")
        
        # 设置日志级别
        lightrag_logger.setLevel(logging.INFO)
        
        # 清除现有 handlers，避免重复输出
        lightrag_logger.handlers.clear()
        
        # 添加自定义 handler，桥接到 loguru 并解析阶段
        class LoguruHandler(logging.Handler):
            """将 logging 日志桥接到 loguru，同时解析阶段信息并推送 WebSocket 进度"""
            
            def emit(self, record):
                # 获取对应的 loguru 级别
                try:
                    level = logger.level(record.levelname).name
                except ValueError:
                    level = record.levelno
                
                # 格式化消息
                message = self.format(record)
                
                # 解析阶段信息并推送 WebSocket
                phase_info = cls._parse_lightrag_phase(message)
                if phase_info:
                    phase, detail = phase_info
                    logger.info(f"[LightRAG:Phase] 阶段={phase}, 详情={detail}")
                    
                    # 尝试推送 WebSocket 进度消息（使用类变量）
                    ws = cls._progress_websocket
                    tool_id = cls._progress_tool_id
                    tool_name = cls._progress_tool_name
                    logger.info(f"[LightRAG:Phase] 进度上下文: ws={ws is not None}, tool_id={tool_id}, tool_name={tool_name}")
                    if ws and tool_id is not None:
                        try:
                            # 获取事件循环并创建任务发送消息
                            loop = asyncio.get_running_loop()
                            logger.info(f"[LightRAG:Phase] 准备推送进度: phase={phase}")
                            asyncio.run_coroutine_threadsafe(
                                cls._send_progress(ws, tool_name, tool_id, phase, detail),
                                loop
                            )
                        except RuntimeError as e:
                            # 没有运行中的事件循环，跳过推送
                            logger.warning(f"[LightRAG:Phase] 无法获取事件循环: {e}")
                    else:
                        logger.debug(f"[LightRAG:Phase] 跳过推送: ws或tool_id未设置")
                
                # 输出到 loguru（添加 [LightRAG] 前缀）
                logger.opt(depth=6, exception=record.exc_info).log(
                    level, f"[LightRAG] {message}"
                )
        
        handler = LoguruHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        lightrag_logger.addHandler(handler)
        
        # 阻止向上传播到 root logger
        lightrag_logger.propagate = False
        
        logger.debug("[LightRAG] 已配置 LightRAG 内部日志桥接")
    
    @classmethod
    def _parse_lightrag_phase(cls, message: str) -> tuple[str, str] | None:
        """解析 LightRAG 日志中的阶段信息
        
        Args:
            message: LightRAG 的日志消息
            
        Returns:
            (phase, detail) 元组，或 None 表示不是阶段日志
        """
        # 🔥 新增：Workers 初始化
        match = re.search(r'(LLM|Embedding) func: (\d+) new workers initialized', message)
        if match:
            worker_type = "智能分析" if match.group(1) == "LLM" else "文本处理"
            return ("init_workers", f"准备{worker_type}引擎...")
        
        # 🔥 新增：关键词提取开始（捕获LLM请求）
        if 'keyword extractor' in message.lower() and 'User Query:' in message:
            return ("extracting_keywords", "正在理解您的问题...")
        
        # 🔥 新增：关键词提取完成
        if ' == LLM cache == saving:' in message and ':keywords:' in message:
            return ("keywords_extracted", "已识别问题要点")
        
        # 🔥 新增：Query nodes（实体查询）
        match = re.search(r'Query nodes: ([^(]+) \(top_k:(\d+)', message)
        if match:
            keywords = match.group(1).strip()
            # 截断关键词显示
            keywords_short = keywords[:20] + '...' if len(keywords) > 20 else keywords
            return ("querying_entities", f"查找与 \"{keywords_short}\" 相关的内容")
        
        # 🔥 新增：Query edges（关系查询）
        match = re.search(r'Query edges: ([^(]+) \(top_k:(\d+)', message)
        if match:
            return ("querying_relations", "分析内容之间的关联...")
        
        # 🔥 新增：Naive query（纯向量检索）
        match = re.search(r'Naive query: (\d+) chunks', message)
        if match:
            chunk_count = match.group(1)
            return ("vector_search", f"找到 {chunk_count} 段相关内容")
        
        # Local query 阶段
        match = re.match(r'Local query: (\d+) entites?, (\d+) relations?', message)
        if match:
            total = int(match.group(1)) + int(match.group(2))
            return ("local_query", f"已定位 {total} 条相关信息")
        
        # Global query 阶段
        match = re.match(r'Global query: (\d+) entites?, (\d+) relations?', message)
        if match:
            total = int(match.group(1)) + int(match.group(2))
            return ("global_query", f"扩展搜索，累计 {total} 条信息")
        
        # Rerank 阶段
        match = re.match(r'Successfully reranked: (\d+) chunks from (\d+)', message)
        if match:
            selected = match.group(1)
            return ("rerank", f"从海量内容中精选出最相关的 {selected} 条")
        
        # Final context 阶段
        match = re.match(r'Final context: (\d+) entities?, (\d+) relations?, (\d+) chunks?', message)
        if match:
            chunks = match.group(3)
            return ("finalize", f"正在整理 {chunks} 条内容为您准备答案")
        
        # Raw search results（检索完成）
        match = re.match(r'Raw search results: (\d+) entities?, (\d+) relations?, (\d+) vector chunks?', message)
        if match:
            chunks = match.group(3)
            return ("search_complete", f"检索完成，共找到 {chunks} 段相关内容")
        
        # 🔥 新增：Selecting chunks (向量相似度筛选)
        match = re.search(r'Selecting (\d+) from (\d+) (entity|relation)-related chunks', message)
        if match:
            selected = match.group(1)
            total = match.group(2)
            return ("selecting_chunks", f"从 {total} 条中筛选出 {selected} 条最相关内容")
        
        return None
    
    @classmethod
    async def _send_progress(cls, ws: WebSocket, tool_name: str, tool_id: int, phase: str, detail: str):
        """发送 tool_progress 消息到 WebSocket
        
        Args:
            ws: WebSocket 连接
            tool_name: 工具名称
            tool_id: 工具占位符 ID
            phase: 阶段名称
            detail: 阶段详情
        """
        try:
            await ws.send_text(json.dumps({
                "type": "tool_progress",
                "tool_name": tool_name,
                "tool_id": tool_id,
                "phase": phase,
                "detail": detail,
            }, ensure_ascii=False))
            logger.debug(f"[LightRAG] 已推送进度: phase={phase}")
        except Exception as e:
            logger.warning(f"[LightRAG] 推送进度失败: {e}")
    
    @classmethod
    def set_progress_context(cls, ws: Optional[WebSocket], tool_id: Optional[int], tool_name: Optional[str] = None):
        """设置进度推送的上下文
        
        在工具执行前调用，设置 WebSocket 和 tool_id，
        使得 LightRAG 内部日志捕获时能推送进度消息。
        
        Args:
            ws: WebSocket 连接，None 表示清除
            tool_id: 工具占位符 ID
            tool_name: 工具名称
        """
        cls._progress_websocket = ws
        cls._progress_tool_id = tool_id
        cls._progress_tool_name = tool_name
    
    @classmethod
    def clear_progress_context(cls):
        """清除进度推送的上下文"""
        cls._progress_websocket = None
        cls._progress_tool_id = None
        cls._progress_tool_name = None
    
    @classmethod
    def invalidate(cls) -> None:
        """清除 LightRAG 单例实例
        
        用于 LLM 配置变更后强制重建实例，确保使用新的 LLM 配置。
        下次调用 get_instance() 时会自动重新创建实例。
        """
        if cls._instance is not None:
            logger.info("[LightRAG] 清除实例缓存，下次请求将使用新 LLM 配置重建")
            cls._instance = None
            cls._db_session = None
        else:
            logger.debug("[LightRAG] 实例未初始化，无需清除")
    
    @classmethod
    async def warmup(cls, db: Session) -> None:
        """预热 LightRAG 实例
        
        在应用启动时调用，提前初始化 LightRAG 实例，避免首次查询时等待。
        
        Args:
            db: 数据库会话
        """
        try:
            logger.info("[LightRAG] 开始预热...")
            await cls.get_instance(db)
            logger.info("[LightRAG] 预热完成，实例已就绪")
        except Exception as e:
            logger.warning(f"[LightRAG] 预热失败（首次查询时会自动初始化）: {e}")
    
    @classmethod
    async def search_context(cls, question: str, db: Session, mode: str = "mix") -> dict:
        """检索永策Pro企业知识库上下文（只返回检索结果，不生成回答）
        
        使用 LightRAG 的多种检索模式检索永策Pro项目的相关文档内容。
        
        Args:
            question: 用户问题，如 "权限管理功能说明"、"订单流程设计"
            mode: 检索模式，可选值：
                  - naive: 纯向量检索（最快）
                  - local: 实体中心图谱检索（常用）
                  - global: 关系中心图谱检索
                  - hybrid: 深度图谱推理（最全）
                  - mix: 平衡模式（默认，推荐）
            
        Returns:
            {
                "context": "检索到的文档内容...",
                "sources": ["文档1", "文档2"]  # 来源文档列表
            }
        """
        try:
            rag = await cls.get_instance(db)
            
            logger.info(f"[LightRAG] 开始检索: question={question[:50]}..., mode={mode}")
            
            # 🔥 立即推送开始检索的进度
            ws = cls._progress_websocket
            tool_id = cls._progress_tool_id
            tool_name = cls._progress_tool_name
            if ws and tool_id is not None:
                try:
                    # 截断问题显示，更简洁友好
                    question_short = question[:15] + '...' if len(question) > 15 else question
                    await cls._send_progress(
                        ws, tool_name, tool_id,
                        "start_search",
                        f"开始为您查找关于「{question_short}」的信息"
                    )
                except Exception as e:
                    logger.warning(f"[LightRAG] 推送开始进度失败: {e}")
            
            # 根据模式动态调整 chunk_top_k
            chunk_top_k_map = {
                "naive": 20,    # 纯向量，少一些
                "local": 30,    # 局部图谱
                "global": 40,   # 全局图谱
                "hybrid": 50,   # 深度分析，多一些
                "mix": 40,      # 平衡模式
            }
            chunk_top_k = chunk_top_k_map.get(mode, 40)
            
            # 调用 LightRAG 查询（only_need_context=True 只返回检索结果）
            context = await rag.aquery(
                question,
                param=QueryParam(
                    mode=mode,
                    only_need_context=True,  # 只返回上下文，不生成回答
                    chunk_top_k=chunk_top_k
                )
            )
            
            # 检查返回结果是否为 None（查询失败）
            if context is None:
                logger.error(f"[LightRAG] 查询返回 None，可能是 LLM 调用失败")
                return {
                    "context": "",
                    "sources": [],
                    "error": "LLM 调用失败，请检查 LLM 配置"
                }
            
            if not context:
                logger.warning(f"[LightRAG] 检索结果为空")
                return {
                    "context": "",
                    "sources": []
                }
            
            # 提取来源文档
            sources = cls._extract_sources(context)
            
            logger.info(f"[LightRAG] 检索完成: context_length={len(context)}, sources={len(sources)}")
            
            return {
                "context": context,
                "sources": sources
            }
        
        except Exception as e:
            logger.error(f"[LightRAG] 检索失败: {e}")
            return {
                "context": "",
                "sources": [],
                "error": str(e),
            }
    
    @classmethod
    def _extract_sources(cls, context: str) -> list[dict]:
        """从 context 中提取 LightRAG 的 Reference Document List
        
        LightRAG 在 context 末尾会附加 Reference Document List，格式如：
        [1] 文档名称 (https://xxx/doc/ABC123)
        [2] 另一个文档 (https://xxx/doc/DEF456)
        
        Args:
            context: LightRAG 返回的上下文文本
            
        Returns:
            去重后的来源文档列表，每个元素为 {"name": "文档名", "url": "文档地址"}
        """
        sources = []
        seen = set()
        
        # 格式: [数字] 文档名称 (URL)
        matches = re.findall(r'\[\d+\]\s*([^(\n]+?)\s*\((https?://[^)]+)\)', context)
        for name, url in matches:
            name = name.strip()
            url = url.strip()
            if url not in seen:
                seen.add(url)
                sources.append({"name": name, "url": url})
        
        return sources
    

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
import logging
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session
from lightrag import LightRAG, QueryParam
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import EmbeddingFunc

from backend.app.services.ai_model_service import AIModelService
from backend.app.db.neo4j_client import (
    DEFAULT_NEO4J_URI,
    DEFAULT_NEO4J_USER,
    DEFAULT_NEO4J_PASSWORD,
)
from backend.app.core.logger import logger


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
    
    # 基础配置 - 使用绝对路径指向 test/lightrag_data
    # 获取项目根目录（backend/app/services -> backend -> 项目根）
    _PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
    WORKING_DIR = str(_PROJECT_ROOT / "test" / "lightrag_data")
    WORKSPACE = "opdoc"  # Neo4j 数据隔离标识（label 前缀）
    
    # Embedding 配置（暂时硬编码，后续可迁移到 AIModel 表）
    # TODO: 考虑添加 EmbeddingModel 配置表
    EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-8B"
    EMBEDDING_API_KEY = "sk-vxyvdnryevgolxatlsqilklzpiyfadxpkkqpvsagrgvuzavi"
    EMBEDDING_BASE_URL = "https://api.siliconflow.cn/v1"
    EMBEDDING_DIM = 4096
    
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
        # 获取系统激活的 LLM 配置
        try:
            llm_config = AIModelService.get_active_llm_config(db)
            logger.info(f"[LightRAG] 使用系统 LLM 配置: model={llm_config.model_name}")
        except RuntimeError as e:
            logger.error(f"[LightRAG] 获取 LLM 配置失败: {e}")
            raise
        
        # 设置 Neo4j 环境变量（LightRAG 内部需要）
        os.environ["NEO4J_URI"] = DEFAULT_NEO4J_URI
        os.environ["NEO4J_USERNAME"] = DEFAULT_NEO4J_USER
        os.environ["NEO4J_PASSWORD"] = DEFAULT_NEO4J_PASSWORD
        os.environ["OPENAI_API_KEY"] = llm_config.api_key  # LightRAG 要求必须设置
        
        logger.info(f"[LightRAG] Neo4j 配置: uri={DEFAULT_NEO4J_URI}, workspace={cls.WORKSPACE}")
        
        # 确保工作目录存在
        os.makedirs(cls.WORKING_DIR, exist_ok=True)
        
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
        
        # 自定义 Embedding 函数（使用硬编码配置）
        async def embedding_func(texts: list[str]):
            logger.debug(f"[LightRAG] Embedding: {len(texts)} texts, model={cls.EMBEDDING_MODEL}")
            return await openai_embed(
                texts,
                model=cls.EMBEDDING_MODEL,
                api_key=cls.EMBEDDING_API_KEY,
                base_url=cls.EMBEDDING_BASE_URL,
            )
        
        # 配置 LightRAG 的内部日志级别
        cls._configure_lightrag_logging()
        
        # 创建 LightRAG 实例
        rag = LightRAG(
            working_dir=cls.WORKING_DIR,
            workspace=cls.WORKSPACE,  # 数据隔离标识（Neo4j label前缀）
            
            # LLM 配置
            llm_model_func=llm_func,
            
            # Embedding 配置
            embedding_func=EmbeddingFunc(
                embedding_dim=cls.EMBEDDING_DIM,
                max_token_size=8192,
                func=embedding_func,
            ),
            
            # 存储配置
            graph_storage="Neo4JStorage",  # 复用现有 Neo4j
            vector_storage="NanoVectorDBStorage",  # 轻量向量库
            kv_storage="JsonKVStorage",
            doc_status_storage="JsonDocStatusStorage",
            
            # 性能参数
            chunk_token_size=1200,
            chunk_overlap_token_size=100,
            embedding_batch_num=8,
            embedding_func_max_async=1,  # 避免并发过高
            llm_model_max_async=6,
            
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
            f"working_dir={cls.WORKING_DIR}, "
            f"workspace={cls.WORKSPACE}, "
            f"llm={llm_config.model_name}, "
            f"embedding={cls.EMBEDDING_MODEL}"
        )
        
        return rag
    
    @classmethod
    def _configure_lightrag_logging(cls):
        """配置 LightRAG 内部日志，使其输出到我们的 logger
        
        LightRAG 内部使用标准的 logging 模块，我们将其日志
        桥接到系统的 loguru logger。
        """
        # 获取 LightRAG 的 logger
        lightrag_logger = logging.getLogger("lightrag")
        
        # 设置日志级别
        lightrag_logger.setLevel(logging.INFO)
        
        # 清除现有 handlers，避免重复输出
        lightrag_logger.handlers.clear()
        
        # 添加自定义 handler，桥接到 loguru
        class LoguruHandler(logging.Handler):
            """将 logging 日志桥接到 loguru"""
            
            def emit(self, record):
                # 获取对应的 loguru 级别
                try:
                    level = logger.level(record.levelname).name
                except ValueError:
                    level = record.levelno
                
                # 格式化消息
                message = self.format(record)
                
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
    async def search_context(cls, question: str, db: Session) -> dict:
        """检索永策Pro企业知识库上下文（只返回检索结果，不生成回答）
        
        使用 LightRAG 的混合检索模式（向量 + 图谱）检索永策Pro项目的相关文档内容。
        
        Args:
            question: 用户问题，如 "权限管理功能说明"、"订单流程设计"
            
        Returns:
            {
                "context": "检索到的文档内容...",
                "sources": ["文档1", "文档2"]  # 来源文档列表
            }
        """
        try:
            rag = await cls.get_instance(db)
            
            logger.info(f"[LightRAG] 开始检索: question={question[:50]}...")
            
            # 调用 LightRAG 查询（only_need_context=True 只返回检索结果）
            context = await rag.aquery(
                question,
                param=QueryParam(
                    mode="hybrid",  # 向量 + 图谱混合检索
                    only_need_context=True,  # 只返回上下文，不生成回答
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
            
            logger.info(f"[LightRAG] 检索完成: context_length={len(context)}")
            
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
    def _extract_sources(cls, context: str) -> list[str]:
        """从 context 中提取文档来源标识
        
        LightRAG 在索引时会保留 [DOC_ID:xxx] 和 [TITLE:xxx] 标记，
        这里通过正则提取这些标记作为来源引用。
        
        Args:
            context: LightRAG 返回的上下文文本
            
        Returns:
            去重后的来源文档列表
        """
        # 提取 [DOC_ID:xxx] 标记
        doc_ids = re.findall(r'\[DOC_ID:([^\]]+)\]', context)
        
        # 提取 [TITLE:xxx] 标记
        titles = re.findall(r'\[TITLE:([^\]]+)\]', context)
        
        # 合并去重
        sources = list(set(doc_ids + titles))
        
        return sources

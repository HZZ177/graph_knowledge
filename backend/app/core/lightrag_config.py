"""
LightRAG 统一配置模块

集中管理 LightRAG 相关配置，供 lightrag_service 和 lightrag_index_service 共用。

配置策略：
- 工作目录：backend/data/lightrag
- Workspace：opdoc（Neo4j 数据隔离标识）
- Neo4j：复用 neo4j_client 配置
- LLM：复用系统的 task model 配置
- Embedding：暂时硬编码（后续可扩展到数据库）
"""

from pathlib import Path


# ============== 路径配置 ==============

# 项目根目录（backend 的父目录）
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# LightRAG 数据存储目录
# 规范化路径：从 test/lightrag_data 迁移到 backend/data/lightrag
LIGHTRAG_WORKING_DIR = str(_PROJECT_ROOT / "backend" / "data" / "lightrag")

# 数据隔离标识（Neo4j label 前缀）
LIGHTRAG_WORKSPACE = "opdoc"


# ============== Embedding 配置 ==============
# 暂时硬编码，后续可扩展到数据库配置

EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-8B"
EMBEDDING_API_KEY = "sk-vxyvdnryevgolxatlsqilklzpiyfadxpkkqpvsagrgvuzavi"
EMBEDDING_BASE_URL = "https://api.siliconflow.cn/v1"
EMBEDDING_DIM = 4096


# ============== Rerank 配置 ==============
# 硅基流动平台，兼容 Cohere API

RERANK_MODEL = "Qwen/Qwen3-Reranker-8B"
RERANK_API_KEY = "sk-vxyvdnryevgolxatlsqilklzpiyfadxpkkqpvsagrgvuzavi"
RERANK_BASE_URL = "https://api.siliconflow.cn/v1/rerank"


# ============== 性能参数 ==============

CHUNK_TOKEN_SIZE = 1200
CHUNK_OVERLAP_TOKEN_SIZE = 100
EMBEDDING_BATCH_NUM = 8
EMBEDDING_FUNC_MAX_ASYNC = 1  # 硅基流动 RPM 限制较严格
LLM_MODEL_MAX_ASYNC = 3  # 图谱并发 = 此值 * 2，Neo4j Aura 限制需保持较低


# ============== 存储类型 ==============

KV_STORAGE = "JsonKVStorage"
VECTOR_STORAGE = "NanoVectorDBStorage"
GRAPH_STORAGE = "Neo4JStorage"
DOC_STATUS_STORAGE = "JsonDocStatusStorage"


# ============== 多模态配置 ==============

# 是否启用图片内容理解（VLM）
ENABLE_IMAGE_UNDERSTANDING = True

# 图片理解 Prompt 模板
IMAGE_UNDERSTANDING_PROMPT = """请描述这张图片的内容，用于帮助理解文档。

【文档标题】
{doc_title}

【图片位置的上下文】
{context}

【图片标题】
{alt_text}

【要求】
1. 描述图片展示的功能、操作流程或概念，而非具体数据
2. 不要提取截图中的示例数据（如用户名、编号、具体数值等），用"某某"或"示例数据"替代
3. 重点说明界面的用途和操作方式
4. 如果是流程图，说明步骤逻辑和流向
5. 如果是架构图，说明各模块的职责和关系
6. 用中文回答，100-200字
7. 不要使用任何符号或图标
"""

# 图片上下文提取配置
IMAGE_CONTEXT_MAX_CHARS = 300  # 提取图片前后最多300字符作为上下文

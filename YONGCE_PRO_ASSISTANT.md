# 永策Pro智能助手 - 系统架构说明

---

## 一、系统整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              前端 (React 18 + TypeScript + Vite)             │
├─────────────────────────────────────────────────────────────────────────────┤
│  ChatPage     │  DocCenterPage  │  BusinessLibraryPage  │  LLMModelManage   │
│  AI对话(WS)   │   文档中心       │   ReactFlow画布       │    模型配置        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │ REST API         WebSocket    │
                    ▼                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          后端 (FastAPI + Uvicorn)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  API Layer:  llm_chat  │  doc_center  │  canvas  │  graph  │  llm_models    │
├─────────────────────────────────────────────────────────────────────────────┤
│  Service:  chat_service │ doc_center_service │ lightrag_service/index_service │
├─────────────────────────────────────────────────────────────────────────────┤
│  Agent:  knowledge_qa │ log_troubleshoot │ intelligent_testing │ opdoc_qa   │
└─────────────────────────────────────────────────────────────────────────────┘
                    │                     │                      │
        ┌───────────┴──────┐              │              ┌───────┴───────┐
        ▼                  ▼              ▼              ▼               ▼
   SQLite             Checkpointer     Neo4j         LightRAG        帮助中心MySQL
  (元数据)           (对话历史)       (知识图谱)     (文档索引)        (外部数据源)
```

### 技术栈

| 层级       | 技术                                                                                   |
|----------|--------------------------------------------------------------------------------------|
| **前端**   | React 18, TypeScript, Vite, Ant Design 5, @xyflow/react, @uiw/react-markdown-preview |
| **后端**   | FastAPI, Uvicorn, SQLAlchemy 2.0                                                     |
| **AI框架** | LangChain + LangGraph, CrewAI, LiteLLM                                               |
| **存储**   | SQLite (元数据), Neo4j 5.x (知识图谱), NanoVectorDB (向量)                                    |
| **外部服务** | 帮助中心 MySQL, OpenList OSS, 硅基流动 (Embedding/Rerank)                                    |

---

## 二、智能对话模块 (ChatPage)

### 2.1 Agent 类型分流

系统支持四种 Agent 类型，通过 `backend/app/api/v1/llm_chat.py` 进行路由分发：

| Agent类型                 | 功能     | 特点                                            |
|-------------------------|--------|-----------------------------------------------|
| **knowledge_qa**        | 业务知识问答 | 基于 Neo4j 知识图谱，16个工具                           |
| **log_troubleshoot**    | 日志排查   | 需要业务线/私有化配置，12个工具                             |
| **intelligent_testing** | 智能测试   | 三阶段工作流(analysis→plan→generate)，每阶段独立thread_id |
| **opdoc_qa**            | 操作文档问答 | **基于 LightRAG**，混合检索(向量+图谱)                   |

### 2.2 对话数据流

```
用户提问
    │
    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  ChatPage.tsx (前端)                                                          │
│  - WebSocket 连接: createChatClient()                                         │
│  - 消息状态管理: DisplayMessage[]                                              │
│  - 工具调用跟踪: ActiveToolInfo / ToolProgressStep                            │
│  - 流式渲染: useTypewriter() / MemoizedMarkdown                               │
└──────────────────────────────────────────────────────────────────────────────┘
    │ WebSocket (StreamChatRequest)
    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  llm_chat.py → 根据 agent_type 分流                                           │
│  - _handle_knowledge_qa()                                                     │
│  - _handle_opdoc_qa()        ← 调用 LightRAG 检索                             │
│  - _handle_log_troubleshoot()                                                 │
│  - _handle_intelligent_testing()                                              │
└──────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  chat_service.streaming_chat()                                                │
│  - AgentRegistry.get_agent()  → LangGraph Agent (ReAct Loop)                  │
│  - 流式推送: tool_start → tool_end → stream → result                          │
│  - Checkpointer 持久化对话历史                                                 │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 WebSocket 消息协议

```json
// 服务端推送消息类型
{
  "type": "start",
  "request_id": "...",
  "thread_id": "..."
}
{
  "type": "tool_start",
  "tool_name": "search_opdoc_context",
  "tool_id": 1
}
{
  "type": "tool_progress",
  "tool_name": "...",
  "phase": "local_query",
  "detail": "..."
}
{
  "type": "tool_end",
  "tool_name": "...",
  "tool_id": 1,
  "result": "..."
}
{
  "type": "stream",
  "content": "回答内容片段..."
}
{
  "type": "result",
  "thread_id": "...",
  "content": "完整回答"
}
{
  "type": "error",
  "error": "错误信息"
}
```

### 2.4 前端核心组件

| 组件                      | 路径                                                     | 功能          |
|-------------------------|--------------------------------------------------------|-------------|
| **ChatPage**            | `frontend/src/pages/ChatPage.tsx`                      | 主对话页面，状态管理  |
| **ChatInputArea**       | `frontend/src/components/chat/ChatInputArea.tsx`       | 输入框+文件上传    |
| **MessageItem**         | `frontend/src/components/chat/MessageItem.tsx`         | 消息渲染+工具调用显示 |
| **ConversationSidebar** | `frontend/src/components/chat/ConversationSidebar.tsx` | 历史会话列表      |
| **AgentSelectorHeader** | `frontend/src/components/chat/AgentSelectorHeader.tsx` | Agent类型切换   |

---

## 三、文档中心处理方式

### 3.1 数据模型

| 模型                     | 表名                       | 说明                                     |
|------------------------|--------------------------|----------------------------------------|
| **DocCenterFolder**    | `doc_center_folders`     | 目录节点，保持帮助中心的树状层级                       |
| **DocCenterDocument**  | `doc_center_documents`   | 文档节点，包含 sync_status / index_status 状态机 |
| **DocCenterIndexTask** | `doc_center_index_tasks` | 索引任务队列                                 |

### 3.2 文档同步流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           文档同步流程                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. 结构同步 (sync_structure_from_help_center)                               │
│     └─ MySQL 查询帮助中心 → 保存目录/文档元数据到 SQLite                       │
│                                                                              │
│  2. 内容同步 (sync_document)                                                 │
│     ├─ 获取分享URL → HelpCenterAPIClient.get_share_url()                    │
│     ├─ 获取文档内容(Markdown) → HelpCenterAPIClient.get_doc_content()       │
│     ├─ 图片处理:                                                             │
│     │   ├─ extract_image_urls() → 提取图片URL                               │
│     │   ├─ download_image() → 下载图片                                       │
│     │   └─ SimpleOSSClient.upload() → 上传到 OpenList OSS                   │
│     ├─ 图片内容理解(VLM增强):                                                 │
│     │   └─ call_vlm_for_image() → 调用 task_llm 生成图片描述                 │
│     └─ 保存到 SQLite: content, content_hash, sync_status=synced             │
│                                                                              │
│  状态流转: pending → syncing → synced (或 failed)                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 文档状态机

**同步状态 (sync_status)**:

```
pending ──(开始同步)──→ syncing ──(成功)──→ synced
                           │
                           └──(失败)──→ failed
```

**索引状态 (index_status)**:

```
pending ──(加入队列)──→ queued ──(开始索引)──→ indexing ──(成功)──→ indexed
                                                  │
                                                  └──(失败)──→ failed
```

### 3.4 前端页面 (DocCenterPage)

**两种模式**：

- **阅读模式**：左侧文件树 + 右侧 Markdown 文档阅读器
- **管理模式**：左侧文件树 + 右侧文档列表（批量同步、索引操作）

**核心功能**：

- 目录树搜索与展开
- 文档筛选（同步状态、索引状态、关键词）
- 批量操作（同步、索引）
- WebSocket 实时进度推送

---

## 四、LightRAG 处理流程

### 4.1 核心服务

| 服务                       | 文件                                               | 功能        |
|--------------------------|--------------------------------------------------|-----------|
| **LightRAGService**      | `backend/app/services/lightrag_service.py`       | 单例，封装查询接口 |
| **LightRAGIndexer**      | `backend/app/services/lightrag_index_service.py` | 文档索引器     |
| **LightRAGIndexService** | 同上                                               | 索引任务队列管理  |

### 4.2 配置策略

```python
# 配置文件: backend/app/core/lightrag_config.py

# LLM: 复用系统激活的 task_llm 配置
llm_config = AIModelService.get_task_llm_config(db)

# Embedding: 硅基流动平台
EMBEDDING_MODEL = "Pro/BAAI/bge-m3"
EMBEDDING_BASE_URL = "https://api.siliconflow.cn/v1"
EMBEDDING_DIM = 1024

# Rerank: Cohere 兼容 API (硅基流动)
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"

# 存储配置
GRAPH_STORAGE = "Neo4JStorage"  # 图谱存储
VECTOR_STORAGE = "NanoVectorDBStorage"  # 向量存储
KV_STORAGE = "JsonKVStorage"  # KV存储

# 分块参数
CHUNK_TOKEN_SIZE = 1200
CHUNK_OVERLAP_TOKEN_SIZE = 100
```

### 4.3 索引流程 (两阶段)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LightRAG 索引流程                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  阶段1: 提取阶段 (extraction)                                                │
│  ├─ 文档分块 (chunk_token_size=1200)                                        │
│  ├─ LLM 提取实体+关系                                                        │
│  └─ 日志: "Chunk X of Y extracted N Ent + M Rel"                            │
│                                                                              │
│  阶段2: 图谱构建 (graph_building)                                            │
│  ├─ Merging stage: 合并实体和关系                                            │
│  ├─ Embedding: 向量化实体/关系                                               │
│  └─ 写入 Neo4j 图谱 + 向量存储                                               │
│                                                                              │
│  进度追踪:                                                                    │
│  - 日志解析: ProgressLogHandler 捕获 LightRAG 内部日志                       │
│  - WebSocket 推送: IndexProgress → 前端 UnifiedProgress 组件                 │
│                                                                              │
│  文档标识: 索引时添加 [文档名称] [文档地址] 前缀，便于检索时提取来源            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.4 查询流程 (opdoc_qa Agent)

```
用户问题
    │
    ▼
LightRAGService.search_context(question)
    │
    ├─ 1. LightRAG.aquery(mode="mix", only_need_context=True)
    │      └─ 混合检索: 向量检索 + 知识图谱遍历
    │
    ├─ 2. Rerank: cohere_rerank() 重排序
    │
    └─ 3. 返回 {context, sources}
           └─ _extract_sources(): 从 Reference Document List 提取来源
    │
    ▼
Agent 根据 context 生成回答 → 流式返回前端
```

---

## 五、数据流转总结

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              完整数据流转                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ① 文档导入                                                                  │
│     帮助中心 MySQL ──(同步结构)──→ SQLite (DocCenterFolder/Document)         │
│                                                                              │
│  ② 内容同步                                                                  │
│     帮助中心 API ──(获取MD)──→ 图片处理 ──→ VLM增强 ──→ SQLite.content        │
│                                    │                                         │
│                                    └─→ OSS (图片永久存储)                    │
│                                                                              │
│  ③ 知识索引                                                                  │
│     SQLite.content ──(LightRAG)──→ Neo4j (实体/关系)                         │
│                                  └─→ NanoVectorDB (向量)                     │
│                                                                              │
│  ④ 智能问答                                                                  │
│     用户问题 ──(WebSocket)──→ Agent 路由                                     │
│                                   │                                          │
│               ┌───────────────────┼───────────────────┐                      │
│               ▼                   ▼                   ▼                      │
│          knowledge_qa        opdoc_qa           其他 Agent                   │
│          (Neo4j 图谱)       (LightRAG)          (各自工具链)                  │
│               │                   │                   │                      │
│               └───────────────────┼───────────────────┘                      │
│                                   ▼                                          │
│                           流式回答 → 前端渲染                                 │
│                                                                              │
│  ⑤ 对话持久化                                                                │
│     LangGraph Checkpointer ──→ llm_checkpoints.db (SQLite)                  │
│     会话元数据 ──→ app.db (Conversation 表)                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 六、关键技术点

| 模块              | 技术                     | 说明                      |
|-----------------|------------------------|-------------------------|
| **前端对话**        | WebSocket + 流式渲染       | `useTypewriter()` 打字机效果 |
| **Agent 编排**    | LangGraph ReAct Loop   | 工具调用 + 多轮推理             |
| **LightRAG 检索** | 混合模式 (hybrid)          | 向量 + 图谱 + Rerank        |
| **进度追踪**        | 日志解析 + WebSocket       | 两阶段进度可视化                |
| **图片增强**        | VLM (task_llm)         | 图片→文字描述，提升检索质量          |
| **对话持久化**       | LangGraph Checkpointer | 多轮对话上下文保持               |
| **模型管理**        | LiteLLM + 自定义网关        | 统一多模型接口                 |

---

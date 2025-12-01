# Graph Knowledge - 业务知识图谱对话系统

基于 **LLM + Neo4j 图数据库** 的业务知识问答与可视化管理平台。通过自然语言对话探索企业业务流程、接口实现和数据资源之间的关联关系，探索代码细节实现等，规划后续提供日志排查，用例审查等功能

## 🎯 核心能力

- **智能对话问答**：基于 LangChain Agent，支持自然语言查询业务流程、接口依赖、数据资源使用情况，代码实现细节等
- **知识图谱可视化**：通过 React Flow 实现业务流程画布的拖拽编辑和关系连接
- **实体自动发现**：LLM 驱动的实体匹配，无需记忆 ID 即可定位目标
- **影响面分析**：追踪接口/数据资源的业务使用范围和上下游依赖
- **骨架自动生成**：基于crewai agent编排的辅助生成业务流程初始结构，支持自定义步骤、实现、数据资源
- **代码检索**：基于 MCP 实现代码级实现细节检索

## 📐 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    前端 (React + TypeScript)                     │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐    │
│  │  ChatPage │  │ Business  │  │ Resource  │  │ LLMModel  │    │
│  │  对话问答  │  │ Library   │  │ Library   │  │  Manage   │    │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │ REST / WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    后端 (FastAPI + LangChain)                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  LangChain Agent + 12 个工具                              │   │
│  │  ├── search_* (4个)    实体发现：业务/步骤/实现/数据资源    │   │
│  │  ├── get_*_context (3个) 上下文获取                       │   │
│  │  ├── get_*_usages (2个)  影响面分析                       │   │
│  │  ├── get_neighbors       邻居探索                         │   │
│  │  ├── get_path            路径查找                         │   │
│  │  └── search_code_context 代码检索                         │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         ┌─────────┐    ┌─────────┐    ┌─────────┐
         │ SQLite  │    │  Neo4j  │    │   LLM   │
         │(元数据) │    │(图查询) │    │ (推理)  │
         └─────────┘    └─────────┘    └─────────┘
```

## 🗂️ 项目结构

```
graph_knowledge/
├── backend/                    # 后端服务
│   ├── app/
│   │   ├── api/v1/            # REST & WebSocket 接口
│   │   │   ├── llm.py         # 对话 & 骨架生成接口
│   │   │   ├── graph.py       # 图查询接口
│   │   │   ├── canvas.py      # 画布保存接口
│   │   │   ├── processes.py   # 业务流程 CRUD
│   │   │   └── resource_nodes.py  # 资源节点管理
│   │   ├── llm/               # LLM 相关
│   │   │   ├── langchain_chat_agent.py   # Agent 配置 & System Prompt
│   │   │   ├── langchain_chat_tools.py   # 12 个工具实现
│   │   │   ├── base.py        # LLM 客户端封装
│   │   │   └── prompts.py     # Prompt 模板
│   │   ├── models/            # SQLAlchemy 数据模型
│   │   │   ├── resource_graph.py  # Business/Step/Implementation/DataResource
│   │   │   └── conversation.py    # 会话历史
│   │   ├── services/          # 业务逻辑层
│   │   │   ├── graph_service.py       # Neo4j 图查询
│   │   │   ├── graph_sync_service.py  # SQLite → Neo4j 同步
│   │   │   ├── llm_chat_service.py    # 流式对话服务
│   │   │   └── canvas_service.py      # 画布数据处理
│   │   ├── db/                # 数据库连接
│   │   │   ├── sqlite.py      # SQLite 配置
│   │   │   └── neo4j_client.py # Neo4j 驱动
│   │   └── main.py            # FastAPI 入口
│   └── requirements.txt
│
├── frontend/                   # 前端应用
│   ├── src/
│   │   ├── pages/             # 页面组件
│   │   │   ├── ChatPage.tsx           # AI 对话页面
│   │   │   ├── BusinessLibraryPage.tsx # 业务画布编辑器
│   │   │   ├── ResourceLibraryPage.tsx # 资源库管理
│   │   │   ├── LLMModelManagePage.tsx  # LLM 模型配置
│   │   │   └── HomePage.tsx           # 首页仪表盘
│   │   ├── api/               # API 封装
│   │   ├── components/        # 通用组件
│   │   ├── hooks/             # 自定义 Hooks
│   │   └── styles/            # 样式文件
│   └── package.json
│
├── test/                       # 测试脚本
└── LLM_Graph_Chat_Tools_Design.md  # 详细设计文档
```

## 🔧 技术栈

### 后端

| 组件     | 技术                    | 说明                  |
|--------|-----------------------|---------------------|
| Web 框架 | FastAPI               | 异步 REST + WebSocket |
| ORM    | SQLAlchemy 2.0        | SQLite 元数据存储        |
| 图数据库   | Neo4j 6.x             | 知识图谱存储与查询           |
| LLM 框架 | LangChain + LangGraph | Agent 编排 & 多轮对话     |
| LLM 调用 | LiteLLM               | 多模型统一接口             |
| 日志     | Loguru                | 结构化日志               |

### 前端

| 组件       | 技术                          | 说明          |
|----------|-----------------------------|-------------|
| 框架       | React 18 + TypeScript       | 类型安全的 UI 开发 |
| 构建工具     | Vite 5                      | 快速开发与构建     |
| UI 组件库   | Ant Design 5                | 企业级组件       |
| 流程图      | @xyflow/react               | 可视化画布编辑     |
| Markdown | @uiw/react-markdown-preview | 对话内容渲染      |
| 路由       | React Router 6              | SPA 路由管理    |

## 📊 数据模型

系统核心实体及其关系：

```
Business (业务流程)
    │
    ├── 1:N ──→ Step (业务步骤)
    │              │
    │              └── N:M ──→ Implementation (技术实现/接口)
    │                              │
    │                              └── N:M ──→ DataResource (数据资源/表)
    │
    └── ProcessStepEdge (步骤流转边)
```

### 核心实体

| 实体               | 主键            | 说明                    |
|------------------|---------------|-----------------------|
| `Business`       | `process_id`  | 业务流程，包含名称、渠道、描述       |
| `Step`           | `step_id`     | 业务步骤，如"用户提交申请"、"风控审核" |
| `Implementation` | `impl_id`     | 技术实现/接口，如 API、定时任务    |
| `DataResource`   | `resource_id` | 数据资源，如数据库表、缓存         |

### 关系类型

| 关系                           | 说明              |
|------------------------------|-----------------|
| `ProcessStepEdge`            | 步骤之间的流转顺序       |
| `StepImplementation`         | 步骤与实现的关联        |
| `ImplementationDataResource` | 实现对数据资源的访问（读/写） |
| `ImplementationLink`         | 实现之间的调用关系       |

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- Neo4j 5.x (可选，用于图查询增强)

### 后端启动

```bash

cd backend

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# 安装依赖
pip install uv
uv pip install -r requirements.txt

# 启动服务
运行main.py即可
```

### ACE_MCP

```bash

# 安装到系统
uv tool install acemcp

```

### 前端启动

```bash

cd frontend

# 安装依赖
npm install

# 开发模式
npm run dev
```

### Neo4j 配置（可选，暂时写死云端neo4j库）

1. 安装并启动 Neo4j Desktop 或 Docker 版本
2. 配置环境变量：
   ```bash
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_password
   ```

### LLM 配置

在前端 **LLM 模型管理** 页面配置模型：

- 支持 OpenAI、Azure OpenAI、本地 Ollama 等
- 兼容crewai和langchain统一调用接口
- 模型格式示例：`openai/gpt-4o-mini`、`ollama/qwen2.5:7b`

## 📖 功能说明

### 1. AI 对话问答 (`/chat`)

通过自然语言与知识图谱交互：

```
用户：开卡流程是什么？
助手：[思考] 用户想了解开卡相关的业务流程...
      [调用 search_businesses]
      
      找到以下相关业务流程：
      1. **月卡开通流程** - 用户在APP中开通会员卡
         - 包含5个步骤：身份验证 → 资格校验 → 支付处理 → 开卡确认 → 通知推送
         - 涉及系统：user-service, payment-service, card-service
```

### 2. 业务画布编辑器 (`/business`)

- 创建/编辑业务流程画布
- 拖拽添加步骤、实现、数据资源节点
- 连接节点建立关系
- 一键同步到 Neo4j

### 3. 资源库管理 (`/resources`)

管理四类资源节点：

- **业务流程**：顶层业务对象
- **步骤**：业务环节/节点
- **实现**：技术接口/服务
- **数据资源**：数据库表/缓存/文件

### 4. 骨架自动生成

通过 AI 自动生成业务流程初始结构：

1. 输入业务名称和描述
2. LLM 分析并生成步骤、实现、数据资源
3. 预览并确认后保存

## 🛠️ Agent 工具集

系统内置 12 个 LangChain 工具：

### 实体发现（4个）

| 工具                       | 说明      |
|--------------------------|---------|
| `search_businesses`      | 搜索业务流程  |
| `search_steps`           | 搜索业务步骤  |
| `search_implementations` | 搜索接口/实现 |
| `search_data_resources`  | 搜索数据资源  |

### 上下文获取（3个）

| 工具                           | 说明          |
|------------------------------|-------------|
| `get_business_context`       | 获取业务流程完整上下文 |
| `get_implementation_context` | 获取接口依赖与调用关系 |
| `get_resource_context`       | 获取数据资源访问情况  |

### 影响面分析（2个）

| 工具                                   | 说明          |
|--------------------------------------|-------------|
| `get_implementation_business_usages` | 接口的业务使用范围   |
| `get_resource_business_usages`       | 数据资源的业务使用范围 |

### 图拓扑（2个）

| 工具                          | 说明       |
|-----------------------------|----------|
| `get_neighbors`             | 获取节点邻居   |
| `get_path_between_entities` | 查找两实体间路径 |

### 代码检索（1个）

| 工具                   | 说明                |
|----------------------|-------------------|
| `search_code_context` | 代码级实现细节检索（依赖 MCP） |
| `list_directory`       | 目录列表              |
| `read_file`            | 文件读取              |
| `read_file_range`      | 文件范围读取            |

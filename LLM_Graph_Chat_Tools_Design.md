# LLM + 图数据对话工具设计方案

## 1. 目标与边界

### 1.1 目标

- 支持 **完全自由问答 + 自动工具调用** 的独立 Chat 页面。
- 让 LLM 能通过自然语言主动发现业务流程 / 实现 / 数据资源，并拉取对应图上下文，回答：
  - 这个流程 / 接口 / 表是什么？
  - 它在哪些流程里、和哪些系统 / 数据有关？
  - 它与另一个实体之间的路径 / 上下游关系。

### 1.2 前提

- 模型支持 function calling（通过 CrewAI 原生 Tool 机制）。
- 图数据已在 Neo4j 中建好，现有 `graph_service` 已提供：
  - `get_business_context(process_id)`
  - `get_implementation_context(impl_id)`
  - `get_resource_context(resource_id)`
  - 及若干路径 / 邻居查询能力（可按需扩展）。

### 1.3 设计原则

- **工具分两层**：
  - 实体发现类：`search_*`，负责自然语言 → 候选实体（带 ID）。
  - 上下文 / 拓扑类：`summarize_*` / `get_*_context` + 通用图工具（neighbors / path）。
- 工具按 **实体类型** 拆分：业务（Business）、实现（Implementation）、数据资源（DataResource）。
- **技术框架**：基于 CrewAI 原生 Tool（`BaseTool` 类继承方式），与项目现有架构保持一致。

## 2. 整体架构

### 2.1 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                    前端 ChatPage                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  消息列表 + 输入框 + 流式输出                             │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │ WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    后端 Chat Agent                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  CrewAI Agent + Tools                                    │   │
│  │  ├── search_businesses_tool                              │   │
│  │  ├── search_implementations_tool                         │   │
│  │  ├── search_data_resources_tool                          │   │
│  │  ├── get_business_context_tool                           │   │
│  │  ├── get_implementation_context_tool                     │   │
│  │  ├── get_resource_context_tool                           │   │
│  │  ├── get_neighbors_tool                                  │   │
│  │  └── get_path_tool                                       │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         ┌─────────┐    ┌─────────┐    ┌─────────┐
         │ SQLite  │    │  Neo4j  │    │   LLM   │
         │(实体列表)│    │(图查询) │    │ (选择)  │
         └─────────┘    └─────────┘    └─────────┘
```

### 2.2 文件清单

```
backend/app/
├── llm/
│   ├── chat_tools.py          # 🆕 8个 Tool 类定义
│   └── chat_agent.py          # 🆕 Chat Agent 配置
├── services/
│   └── llm_chat_service.py    # 修改: 新增 tool-based chat
├── api/v1/
│   └── llm.py                 # 修改: 新增 WebSocket endpoint

frontend/src/
├── pages/
│   └── ChatPage.tsx           # 🆕 独立 Chat 页面
├── api/
│   └── chat.ts                # 🆕 Chat API 封装
└── router.tsx                 # 修改: 添加路由
```

## 3. 实体发现方案（候选列表 + LLM 选择）

### 3.1 方案选型

经过评估，**放弃 embedding 检索方案**，改为 **候选列表 + 小 LLM 选择** 方案。

#### 方案对比

| 维度 | Embedding 检索 | 候选列表 + LLM 选择 |
|------|---------------|-------------------|
| 基础设施 | 需要向量数据库 | 无需额外设施 |
| 实现复杂度 | 高 | 低 |
| 运维成本 | 高 | 低 |
| 语义理解 | 向量相似度 | LLM 原生理解 |
| 同义词/别名 | 需要预处理 | LLM 天然支持 |
| 适用规模 | 大规模（万级以上） | 中小规模（千级以内） |

#### 选择理由

1. **实体规模有限**：业务流程通常几十到几百个，接口/资源几百到几千个，完全在 LLM context window 内。
2. **实现简单**：无需引入向量数据库，减少架构复杂度。
3. **效果更好**：LLM 原生理解能力强于向量相似度，可处理同义词、缩写、模糊描述。
4. **成本可控**：小模型（gpt-4o-mini / claude-3-haiku）即可胜任选择任务。

### 3.2 实现流程

```
用户输入: "开卡流程是什么"
        │
        ▼
┌─────────────────────────────────────────┐
│ 1. 从 SQLite 拉取所有 Business 实体      │
│    SELECT process_id, name, description │
│    FROM businesses                       │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│ 2. 构造候选列表字符串                     │
│    [1] 开通月卡 - 用户在App中开通会员卡   │
│    [2] 新用户注册 - 新用户首次注册流程    │
│    [3] ...                               │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│ 3. LLM 选择最匹配的候选                   │
│    输入: query + 候选列表                │
│    输出: 匹配的 process_id 列表          │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│ 4. 返回候选实体（带匹配原因）             │
│    { process_id, name, match_reason }   │
└─────────────────────────────────────────┘
```

### 3.3 数据模型

**无需新增 `search_text` 字段**，直接使用现有的 `name` + `description` 字段构造候选列表。

如果后续发现匹配效果不佳，可考虑：
- 在画布编辑/保存时，通过 LLM 自动生成更丰富的 `search_text` 描述
- 作为增强功能按需迭代

## 4. 工具总览

### 4.1 实体发现类（search_*）

作用：**自然语言 → 候选实体列表（带 ID）**。

- `search_businesses`
- `search_implementations`
- `search_data_resources`

### 4.2 上下文 / 拓扑类

按实体类型拆：

- 业务流程（Business）
  - `summarize_business`
  - `get_business_context_for_chat`
- 实现 / 接口（Implementation）
  - `summarize_implementation`
  - `get_implementation_context_for_chat`
- 数据资源（DataResource）
  - `summarize_data_resource`
  - `get_resource_context_for_chat`

通用图工具：

- `get_neighbors`
- `get_path_between_entities`

## 5. 实体发现类工具设计（基于 CrewAI BaseTool）

> 所有工具均使用 CrewAI `BaseTool` 类继承方式实现，便于复用 db session 和统一错误处理。

### 5.0 实体发现核心机制：候选列表 + 小 LLM 选择

实体发现工具采用**两阶段架构**，避免将全量实体数据传递给主 Chat Agent，有效控制 Token 消耗：

```
用户问题 → 主 Agent 调用 search_* 工具
                    ↓
            ┌───────────────────────────────────┐
            │  工具内部执行                      │
            │  1. 查询所有该类实体               │
            │  2. 构造候选列表文本               │
            │  3. 调用小 LLM 进行筛选            │
            │  4. 只返回精选结果                 │
            └───────────────────────────────────┘
                    ↓
            主 Agent 只看到 ≤5 个精选实体
```

**小 LLM 选择器实现**：

```python
ENTITY_SELECTOR_PROMPT = """你是一个实体匹配助手。根据用户的查询描述，从候选列表中选择最相关的实体。

## 用户查询
{query}

## 候选列表
{candidates}

## 任务
请分析用户查询，从候选列表中选择最相关的实体（最多选择 {limit} 个）。
只返回你认为相关的实体，如果没有相关的可以返回空列表。

## 输出格式
请严格按 JSON 格式返回选中的实体 ID 列表，例如：
{{"selected_ids": ["id1", "id2"]}}

只输出 JSON，不要有其他内容。"""

def _call_selector_llm(query: str, candidates_text: str, limit: int = 5) -> List[str]:
    """调用小 LLM 进行实体选择"""
    config = get_llm_config(db)
    response = litellm.completion(
        model=config.model,
        api_key=config.api_key,
        api_base=config.api_base,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,  # 低温度，更确定性
        max_tokens=200,
    )
    result = json.loads(response.choices[0].message.content)
    return result.get("selected_ids", [])
```

### 5.1 search_businesses

- **name**: `search_businesses`
- **description**:
  > 根据自然语言描述查找可能相关的业务流程。用于当用户提到"某个业务/流程/活动"但没有给出 process_id 时。

- **parameters（function schema）**：

```jsonc
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "用户对业务流程的自然语言描述，如：'开卡流程'、'新用户首登送券活动'"
    },
    "limit": {
      "type": "integer",
      "description": "最多返回多少条候选结果，默认 5",
      "minimum": 1,
      "maximum": 20
    }
  },
  "required": ["query"]
}
```

- **返回结构**：

```ts
{
  query: string           // 用户查询
  total_count: number     // 该类实体总数
  matched_count: number   // 小 LLM 选中的数量
  candidates: Array<{
    process_id: string
    name: string
    description?: string
    channel?: string
  }>
}
```

- **实现要点（候选列表 + 小 LLM 选择）**：
  1. 从 SQLite 查询所有 Business 的 `process_id`, `name`, `description`, `channel`
  2. 构造候选列表文本：`- ID: proc_001 | 名称: 开卡流程 [APP] | 描述: ...`
  3. 调用小 LLM（`_call_selector_llm`）返回选中的 ID 列表
  4. 根据选中 ID 构造精选结果，返回给主 Agent

- **CrewAI Tool 示例**：

```python
class SearchBusinessesTool(BaseTool):
    name: str = "search_businesses"
    description: str = "根据自然语言描述查找业务流程，返回最匹配的候选列表"
    args_schema: Type[BaseModel] = SearchBusinessesInput
    
    def _run(self, query: str, limit: int = 5) -> str:
        # 1. 查询所有 Business
        businesses = db.query(Business).all()
        
        # 2. 构造候选列表文本（供小 LLM 选择）
        candidates_text = self._build_candidates_text(businesses)
        
        # 3. 调用小 LLM 进行筛选
        selected_ids = _call_selector_llm(query, candidates_text, limit)
        
        # 4. 根据选中的 ID 构造精选结果
        id_to_business = {b.process_id: b for b in businesses}
        candidates = [id_to_business[pid] for pid in selected_ids if pid in id_to_business]
        
        return json.dumps({"query": query, "candidates": candidates, ...})
```

### 5.2 search_implementations

- **name**: `search_implementations`
- **description**:
  > 根据自然语言描述或 URI 片段查找实现/接口，例如"订单详情接口"、"/api/order/detail"。

- **parameters**：

```jsonc
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "对接口或实现的自然语言描述"
    },
    "system": {
      "type": "string",
      "description": "可选，限制在某个系统内搜索"
    },
    "limit": {
      "type": "integer",
      "description": "最多返回的候选数量，默认 5"
    }
  },
  "required": ["query"]
}
```

- **返回结构**：

```ts
{
  query: string
  system_filter?: string   // 系统过滤条件
  total_count: number
  matched_count: number
  candidates: Array<{
    impl_id: string
    name: string
    system?: string
    type?: string
    description?: string
  }>
}
```

- **实现要点**：
  1. 从 SQLite 查询所有 Implementation（可按 system 过滤）
  2. 构造候选列表：`- ID: impl_001 | 名称: 订单详情接口 [order-service] (HTTP) | 描述: ...`
  3. 调用小 LLM 选择最匹配的候选
  4. 返回精选结果

### 5.3 search_data_resources

- **name**: `search_data_resources`
- **description**:
  > 根据自然语言描述查找数据资源（库表或其他数据节点）。

- **parameters**：

```jsonc
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "对数据资源的自然语言描述"
    },
    "system": {
      "type": "string",
      "description": "可选，所属系统过滤"
    },
    "limit": {
      "type": "integer",
      "description": "最多返回的候选数量，默认 5"
    }
  },
  "required": ["query"]
}
```

- **返回结构**：

```ts
{
  query: string
  system_filter?: string
  total_count: number
  matched_count: number
  candidates: Array<{
    resource_id: string
    name: string
    type?: string
    system?: string
    description?: string
  }>
}
```

- **实现要点**：
  1. 从 SQLite 查询所有 DataResource（可按 system 过滤）
  2. 构造候选列表：`- ID: res_001 | 名称: 用户信息表 [user-service] (table) | 描述: ...`
  3. 调用小 LLM 选择最匹配的候选
  4. 返回精选结果

## 6. 上下文 / 拓扑类工具设计

### 6.1 业务流程（Business）

#### 6.1.1 summarize_business

- **name**: `summarize_business`
- **description**:
  > 给出某个业务流程的简要说明和关键要素，用于快速回答“这个流程大概是干什么的”。

- **parameters**：

```jsonc
{
  "type": "object",
  "properties": {
    "process_id": {
      "type": "string",
      "description": "业务流程的唯一标识"
    }
  },
  "required": ["process_id"]
}
```

- **返回结构建议**：

```ts
{
  process_id: string
  name: string
  summary_text: string
  key_steps: Array<{
    step_id: string
    name: string
    brief?: string
  }>
  key_systems: Array<{
    system: string
    role?: string
  }>
}
```

- **实现建议**：
  - 基于 `get_business_context` 返回的 `steps` / `implementations` / `resources`，在服务端做简单规则汇总。
  - 不强制依赖 LLM，可保持确定性。

---

#### 6.1.2 get_business_context_for_chat

- **name**: `get_business_context_for_chat`
- **description**:
  > 返回指定业务流程的详细图结构信息，供 LLM 深入回答路径/依赖等问题。

- **parameters**：与 `summarize_business` 一致，仅 `process_id`。

- **返回结构（映射当前 get_business_context）**：

```ts
{
  process: {
    process_id: string
    name: string
    description?: string
  }
  steps: Array<{
    step: {
      step_id: string
      name: string
      description?: string
      step_type?: string
      order_no?: number
    }
    prev_steps: string[]
    next_steps: string[]
    implementations: Array<{
      impl_id: string
      name: string
      system?: string
      type?: string
      description?: string
      code_ref?: string
    }>
    data_resources: Array<{
      resource_id: string
      name: string
      access_type?: string
      access_pattern?: string
    }>
  }>
  implementations: Array<{
    impl_id: string
    name: string
    system?: string
    type?: string
    description?: string
    code_ref?: string
    accessed_resources: Array<{
      resource_id: string
      access_type?: string
      access_pattern?: string
    }>
    called_impls: string[]
    called_by_impls: string[]
  }>
  resources: Array<{
    resource_id: string
    name: string
    db?: string
    table?: string
    description?: string
  }>
}
```


### 6.2 实现 / 接口（Implementation）

#### 6.2.1 summarize_implementation

- **name**: `summarize_implementation`
- **description**:
  > 给出某个实现/接口的简要说明，包括它的用途、URI、所在系统以及主要使用场景。

- **parameters**：

```jsonc
{
  "type": "object",
  "properties": {
    "impl_id": {
      "type": "string",
      "description": "实现/接口的唯一标识"
    }
  },
  "required": ["impl_id"]
}
```

- **返回结构建议**：

```ts
{
  impl_id: string
  name: string
  system?: string
  uri?: string
  summary_text: string
  related_processes: Array<{
    process_id: string
    name: string
  }>
}
```

---

#### 6.2.2 get_implementation_context_for_chat

- **name**: `get_implementation_context_for_chat`
- **description**:
  > 返回某个实现的业务使用情况、资源依赖及实现间调用关系。

- **parameters**：同上，仅 `impl_id`。

- **返回结构建议**：

```ts
{
  implementation: {
    impl_id: string
    name: string
    system?: string
    uri?: string
    description?: string
    type?: string
    code_ref?: string
  }
  process_usages: Array<{
    process_id: string
    process_name: string
    step_id: string
    step_name: string
  }>
  dependencies: {
    calls: Array<{ impl_id: string; name?: string; system?: string }>
    called_by: Array<{ impl_id: string; name?: string; system?: string }>
  }
  data_resources: Array<{
    resource_id: string
    name: string
    access_type?: string
    access_pattern?: string
  }>
}
```


### 6.3 数据资源（DataResource）

#### 6.3.1 summarize_data_resource

- **name**: `summarize_data_resource`
- **description**:
  > 给出某个数据资源（库表等）的简要说明，包括所在库表、用途及典型读写方。

- **parameters**：

```jsonc
{
  "type": "object",
  "properties": {
    "resource_id": {
      "type": "string",
      "description": "数据资源的唯一标识"
    }
  },
  "required": ["resource_id"]
}
```

- **返回结构建议**：

```ts
{
  resource_id: string
  name: string
  db?: string
  table?: string
  summary_text: string
  main_fields?: Array<{ name: string; description?: string }>
  typical_usages?: string
}
```

---

#### 6.3.2 get_resource_context_for_chat

- **name**: `get_resource_context_for_chat`
- **description**:
  > 返回某个数据资源在业务中的使用上下文，包括哪些流程/步骤/实现在读写它。

- **parameters**：同上，仅 `resource_id`。

- **返回结构建议**：

```ts
{
  resource: {
    resource_id: string
    name: string
    db?: string
    table?: string
    description?: string
  }
  businesses: Array<{
    process_id: string
    name: string
  }>
  steps: Array<{
    step_id: string
    name: string
    process_id: string
  }>
  implementations: Array<{
    impl_id: string
    name: string
    system?: string
  }>
  impl_resource_links: Array<{
    impl_id: string
    resource_id: string
    access_type?: string
    access_pattern?: string
  }>
}
```


### 6.4 通用图工具

#### 6.4.1 get_neighbors

- **name**: `get_neighbors`
- **description**:
  > 获取某个节点周围一跳或多跳的邻居节点，用于回答“这个东西周围还有什么”的问题。

- **parameters**：

```jsonc
{
  "type": "object",
  "properties": {
    "node_type": {
      "type": "string",
      "enum": ["business", "implementation", "data_resource"],
      "description": "起点节点类型"
    },
    "node_id": {
      "type": "string",
      "description": "起点节点 ID（如 process_id / impl_id / resource_id）"
    },
    "depth": {
      "type": "integer",
      "description": "向外扩展的层数，默认 1",
      "minimum": 1,
      "maximum": 3
    },
    "include_types": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": ["business", "implementation", "data_resource", "step"]
      },
      "description": "可选，仅返回指定类型的邻居"
    }
  },
  "required": ["node_type", "node_id"]
}
```

- **返回结构**：按类型分组的邻居节点 + 边信息（可按实现时具体设计）。

---

#### 6.4.2 get_path_between_entities

- **name**: `get_path_between_entities`
- **description**:
  > 查找两个实体（流程/实现/数据资源）之间的路径，用于回答“从 A 到 B 之间经过了什么”的问题。

- **parameters**：

```jsonc
{
  "type": "object",
  "properties": {
    "start_type": { "type": "string", "enum": ["business", "implementation", "data_resource"] },
    "start_id": { "type": "string" },
    "end_type": { "type": "string", "enum": ["business", "implementation", "data_resource"] },
    "end_id": { "type": "string" },
    "max_hops": {
      "type": "integer",
      "description": "最大允许路径长度，默认 6",
      "minimum": 1,
      "maximum": 10
    }
  },
  "required": ["start_type", "start_id", "end_type", "end_id"]
}
```

- **返回结构**：

```ts
{
  nodes: Array<{
    id: string
    type: "business" | "implementation" | "data_resource" | "step"
    name?: string
    extra?: Record<string, any>
  }>
  edges: Array<{
    from: string
    to: string
    edge_type?: string
    extra?: Record<string, any>
  }>
}
```


## 7. 对话编排建议

在独立 Chat 页面中，可以在 Agent 的 system prompt 中明确如下策略：

1. **不要假设用户会提供任何技术 ID**（process_id / impl_id / resource_id）。
2. 当用户自然语言中提到：
   - 某个“业务/流程/活动” → 优先调用 `search_businesses`。
   - 某个“接口/服务/API” → 优先调用 `search_implementations`。
   - 某个“表/数据/库” → 优先调用 `search_data_resources`。
3. 拿到 search_* 返回的候选后：
   - 如果只有一个高分候选 → 直接用其 ID 调用后续上下文工具。
   - 如果多个候选分数接近 → 先向用户澄清“你说的是 A 还是 B？”。
4. 已定位到具体实体时：
   - 简单概览性问题 → 优先调用 `summarize_*` 工具。
   - 涉及路径、上下游、依赖范围的问题 → 再调用 `get_*_context_for_chat` 或 `get_neighbors` / `get_path_between_entities`。
5. Agent 可以在对话内部维护“当前焦点实体”（最近一次确认过的流程/接口/表），对于后续的“它/这个接口/这个表”指代，优先指向该实体，如有歧义再调用 search_* 或向用户澄清。


## 8. 后续迭代方向

- 为 Business / Implementation / DataResource 设计或自动生成更高质量的 `search_text` 描述，可通过单独的 Agent 批处理生成。
- 在 `summarize_*` 工具中，逐步引入 LLM 辅助生成“自然语言摘要”，在保证确定性字段输出的前提下，提升可读性。
- 基于本方案扩展更多实体类型（例如系统节点、外部服务、事件等），保持相同的 search / summary / detail + 通用图工具模式。

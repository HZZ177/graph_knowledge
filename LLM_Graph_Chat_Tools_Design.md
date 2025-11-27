# LLM + 图数据对话工具设计方案

## 1. 目标与边界

### 1.1 目标

- 支持 **完全自由问答 + 自动工具调用** 的独立 Chat 页面。
- 让 LLM 能通过自然语言主动发现业务流程 / 实现 / 数据资源，并拉取对应图上下文，回答：
  - 这个流程 / 接口 / 表是什么？
  - 它在哪些流程里、和哪些系统 / 数据有关？
  - 它与另一个实体之间的路径 / 上下游关系。

### 1.2 前提

- 模型支持 function calling（主要通过 LiteLLM 底层供应商）。
- 图数据已在 Neo4j 中建好，现有 `graph_service` 已提供：
  - `get_business_context(process_id)`
  - `get_implementation_context(impl_id)`
  - `get_resource_context(resource_id)`
  - 及若干路径 / 邻居查询能力（可按需扩展）。

### 1.3 设计原则

- **工具分两层**：
  - 实体发现类：`search_*`，负责自然语言 → 候选实体（带 ID），内部只做检索，不做 LLM 推理。
  - 上下文 / 拓扑类：`summary` / `detail` + 通用图工具（neighbors / path）。
- 工具按 **实体类型** 拆分：业务（Business）、实现（Implementation）、数据资源（DataResource）。
- 每种实体维护一个用于检索的自然语言字段（`search_text` / `description`），embedding 只针对该字段，不直接 embed 结构化行。


## 2. 数据模型扩展（面向搜索的描述字段）

> 这里用“概念模型”描述，不强绑具体 ORM 字段名，实际落地可按现有模型调整。

### 2.1 Business（业务流程）

新增字段建议：

- `search_text: str`
  - 面向检索的自然语言描述，建议包含：
    - 名称：业务流程名称
    - 简要说明：一句话描述
    - 常见叫法（可选）：例如“开通月卡、开卡、办卡”
    - 关键系统：涉及的主要系统 / 服务
  - 示例：
    ```text
    业务流程：开通月卡。也叫开卡、办卡。描述：用户在 App 或小程序中开通月度会员卡，完成支付后生效。涉及系统：会员中心、订单服务。
    ```
  - 初期生成方式可以很简单：
    - 模板拼接：`f"业务流程：{name}。描述：{description or ''}。"`
    - 后续可考虑用一个 Agent 批量优化描述。

### 2.2 Implementation（实现 / 接口）

新增字段建议：

- `search_text: str`
  - 建议包含：
    - 名称：实现/接口名称
    - URI：HTTP 路径（如有）
    - 所属系统：哪个服务
    - 用途：这个接口大概做什么
    - 典型场景：在哪些业务场景中常用
  - 示例：
    ```text
    接口：订单详情查询接口。URI：/api/order/detail。所属系统：order-service。用途：根据订单号查询订单的基础信息、状态及支付记录。常用于订单列表点击进入详情页面。
    ```

### 2.3 DataResource（数据资源 / 表）

新增字段建议：

- `search_text: str`
  - 建议包含：
    - 名称 + 库表：如 `user_profile` 表，库 `user_db`
    - 常用叫法：如“用户资料表、用户基本信息表”
    - 用途：存储哪些信息
    - 关键字段（可选）：字段名 + 简短含义
  - 示例：
    ```text
    表：user_profile。也叫用户资料表、用户基本信息表。所属库：user_db。用途：存储用户的基本信息和会员状态，例如手机号码、会员等级、vip_status 等。
    ```

> 后续所有 `search_*` 工具的 embedding 检索都主要针对 `search_text` 字段。


## 3. 工具总览

### 3.1 实体发现类（search_*）

作用：**自然语言 → 候选实体列表（带 ID）**。

- `search_businesses`
- `search_implementations`
- `search_data_resources`

### 3.2 上下文 / 拓扑类

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


## 4. 实体发现类工具设计

### 4.1 search_businesses

- **name**: `search_businesses`
- **description**:
  > 根据自然语言描述查找可能相关的业务流程。用于当用户提到“某个业务/流程/活动”但没有给出 process_id 时。

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

- **返回结构建议**：

```ts
{
  candidates: Array<{
    process_id: string
    name: string
    description?: string       // 原始描述
    search_text?: string       // 可选返回，方便调试
    score: number              // 0~1，相似度
  }>
}
```

- **实现要点**：
  - 对 `search_text` 做 embedding 相似度检索（top-K）。
  - 可叠加 `name` / `description` LIKE 搜索做补充。
  - 根据相似度归一化出 `score`，不做 LLM 推理。

---

### 4.2 search_implementations

- **name**: `search_implementations`
- **description**:
  > 根据自然语言描述或 URI 片段查找实现/接口，例如“订单详情接口”、“/api/order/detail 报 500”。

- **parameters**：

```jsonc
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "对接口或实现的自然语言描述，如：'订单详情接口'、'用户首登送券的风控接口'"
    },
    "system": {
      "type": "string",
      "description": "可选，限制在某个系统或服务内搜索，如 'order-service'"
    },
    "uri_contains": {
      "type": "string",
      "description": "可选，HTTP URI 片段，如 '/api/order/detail'"
    },
    "limit": {
      "type": "integer",
      "description": "最多返回的候选数量，默认 5",
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
  candidates: Array<{
    impl_id: string
    name: string
    system?: string
    uri?: string
    description?: string
    search_text?: string
    score: number
  }>
}
```

- **实现要点**：
  - 主：对 `search_text` 做 embedding 检索。
  - 辅：按 `uri` / `name` / `system` 做 LIKE / 全文匹配。
  - 合并结果去重，归一化 `score`。

---

### 4.3 search_data_resources

- **name**: `search_data_resources`
- **description**:
  > 根据自然语言描述查找数据资源（库表或其他数据节点），如“用户资料表”、“月卡记录表”。

- **parameters**：

```jsonc
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "对数据资源的自然语言描述，如 '用户资料表'、'月卡记录'"
    },
    "db": {
      "type": "string",
      "description": "可选，数据库名过滤"
    },
    "limit": {
      "type": "integer",
      "description": "最多返回的候选数量，默认 5",
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
  candidates: Array<{
    resource_id: string
    name: string
    db?: string
    table?: string
    description?: string
    search_text?: string
    score: number
  }>
}
```

- **实现要点**：
  - 主：embedding 检索 `search_text`。
  - 辅：`name` / `db` / `table` LIKE 搜索。


## 5. 上下文 / 拓扑类工具设计

### 5.1 业务流程（Business）

#### 5.1.1 summarize_business

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

#### 5.1.2 get_business_context_for_chat

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


### 5.2 实现 / 接口（Implementation）

#### 5.2.1 summarize_implementation

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

#### 5.2.2 get_implementation_context_for_chat

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


### 5.3 数据资源（DataResource）

#### 5.3.1 summarize_data_resource

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

#### 5.3.2 get_resource_context_for_chat

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


### 5.4 通用图工具

#### 5.4.1 get_neighbors

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

#### 5.4.2 get_path_between_entities

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


## 6. 对话编排建议

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


## 7. 后续迭代方向

- 为 Business / Implementation / DataResource 设计或自动生成更高质量的 `search_text` 描述，可通过单独的 Agent 批处理生成。
- 在 `summarize_*` 工具中，逐步引入 LLM 辅助生成“自然语言摘要”，在保证确定性字段输出的前提下，提升可读性。
- 基于本方案扩展更多实体类型（例如系统节点、外部服务、事件等），保持相同的 search / summary / detail + 通用图工具模式。

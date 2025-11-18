# 企业业务知识库与图模型 PoC 交接说明（以“月卡开卡”为例）

## 1. 背景与目标

集团业务复杂、系统众多，目前业务知识分散在：

- 各业务系统代码（Controller/Service/DAO）
- DB 表结构、配置文件、日志、调用链
- 人的经验与口口相传

痛点：

- 新人/横向团队难以用“业务视角”看懂一个完整流程
- 出问题时排查高度依赖个人经验
- 很难为内部 AI 助手提供稳定、结构化的业务上下文

目标是建设一套**企业业务知识库**，让 AI 能够回答类似问题：

- “C 端用户开一张月卡，整体流程是怎样的？经过哪些接口和系统？”
- “开卡失败了，常见失败点在哪些步骤？涉及哪些表？”

当前讨论阶段，我们**暂时不考虑全面落地**，而是围绕一个小目标做 PoC：

> 用“C 端开通月卡”作为试点场景，  
> 在图数据库（Neo4j）里构建一个**最小可用数据集**，  
> 验证：AI 是否可以基于这张小图，给出接口级 + 数据流转级的流程说明。

---

## 2. 抽象模型（高层共识）

本 PoC 使用一个尽量“业务友好”的**四层模型**来描述流程：

1. **业务（Business）**

   - 表示一个对业务方可说清楚的场景，例如：
     - `c_open_card`：C 端开通月卡。
   - 记录该业务的名称、面向的端（channel）、入口页面等信息。

2. **步骤（Step）**

   - 表示业务流程中的“一步”，可以是业务动作，也可以是技术动作。  
   - 不在 `step_id` 中编码顺序，顺序完全由步骤之间的连线（`START_AT`、`NEXT`）表达。  
   - 通过 `step_type = business/technical` 粗分“业务步骤 / 技术步骤”。

3. **执行（Implementation）**

   - 表示真正落地到系统中的执行单元：HTTP 接口、RPC 方法、定时任务、消息订阅等。  
   - 用来回答“这一步是谁在执行、调用了哪个接口”。

4. **数据资源（DataResource）**

   - 表示执行背后读写的关键技术资源：数据库表、缓存、消息主题等。  
   - 用来回答“这一步涉及哪些表 / 哪些数据”。

核心思路可以概括为：

> “Business 定义一个业务；  
> Business 通过 Step 链给出业务顺序；  
> 每个 Step 挂 Execution（接口）和 DataResource（数据）；  
> AI 顺着这条链，从业务走到接口和数据。”

---

## 3. 面向 AI 的使用路径（从问题到子图）

当用户问：“C 端开月卡的流程是怎样走的？”时，AI 的理想工作流是：

1. **找到对应业务节点**

   - 在图中找到 `Business(process_id = 'c_open_card')`。

2. **获取流程步骤链**

   - 从 `Business-[:START_AT]->(Step)` 出发，沿 `[:NEXT]` 找到一条主路径：
     - Step1：校验身份
     - Step2：校验开卡资格
     - Step3：创建月卡与支付订单
     - Step4：发起支付并确认结果
     - Step5：绑定车牌（可选）

3. **放大每一步的执行与数据**

   - 通过 `(:Step)-[:EXECUTED_BY]->(:Implementation)` 找到对应的接口/任务：
     - 所属系统、HTTP Path/RPC 方法、代码位置。  
   - 通过 `(:Implementation)-[:ACCESSES_RESOURCE]->(:DataResource)` 找到数据资源：
     - 哪些表被读写、读还是写、访问模式说明。

4. **LLM 基于子图 + 文本描述生成回答**

   - Step 链作为“流程骨架”；  
   - Implementation 和 DataResource 提供“接口级 + 数据流转级”细节；  
   - LLM 按“按步骤逐条解释”的格式输出结果，同时在对业务用户的回答中尽量隐藏内部 ID / 表名等技术细节。

本次 PoC 的重点是验证：**只要图里有这些最小关系，AI 就能给出足够可信的回答**。

---

## 4. 图数据库方向：Neo4j + Property Graph 建模

### 4.1 为什么选 Property Graph（Neo4j 风格）

- 本阶段目标更偏“业务关系图 + 路径查询”，不追求复杂推理，本体（OWL/RDF）过于沉重。  
- Property Graph 模型简单：
  - 节点（Node）代表对象：业务、步骤、执行、数据资源；  
  - 边（Relationship）代表关系：起始、顺序、执行、数据访问；  
  - 节点和边都可以携带属性（name、type、access_type 等）。  
- Neo4j 工具链成熟，易于可视化和调试路径结果。

### 4.2 PoC 中采用的节点/关系类型（最小集合）

**节点（Labels）**

- `Business`
  - `process_id`, `name`, `channel`, `description`, `entrypoints`
- `Step`
  - `step_id`, `name`, `description`, `step_type`
- `Implementation`
  - `impl_id`, `name`, `type`, `system`, `description`, `code_ref`
- `DataResource`
  - `resource_id`, `name`, `type`, `system`, `description`

**关系（Relationships）**

- `(:Business)-[:START_AT]->(:Step)`：业务起始步骤  
- `(:Step)-[:NEXT {process_id}]->(:Step)`：同一业务内的下一步  
- `(:Step)-[:EXECUTED_BY]->(:Implementation)`：该步骤由哪些执行单元实现  
- `(:Implementation)-[:ACCESSES_RESOURCE {access_type, access_pattern}]->(:DataResource)`：执行读写哪些数据资源

---

## 5. “月卡开卡”最小数据集示例（概要）

为 PoC 我们构造了一份**编造的最小数据集**，只覆盖“C 端开通月卡”这一条主流程。

### 5.1 业务与步骤（示意）

- `Business`：
  - `process_id = "c_open_card"`
  - name：C端开通月卡
  - channel：`app`
  - entrypoints：`PAGE:App.MonthCard.Open` 等

- `Step`（5 个主路径步骤，`step_id` 直接使用能力 ID，便于复用）：
  1. `step_id = "common/user.verify_identity"`：校验用户身份与账号状态（technical）  
  2. `step_id = "membership/month_card/card.check_open_eligibility"`：校验用户是否具备开卡资格（business）  
  3. `step_id = "membership/month_card/card.open"`：创建月卡实例与支付订单（business）  
  4. `step_id = "common/payment.pay_order"`：发起支付并确认支付结果（technical）  
  5. `step_id = "membership/month_card/card.bind_plate"`：绑定车牌到月卡（business，可选）

步骤的先后顺序在数据集中通过一个简单的 `order_no` 字段给出，
写入 Neo4j 时转换为 `Business-START_AT->Step` 和 `Step-NEXT->Step` 的关系链。

### 5.2 执行（Implementation）节点（示意）

示例：

- `common/user.verify_identity` 对应：
  - `name = "POST /api/v1/user/verify_identity"`
  - `type = "http_endpoint"`
  - `system = "user-service"`
  - `code_ref = "user-service/controllers/user_controller.py:verify_identity"`

- `membership/month_card/card.open` 对应：
  - `name = "POST /internal/month_card/open"`
  - `type = "http_endpoint"`
  - `system = "member-service"`
  - `code_ref = "member-service/controllers/card_controller.py:open_card"`

其他能力也有类似的实现节点，用来回答“这一步由哪个系统的哪个接口完成”。

### 5.3 数据资源节点（示意）

- `member_db.user_card`：
  - `name = "user_card"`，`type = "db_table"`，`system = "member-service"`，
    `description` 为“月卡实例表，记录用户、车场、产品、状态、有效期等”。
- `pay_db.pay_order`：
  - `name = "pay_order"`，`type = "db_table"`，`system = "payment-service"`，
    `description` 为“支付订单表，记录订单金额、支付状态、业务关联等”。
- `member_db.card_plate_bind`：
  - `name = "card_plate_bind"`，`type = "db_table"`，`system = "member-service"`，
    `description` 为“月卡与车牌绑定关系表”。

### 5.4 执行与数据访问关系（示意）

示例：

- `Implementation(impl_id for card.open)`：
  - 通过 `[:ACCESSES_RESOURCE {access_type:"write"}]` 写 `member_db.user_card`、`pay_db.pay_order`。  
- `Implementation(impl_id for payment.pay_order)`：
  - 通过 `[:ACCESSES_RESOURCE {access_type:"read_write"}]` 读写 `pay_db.pay_order`。  
- `Implementation(impl_id for card.bind_plate)`：
  - 通过 `[:ACCESSES_RESOURCE {access_type:"write"}]` 写 `member_db.card_plate_bind`。

---

## 6. 当前 PoC 实现形态（技术示例）

为便于快速验证，我们在当前仓库中用 Python + Neo4j 官方 driver 写了一个**示例脚本**：

- `test/neo4j_load_open_card.py`：
  - 内部直接定义了上述“最小数据集”的字典结构；
  - 连接 Neo4j（通过 `NEO4J_URI`、`NEO4J_USER`、`NEO4J_PASSWORD` 或脚本内默认值）；
  - 创建唯一约束：`Business.process_id`、`Step.step_id`、`DataResource.resource_id`、`Implementation.impl_id`；
  - `MERGE` 写入四类节点：Business、Step、Implementation、DataResource；
  - `MERGE` 创建关系：`START_AT`、`NEXT`、`EXECUTED_BY`、`ACCESSES_RESOURCE`。

跑完之后，在 Neo4j Browser 中执行：

```cypher
MATCH (b:Business {process_id: 'c_open_card'})-[*1..4]->(n)
RETURN b, n;
```

可以看到“C 端开通月卡”的业务起点、步骤链以及挂在每一步下的接口和数据资源。

---

## 7. 下一步讨论建议：可行性验证重点

后续可以重点围绕**“最小数据集 + 一次完整验证”**来展开，而不急着扩展领域：

1. **验证图结构是否表达力足够**

   - 只用这条“开卡”流程，看以下问题能否在图上自然表达：
     - 流程步骤顺序（Step 链）；
     - 每步的业务含义（Step.description + step_type）；
     - 每步对应的接口/系统（Implementation）；
     - 每步读写的表/数据资源（DataResource）。

2. **验证 AI 回答效果**

   - 手工写一个简单的查询（或小服务）：
     - 输入：`process_id = 'c_open_card'`；
     - 输出：一个结构化 JSON，包含 Business + Step 链 + 每步的 Implementation 与 DataResource 信息；
   - 把这个 JSON 喂给 LLM，要求它生成：
     - 按步骤说明的“接口级 + 数据流向 + 关键判断点”的流程回答；
   - 评估：
     - 粒度是否合适？
     - 是否缺了什么关键关系/字段？

3. **基于验证结果，反向调整图模型**

   - 如果 AI 回答时某些信息总是模糊：
     - 反馈回来，是缺字段，还是缺节点/关系类型？
   - 在这个小域内稳定之后，再考虑：
     - 进一步细化错误模式（例如单独建 ErrorPattern 节点）；
     - 引入更细粒度的业务实体关系；
     - 扩展到“续费”、“后台删卡”等流程。

---

## 8. 小结

本阶段达成的共识可以概括为：

- **方向上**：  
  - 使用 Neo4j 这类 Property Graph 存储“流程 – 能力 – 实现 – 数据资源”的关系，是可行且直观的一条路。
- **范围上**：  
  - 暂不追求全域覆盖，而是集中在“C 端开卡”这一条流程，用最小数据集做一次 PoC。
- **手段上**：  
  - 通过小脚本把编造的业务流程数据写入 Neo4j，  
  - 再通过简单查询 + LLM 生成说明，验证这条技术路径是否满足“接口级 + 数据流转级解释”的需求。

---

## 9. 精简版四层节点模型（Business / Step / Implementation / DataResource）

在进一步讨论和 PoC 迭代中，我们把最初的 "流程 + 能力 + 实现 + 数据资源" 模型，
**精简为四类更贴近业务直觉的节点**，并把“顺序”全部交给关系来表达。

### 9.1 节点（Labels）

- **Business**（业务）  
  - `process_id`：业务 ID，例如 `c_open_card`  
  - `name`：业务名称，例如 `C端开通月卡`  
  - `channel`：业务所在端，例如 `C端App` / `B端` / `小程序`  
  - `description`：业务简要说明  
  - `entrypoints`：业务入口，例如页面路径 / URI / 文本描述

- **Step**（步骤）  
  - `step_id`：步骤内部 ID，仅用于建模与复用，不编码顺序（如 `membership/month_card/card.open`），
    便于同一能力在多个流程中复用  
  - `name`：步骤名称，例如“校验用户身份与账号状态”  
  - `description`：步骤的业务向描述  
  - `step_type`：`business` / `technical`，用于区分业务步骤与技术步骤

- **Implementation**（执行/接口层）  
  - `impl_id`：执行 ID（内部唯一）  
  - `name`：执行名称（接口、RPC 方法、Pulsar Topic 等，例：`POST /api/v1/month_card/open`）  
  - `type`：执行类型，例如 `http_api` / `rpc` / `pulsar` / `job`  
  - `system`：所属服务，例如 `member-service` / `payment-service`  
  - `description`：执行的业务向说明（这一步大致干了什么）  
  - `code_ref`：代码位置（内部排查用）

- **DataResource**（数据资源）  
  - `resource_id`：资源 ID，例如 `member_db.user_card`、`pay_db.pay_order`  
  - `name`：资源名称（通常为英文表名），例如 `user_card`、`pay_order`  
  - `type`：资源类型，例如 `db_table` / `redis` / `kafka_topic`  
  - `system`：所属系统，例如 `member-service` / `payment-service`  
  - `description`：数据资源的业务向说明（中文表名与用途描述）

### 9.2 关系（Relationships）

在这个精简模型中，**唯一的主线顺序由 Step 链表达**，其余层级通过侧边关系挂载：

- `(:Business)-[:START_AT]->(:Step)`  
  - 表示某个业务的起始步骤。

- `(:Step)-[:NEXT {process_id}]->(:Step)`  
  - 表示在某个业务流程下，两步之间的顺序关系；  
  - 具体第几步不再写入属性，而是根据从起点沿 `NEXT` 的路径位置（order_index）得出。

- `(:Step)-[:EXECUTED_BY]->(:Implementation)`  
  - 表示该步骤由哪些接口 / 任务实现；  
  - 同一个 Implementation 可以挂到多个 Step 上（复用接口）。

- `(:Implementation)-[:ACCESSES_RESOURCE {access_type, access_pattern}]->(:DataResource)`  
  - 表示某个执行对哪些数据资源进行读/写；  
  - `access_type`：`read` / `write` / `read_write` 等；  
  - `access_pattern`：访问模式说明（按什么 key 查询、插入何种记录等）。

### 9.3 面向 AI 的查询与 JSON 结构（示意）

在最新的 PoC 脚本中，我们以 `Business` + `Step` 为主线，为 AI 提供结构化上下文：

1. 选定业务：

   ```cypher
   MATCH (b:Business {process_id: $pid}) RETURN b
   ```

2. 从起点沿 `NEXT` 关系找到一条最长路径：

   ```cypher
   MATCH (b:Business {process_id: $pid})-[:START_AT]->(start:Step)
   MATCH path = (start)-[:NEXT*0..10]->(end:Step)
   WITH b, path
   ORDER BY length(path) DESC
   LIMIT 1
   WITH b, nodes(path) AS steps
   UNWIND range(0, size(steps) - 1) AS idx
   WITH b, steps[idx] AS step, idx AS order_index
   OPTIONAL MATCH (step)-[:EXECUTED_BY]->(impl:Implementation)
   OPTIONAL MATCH (impl)-[rel:ACCESSES_RESOURCE]->(dr:DataResource)
   ```

3. 把每个步骤展开为 JSON：

   ```jsonc
   {
     "process": { ... Business ... },
     "steps": [
       {
         "order_index": 0,
         "step": {
           "name": "校验用户身份与账号状态",
           "description": "...",
           "step_type": "technical"
         },
         "implementations": [
           {
             "name": "POST /api/v1/user/verify_identity",
             "type": "http_api",
             "system": "user-service",
             "description": "...",
             "code_ref": "..."
           }
         ],
         "data_resources": [
           {
             "resource": {
               "resource_id": "member_db.user_card",
               "name": "user_card",
               "type": "db_table",
               "system": "member-service",
               "description": "月卡实例表，记录每张月卡的用户、车场、产品、状态、有效期等信息"
             },
             "access_type": "read",
             "access_pattern": "按 user_id 和 product_id 查询现有有效月卡"
           }
         ]
       }
     ]
   }
   ```

LLM 基于上述结构，可以：

- 按 `order_index` 依次说明流程；
- 用 `step_type` 决定讲解偏业务还是偏技术；
- 结合 Implementation / DataResource 的描述，给出接口级和数据流转级的业务解释，
  同时在对业务用户的回答中隐藏不必要的内部细节（如具体表名、系统名）。


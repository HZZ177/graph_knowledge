# 日志排查Agent开发文档

**版本**: 1.0  
**创建日期**: 2024-12-03  
**项目**: Graph Knowledge - 企业级AI业务知识图谱系统  
**目标**: 基于现有Agent架构扩展日志排查能力

---

## 文档说明

本文档是日志排查Agent的**唯一开发指南**，包含完整的需求分析、架构设计、功能规范和实现要求。开发人员应严格按照本文档进行实现，确保与现有系统的无缝集成。

---

## 目录

1. [项目背景](#1-项目背景)
2. [核心设计理念](#2-核心设计理念)
3. [系统架构](#3-系统架构)
4. [日志查询API规范](#4-日志查询api规范)
5. [工具设计](#5-工具设计)
6. [Agent配置](#6-agent配置)
7. [前端UI设计](#7-前端ui设计)
8. [参数控制机制](#8-参数控制机制)
9. [安全与权限](#9-安全与权限)
10. [典型使用场景](#10-典型使用场景)
11. [实施路线图](#11-实施路线图)
12. [测试验收标准](#12-测试验收标准)

---

## 1. 项目背景

### 1.1 现有系统能力

当前系统已实现**业务知识问答Agent**，具备以下核心能力：

- **业务流程理解**：通过15个专业工具查询业务流程、步骤、实现和数据资源
- **代码检索分析**：基于MCP协议的语义级代码搜索和精确文本搜索
- **影响面评估**：分析接口和数据资源在各业务中的使用情况
- **知识图谱查询**：从Neo4j获取完整的业务上下文和依赖关系

### 1.2 扩展需求

为支持生产环境故障快速诊断，需要在现有架构基础上扩展**日志排查Agent**，实现：

- **跨服务日志查询**：在微服务架构中自动追踪调用链路
- **业务与日志结合**：理解业务流程后，定向查询相关服务日志
- **智能故障诊断**：从日志错误 → 堆栈分析 → 代码定位 → 业务影响评估的完整链路
- **多环境支持**：支持测试环境、生产环境、私有化部署等不同业务线

### 1.3 核心价值

1. **降低故障排查时间**：从人工跨系统查询到AI自动化链路追踪
2. **提升诊断准确性**：结合业务理解和代码分析，定位根本原因
3. **支持非技术人员**：将技术日志翻译为业务语言
4. **知识沉淀**：通过对话历史积累故障案例库

---

## 2. 核心设计理念

### 2.1 工具组合模式

日志排查Agent采用**工具复用 + 专属扩展**的设计模式：

**专属工具**（新增4个）：
- `search_logs`：日志查询工具
- `analyze_error_stack`：错误堆栈分析
- `trace_request_flow`：分布式链路追踪
- `get_log_context`：日志上下文获取

**复用工具**（从现有15个工具中选择）：
- `search_businesses`：业务流程搜索
- `search_implementations`：接口搜索
- `get_business_context`：获取业务上下文
- `get_implementation_business_usages`：评估业务影响面
- `search_code_context`：代码语义搜索
- `grep_code`：精确代码搜索
- `read_file`：文件读取
- `read_file_range`：按行读取文件
- `get_neighbors`：图拓扑查询

**设计优势**：
- 无需重复开发业务理解和代码分析能力
- 专注于日志查询和分析的专属功能
- 降低开发成本和维护复杂度

### 2.2 分层控制模型

采用**UI控制业务范围 + AI自主决策服务**的混合控制模式：

**第一层：用户UI层（业务线/集团选择）**
- 控制参数：`businessLine`, `privateServer`
- 作用：确定日志查询的安全边界
- 用户操作：在配置面板选择业务线和私有化集团

**第二层：AI决策层（服务与关键词选择）**
- 控制参数：`serverName`, `keyword`, `startTime`, `endTime`
- 作用：根据问题智能判断查询策略
- AI能力：自主选择查询哪些微服务、使用什么关键词

**第三层：系统固定层（性能与安全限制）**
- 固定参数：`limit: 2000`, `pageSize: 50`
- 作用：保护系统性能和稳定性

**核心原则**：
- **UI控制边界**：用户选择业务线，确保日志隔离和权限控制
- **AI控制细节**：AI根据问题自主选择查询哪些微服务
- **系统保护**：固定参数防止性能问题

### 2.3 跨服务排查能力

AI能够自主进行跨服务调用链追踪：

**传统方式（人工）**：
```
用户判断 → 查A服务 → 发现调用B → 切换查B服务 → 发现调用C → 切换查C服务
（耗时长，易遗漏）
```

**AI自动化方式**：
```
AI分析问题 → 并行查询A/B/C服务 → 通过trace_id关联 → 生成完整调用链
（快速、完整、准确）
```

---

## 3. 系统架构

### 3.1 现有架构回顾

系统采用以下技术栈：

**后端**：
- FastAPI：Web框架
- LangChain：Agent框架
- Neo4j：知识图谱存储
- SQLite：元数据和会话历史
- MCP：代码检索协议

**前端**：
- React + TypeScript
- Ant Design：UI组件库
- WebSocket：流式通信

**Agent机制**：
- AgentRegistry：单例管理，避免重复编译
- AsyncSqliteSaver：会话历史持久化
- 流式事件处理：on_chat_model_stream, on_tool_start, on_tool_end

### 3.2 扩展架构

日志排查Agent在现有架构上的扩展点：

**新增配置文件**：
- `backend/app/llm/langchain/configs.py`：新增 LOG_TROUBLESHOOT_SYSTEM_PROMPT 和 Agent配置
- `backend/app/core/log_query_config.py`：日志查询配置管理

**新增工具文件**：
- `backend/app/llm/langchain/log_tools.py`：日志查询相关工具

**扩展现有文件**：
- `backend/app/api/v1/llm_chat.py`：支持 agent_context 传递
- `frontend/src/pages/ChatPage.tsx`：新增日志配置面板
- `frontend/src/api/llm.ts`：扩展 ChatRequest 接口

### 3.3 数据流转

```
用户界面
  ↓ 选择业务线和集团
配置参数（businessLine, privateServer）
  ↓ WebSocket传递
后端接收并存入metadata
  ↓ 注入到System Prompt
AI Agent理解当前范围
  ↓ 调用search_logs工具
工具合并UI参数和AI参数
  ↓ HTTP请求
企业日志查询API
  ↓ 返回结果
AI分析并格式化展示
  ↓ WebSocket流式推送
前端UI渲染
```

---

## 4. 日志查询API规范

### 4.1 API基本信息

**接口地址**：
```
POST https://ts.keytop.cn/cd-common-server/log-query/list
```

**请求头**：
```
appId: testai
secretKey: d73833a466c040819dd086db57c0ed82
Content-Type: application/json
```

### 4.2 请求参数规范

| 参数名 | 类型 | 必填 | 控制方 | 说明 |
|--------|------|------|--------|------|
| keyword | String | 是 | AI | 主要搜索关键词，如"ERROR"、"开卡失败" |
| keyword2 | String | 否 | AI | 次要关键词，与keyword是AND关系 |
| businessLine | String | 是 | UI | 业务线，如"永策测试"、"C端车主服务"、"私有化" |
| serverName | String | 是 | AI | 服务名称，从白名单选择 |
| privateServer | String | 否 | UI | 私有化集团名称，仅当businessLine="私有化"时有效 |
| startTime | String | 是 | AI | 开始时间，格式：YYYY-MM-DD HH:mm:ss |
| endTime | String | 是 | AI | 结束时间，格式：YYYY-MM-DD HH:mm:ss |
| limit | Integer | 是 | 系统 | 固定值：2000 |
| pageNo | Integer | 是 | AI | 页码，从1开始 |
| pageSize | Integer | 是 | 系统 | 固定值：50 |

### 4.3 请求示例

```json
{
  "keyword": "error",
  "keyword2": "",
  "businessLine": "永策测试",
  "serverName": "vehicle-owner-admin",
  "privateServer": null,
  "startTime": "2025-12-02 10:43:32",
  "endTime": "2025-12-02 11:43:32",
  "limit": 2000,
  "pageNo": 1,
  "pageSize": 50
}
```

### 4.4 响应格式

API返回标准JSON格式：

**成功响应**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total": 150,
    "list": [
      {
        "logTime": "2025-12-02 10:45:23",
        "logLevel": "ERROR",
        "logContent": "java.lang.NullPointerException at ...",
        "traceId": "trace-abc123",
        "service": "vehicle-owner-admin"
      }
    ]
  }
}
```

**错误响应**：
```json
{
  "code": 500,
  "message": "查询失败: 参数错误"
}
```

### 4.5 重要约束

1. **时间范围限制**：endTime - startTime 不得超过24小时
2. **关键词AND关系**：keyword和keyword2同时存在时为交集查询
3. **分页限制**：单次最多返回50条（pageSize固定）
4. **总量限制**：limit固定为2000，防止查询超大数据集
5. **业务线隔离**：不同businessLine的日志完全隔离

---

## 5. 工具设计

### 5.1 search_logs - 日志查询工具

**功能描述**：
在企业日志系统中搜索日志，支持关键词过滤、时间范围和服务选择。

**参数设计**：
- `keyword` (必填): 主要搜索关键词
- `keyword2` (可选): 次要关键词，AND关系
- `start_time` (必填): 开始时间
- `end_time` (必填): 结束时间
- `server_name` (必填): 服务名称，从Enum选择
- `page_no` (默认1): 页码

**参数验证**：
1. 时间范围不能超过24小时
2. 时间格式必须为 YYYY-MM-DD HH:mm:ss
3. server_name 必须在白名单内
4. 从RunnableConfig的metadata中获取UI配置的 businessLine 和 privateServer

**返回格式**：
```json
{
  "success": true,
  "total": 150,
  "page_no": 1,
  "returned_count": 20,
  "logs": [
    {
      "time": "2024-12-03 10:05:12",
      "level": "ERROR",
      "content": "日志内容（截断500字符）",
      "trace_id": "trace-abc123"
    }
  ],
  "query_params": {
    "keyword": "ERROR",
    "business_line": "永策测试",
    "server_name": "vehicle-owner-server",
    "time_range": "2024-12-03 10:00:00 ~ 11:00:00"
  },
  "hint": "共找到50条日志，当前显示前20条。使用page_no=2查看更多"
}
```

### 5.2 analyze_error_stack - 堆栈分析工具

**功能描述**：
分析Java/Python等语言的异常堆栈，提取关键信息。

**参数设计**：
- `stack_trace` (必填): 完整的堆栈跟踪信息

**返回信息**：
- 异常类型
- 错误消息
- 发生位置（文件名、行号、方法名）
- 调用链路分析
- 可能的原因分析

### 5.3 trace_request_flow - 链路追踪工具

**功能描述**：
根据trace_id跨服务查询分布式调用链路。

**参数设计**：
- `trace_id` (必填): 跟踪ID
- `start_time` (必填): 开始时间
- `end_time` (必填): 结束时间

**返回信息**：
- 完整的调用链路图
- 每个服务的耗时
- 调用成功/失败状态
- 关键日志节点

### 5.4 get_log_context - 日志上下文工具

**功能描述**：
获取指定日志的前后上下文，更全面理解问题发生场景。

**参数设计**：
- `log_time` (必填): 目标日志时间
- `server_name` (必填): 服务名称
- `context_lines` (默认10): 前后各多少行

**返回信息**：
- 目标日志前 N 行
- 目标日志
- 目标日志后 N 行

---

## 6. Agent配置

### 6.1 Agent基本信息

**Agent类型**: `log_troubleshoot`

**显示名称**: "日志排查助手"

**图标**: 🔍 (放大镜图标)

**描述**: "企业级日志分析与故障排查专家，支持跨服务链路追踪和智能诊断。"

### 6.2 System Prompt要点

**动态上下文注入**：
System Prompt需要根据UI配置动态生成，包含：

1. **当前查询范围**
   - 业务线：{businessLine}
   - 私有化集团：{privateServer}（条件显示）

2. **可用服务列表**
   - 详细列出所有可查询的微服务
   - 每个服务的职责、常见场景、查询时机

3. **工具使用规范**
   - AI需要填写的参数
   - 系统自动使用的参数
   - 参数约束和注意事项

4. **跨服务排查策略**
   - 如何确定入口服务
   - 如何追踪调用链
   - 如何使用trace_id关联日志

5. **时间推断规则**
   - 当前服务器时间：{current_time}
   - 相对时间转绝对时间的规则

### 6.3 工具配置

**专属工具**：
```python
def get_log_troubleshoot_tools():
    return [
        search_logs,           # 日志查询
        analyze_error_stack,   # 堆栈分析
        trace_request_flow,    # 链路追踪
        get_log_context,       # 上下文获取
    ]
```

**复用工具**：
```python
def get_log_troubleshoot_tools():
    # ... 专属工具
    
    # 从现有工具中选择
    from .tools import (
        search_businesses,
        search_implementations,
        get_business_context,
        get_implementation_business_usages,
        search_code_context,
        grep_code,
        read_file,
        read_file_range,
    )
    
    return [
        # 日志工具
        search_logs,
        analyze_error_stack,
        trace_request_flow,
        get_log_context,
        # 业务理解
        search_businesses,
        search_implementations,
        get_business_context,
        get_implementation_business_usages,
        # 代码分析
        search_code_context,
        grep_code,
        read_file,
        read_file_range,
    ]
```

### 6.4 注册到AGENT_CONFIGS

在 `backend/app/llm/langchain/configs.py` 中新增Agent配置：

```python
AGENT_CONFIGS = {
    "knowledge_qa": AgentConfig(
        # ... 现有配置
    ),
    
    "log_troubleshoot": AgentConfig(
        agent_type="log_troubleshoot",
        name="日志排查助手",
        description="企业级日志分析与故障排查专家",
        system_prompt_template=LOG_TROUBLESHOOT_SYSTEM_PROMPT,
        tool_factory=get_log_troubleshoot_tools,
        icon="🔍",
    ),
}
```

---

## 7. 前端UI设计

### 7.1 Agent选择器

**位置**：对话页面左侧栏顶部

**显示内容**：
- 业务知识助手
- 日志排查助手 🔍

**交互行为**：
- 切换Agent时，自动显示/隐藏相应配置面板
- 切换到日志排查Agent时，显示日志查询配置面板
- 配置选项通过localStorage持久化

### 7.2 日志配置面板

**位置**：Agent选择器下方

**组件结构**：
```
┌───────────────────────────┐
│  日志排查助手配置           │
├───────────────────────────┤
│                            │
│  查询范围                    │
│  ┌─────────────────────┐  │
│  │ 业务线 *              │  │
│  │ ○ 永策测试            │  │
│  │ ○ C端车主服务生产     │  │
│  │ ● 私有化              │  │
│  └─────────────────────┘  │
│                            │
│  ┌─────────────────────┐  │
│  │ 私有化集团          │  │
│  │ [下拉选择: 某商业广场] │  │
│  └─────────────────────┘  │
│  ↑ 只有选择"私有化"时才显示 │
│                            │
│  ℹ️ AI将自动判断需要查询的服务 │
│                            │
└───────────────────────────┘
```

**字段详细设计**：

1. **业务线选择** (Radio Group)
   - 永策测试
   - C端车主服务生产
   - 私有化
   - 默认选中：永策测试

2. **私有化集团选择** (Select)
   - 显示条件：businessLine === "私有化"
   - 选项：某商业广场、某机场集团、某医院集团
   - 支持搜索过滤

3. **提示信息**
   - 图标 + 文本："AI将自动判断需要查询的服务"
   - 颜色：信息提示蓝

### 7.3 工具调用可视化

**工具卡片展示**：
```
[调用工具: 日志查询 (0.8s · 找到50条结果)]
  查询参数：
  - 服务：vehicle-owner-server
  - 关键词：开卡失败
  - 时间：2024-12-03 10:00-11:00
  [展开查看详情]

[调用工具: 日志查询 (1.2s · 找到15条结果)]
  查询参数：
  - 服务：card-service
  - 关键词：trace-abc123
  - 时间：2024-12-03 10:00-11:00
  [展开查看详情]
```

**展开后显示内容**：
- 输入参数摘要
- 输出结果摘要（前3-5条日志）
- 完整输出的JSON格式化展示

### 7.4 数据结构扩展

**ChatRequest接口扩展**：
```typescript
interface ChatRequest {
  question: string
  thread_id?: string
  agent_type?: string
  // 新增：Agent上下文配置
  agent_context?: {
    log_query?: {
      businessLine: string
      privateServer: string | null
    }
  }
}
```

**状态管理**：
```typescript
const [logQueryConfig, setLogQueryConfig] = useState({
  businessLine: '永策测试',
  privateServer: null,
})

// 保存到localStorage
useEffect(() => {
  localStorage.setItem('logQueryConfig', JSON.stringify(logQueryConfig))
}, [logQueryConfig])

// 页面加载时恢复
useEffect(() => {
  const saved = localStorage.getItem('logQueryConfig')
  if (saved) {
    setLogQueryConfig(JSON.parse(saved))
  }
}, [])
```

---

## 8. 参数控制机制

### 8.1 参数流转图

```
┌──────────────────────────────────┐
│         用户界面层                  │
│  ┌───────────────────────────┐  │
│  │ 业务线选择: [永策测试 ▼]    │  │
│  │ 私有集团: [某商场 ▼] (条件) │  │
│  └───────────────────────────┘  │
│              ↓ 固定参数          │
└──────────────────────────────────┘
                ↓
┌──────────────────────────────────┐
│        WebSocket 请求                │
│  {                                  │
│    agent_context: {                 │
│      businessLine: "永策测试",       │
│      privateServer: null              │
│    }                                │
│  }                                  │
└──────────────────────────────────┘
                ↓
┌──────────────────────────────────┐
│          AI Agent 层                │
│  ┌───────────────────────────┐  │
│  │ 理解问题 → 选择服务        │  │
│  │ serverName: "payment-service" │  │
│  │ keyword: "支付失败"           │  │
│  └───────────────────────────┘  │
│              ↓ 动态参数          │
└──────────────────────────────────┘
                ↓
┌──────────────────────────────────┐
│         工具执行层                │
│  合并参数：                        │
│  {                                  │
│    // AI参数                        │
│    keyword: "支付失败",              │
│    serverName: "payment-service",     │
│    startTime: "...",                  │
│                                       │
│    // UI参数                        │
│    businessLine: "永策测试",         │
│    privateServer: null,               │
│                                       │
│    // 系统参数                      │
│    limit: 2000,                       │
│    pageSize: 50                       │
│  }                                  │
└──────────────────────────────────┘
                ↓
┌──────────────────────────────────┐
│        日志查询API                  │
│  验证 → 查询 → 返回结果            │
└──────────────────────────────────┘
```

### 8.2 后端参数获取

**从 RunnableConfig 获取 UI 配置**：

在工具函数中，通过 `run_manager` 获取metadata：

```python
@tool
def search_logs(
    keyword: str,
    server_name: str,
    start_time: str,
    end_time: str,
    keyword2: str = "",
    page_no: int = 1,
    run_manager: Optional[CallbackManagerForToolRun] = None,
) -> str:
    # 获取metadata
    metadata = {}
    if run_manager:
        metadata = getattr(run_manager, "metadata", {})
    
    # 提取UI配置
    agent_context = metadata.get("agent_context", {})
    log_context = agent_context.get("log_query", {})
    
    business_line = log_context.get("businessLine", "永策测试")
    private_server = log_context.get("privateServer", None)
    
    # 构建完整请求
    request_payload = {
        "keyword": keyword,
        "keyword2": keyword2,
        "businessLine": business_line,
        "serverName": server_name,
        "privateServer": private_server,
        "startTime": start_time,
        "endTime": end_time,
        "limit": 2000,
        "pageNo": page_no,
        "pageSize": 50,
    }
    
    # 调用API...
```

### 8.3 参数验证策略

**多层验证**：

1. **前端验证**：
   - 业务线必选
   - 私有化时集团必选

2. **Pydantic Schema验证**：
   - server_name 使用 Enum 类型限定选项
   - 时间格式验证

3. **工具内部验证**：
   - 时间范围不超过24小时
   - businessLine 白名单验证
   - server_name 白名单验证

4. **API层验证**：
   - 最终的安全屏障
   - 拒绝非法请求

---

## 9. 安全与权限

### 9.1 三层隔离机制

**第一层：业务线隔离**
- 不同业务线的日志完全隔离
- 测试环境 ≠ 生产环境 ≠ 私有化
- 用户只能查看有权限的业务线

**第二层：集团隔离**
- 私有化场景下，不同集团的日志隔离
- A商场 ≠ B商场

**第三层：服务白名单**
- 即使在正确的业务线下
- AI也只能选择白名单内的服务
- 不能访问管理后台、B端服务等

### 9.2 白名单配置

**配置文件结构**：

```python
# backend/app/core/log_query_config.py

class LogQueryConfig:
    # C端车主服务允许的业务线
    ALLOWED_BUSINESS_LINES = [
        "永策测试",
        "C端车主服务生产",
        "私有化",
    ]
    
    # C端车主服务允许的服务器名称
    ALLOWED_SERVER_NAMES = [
        "vehicle-owner-server",
        "vehicle-owner-admin",
        "card-service",
        "payment-service",
        "user-service",
        "notification-service",
        "order-service",
    ]
    
    # 私有化集团列表（示例）
    PRIVATE_SERVERS = [
        "某商业广场",
        "某机场集团",
        "某医院集团",
    ]
```

### 9.3 防越权机制

**场景1：AI尝试访问非法服务**
```
AI尝试：serverName="admin-backend-service"
    ↓
工具验证：不在白名单中
    ↓
返回错误："serverName 必须是以下之一: vehicle-owner-server, card-service, ..."
    ↓
AI自我修正：选择 vehicle-owner-server
```

**场景2：用户尝试修改请求抦截**
```
用户端修改WebSocket消息，传入businessLine="管理后台"
    ↓
后端验证：不在 ALLOWED_BUSINESS_LINES
    ↓
直接拒绝请求，返回 403 Forbidden
```

### 9.4 API层鉴权

日志查询API本身使用 appId/secretKey 鉴权：
- 每个应用只能访问授权范围
- testai 只能访问C端车主服务范围
- 即使绕过前端/后端验证，API层仍然拒绝

---

## 10. 典型使用场景

### 10.1 场景1：单服务错误排查

**用户问题**："今天上午登录失败，帮我查一下日志"

**AI执行流程**：
1. 理解问题：登录功能，单一服务
2. 查询 user-service 日志
3. 发现数据库连接失败错误
4. 分析堆栈，定位到连接池配置问题
5. 给出诊断结果和解决方案

### 10.2 场景2：跨服务链路追踪

**用户问题**："开卡失败，用户反馈支付成功但卡没开通"

**AI执行流程**：
1. 理解问题：开卡流程，涉及多服务
2. **第一步**：查 vehicle-owner-server 入口日志
   - 发现请求到达，获取 trace_id=abc123
3. **第二步**：查 card-service 业务处理日志
   - 使用 trace_id 查询
   - 发现调用 payment-service 查询余额
4. **第三步**：查 payment-service 日志
   - 发现返回了错误的余额信息
5. **第四步**：分析代码
   - 使用 grep_code 查找 payment-service 余额查询逻辑
   - 发现缓存更新逻辑有bug
6. **第五步**：评估影响面
   - 使用 get_implementation_business_usages
   - 发现多个业务受影响

### 10.3 场景3：业务与日志结合诊断

**用户问题**："充值失败，帮我看看是不是业务流程有问题"

**AI执行流程**：
1. **理解业务**：使用 search_businesses 查询充值流程
2. **查询日志**：根据业务流程涉及的服务查询日志
3. **对比分析**：业务定义 vs 实际执行
4. **发现问题**：业务流程定义了步骤X，但日志显示没有执行
5. **定位代码**：使用 search_code_context 查找相关实现
6. **给出结论**：业务配置与代码实现不一致

---

## 11. 实施路线图

### 11.1 Phase 1：基础架构（1-2天）

**目标**：搭建日志排查Agent的基本框架

**任务清单**：

1. **后端配置扩展**
   - [ ] 扩展 `backend/app/api/v1/llm_chat.py`
     - 修改 ChatRequest Pydantic模型，添加 agent_context 字段
     - 在WebSocket处理中提取 agent_context
     - 将 agent_context 传递给 streaming_chat 服务
   - [ ] 扩展 `backend/app/services/chat/chat_service.py`
     - 修改 streaming_chat 函数签名，接收 metadata 参数
     - 将 metadata 注入到 RunnableConfig

2. **配置管理**
   - [ ] 创建 `backend/app/core/log_query_config.py`
     - 定义 LogQueryConfig 类
     - 配置 ALLOWED_BUSINESS_LINES 白名单
     - 配置 ALLOWED_SERVER_NAMES 白名单
     - 配置 PRIVATE_SERVERS 列表
     - 实现 validate_context 方法

3. **前端API扩展**
   - [ ] 扩展 `frontend/src/api/llm.ts`
     - 扩展 ChatRequest interface，添加 agent_context 字段
     - 确保 WebSocket 发送逻辑支持新字段

**验收标准**：
- WebSocket 可以成功传递 agent_context
- 后端能够接收并解析 agent_context
- 白名单配置正确加载

### 11.2 Phase 2：核心工具开发（3-4天）

**目标**：实现日志查询相关工具

**任务清单**：

1. **search_logs 工具**
   - [ ] 创建 `backend/app/llm/langchain/log_tools.py`
   - [ ] 定义 SearchLogsInput Pydantic Schema
     - 使用 Enum 限定 server_name 选项
     - 添加时间格式验证
   - [ ] 实现 search_logs 工具函数
     - 从 run_manager 获取 metadata
     - 提取 UI 配置参数
     - 验证时间范围（24小时限制）
     - 验证参数白名单
     - 调用日志查询API
     - 格式化返回结果
   - [ ] 错误处理
     - 网络超时处理
     - API错误响应处理
     - 参数验证失败提示

2. **analyze_error_stack 工具**
   - [ ] 定义 AnalyzeErrorStackInput Schema
   - [ ] 实现堆栈解析逻辑
     - Java 异常堆栈解析
     - Python 异常堆栈解析
     - 提取关键信息（异常类型、文件名、行号、方法名）

3. **trace_request_flow 工具**
   - [ ] 定义 TraceRequestFlowInput Schema
   - [ ] 实现链路追踪逻辑
     - 根据 trace_id 查询多个服务
     - 构建调用链路图
     - 计算耗时和状态

4. **get_log_context 工具**
   - [ ] 定义 GetLogContextInput Schema
   - [ ] 实现上下文获取逻辑
     - 获取指定日志的前 N 行
     - 获取指定日志的后 N 行

**验收标准**：
- search_logs 工具能够成功查询日志
- 参数验证正常工作
- API调用成功率 > 95%
- 错误提示明确易懂

### 11.3 Phase 3：Agent配置（2-3天）

**目标**：配置和注册Agent

**任务清单**：

1. **System Prompt 编写**
   - [ ] 在 `backend/app/llm/langchain/configs.py` 中编写 LOG_TROUBLESHOOT_SYSTEM_PROMPT
     - 当前查询范围说明
     - 可用服务列表和职责描述
     - 工具使用规范
     - 跨服务排查策略
     - 时间推断规则
   - [ ] 实现动态注入逻辑
     - 根据 agent_context 生成上下文信息
     - 注入当前服务器时间

2. **工具集配置**
   - [ ] 实现 get_log_troubleshoot_tools 函数
     - 添加日志专属工具
     - 复用现有业务理解工具
     - 复用现有代码分析工具

3. **Agent 注册**
   - [ ] 在 AGENT_CONFIGS 中添加 log_troubleshoot 配置
     - 设置 agent_type
     - 设置 name 和 description
     - 指定 system_prompt_template
     - 指定 tool_factory
     - 设置 icon

**验收标准**：
- Agent 能够成功启动
- System Prompt 正确注入
- 所有工具正常加载
- Agent 可以响应简单查询

### 11.4 Phase 4：前端UI开发（3-4天）

**目标**：实现用户界面

**任务清单**：

1. **Agent 选择器扩展**
   - [ ] 修改 `frontend/src/pages/ChatPage.tsx`
     - 在 Agent 选择器中添加日志排查Agent
     - 添加图标和名称

2. **配置面板组件**
   - [ ] 创建日志配置面板组件
     - 业务线 Radio Group
     - 私有化集团 Select（条件显示）
     - 提示信息显示
   - [ ] 样式设计
     - 卡片式布局
     - 响应式设计

3. **状态管理**
   - [ ] 添加 logQueryConfig state
   - [ ] 实现 localStorage 持久化
   - [ ] 实现配置恢复逻辑

4. **请求发送逻辑**
   - [ ] 修改 handleSendMessage 函数
     - 判断当前 Agent 类型
     - 条件性添加 agent_context
     - 发送 WebSocket 请求

5. **工具调用可视化优化**
   - [ ] 优化 ToolProcess 组件显示
     - 显示查询的服务名
     - 显示关键词和时间范围
     - 显示结果数量

**验收标准**：
- UI 界面美观易用
- 配置选项正常工作
- 配置持久化正常
- 工具调用清晰可见

### 11.5 Phase 5：测试与优化（2-3天）

**目标**：全面测试和性能优化

**任务清单**：

1. **功能测试**
   - [ ] 单服务日志查询测试
   - [ ] 跨服务链路追踪测试
   - [ ] 参数验证测试
   - [ ] 错误处理测试

2. **安全测试**
   - [ ] 白名单验证测试
   - [ ] 业务线隔离测试
   - [ ] 越权攻击测试

3. **性能优化**
   - [ ] API调用超时设置
   - [ ] 大量日志返回的截断处理
   - [ ] 并发查询优化

4. **用户体验优化**
   - [ ] 错误提示信息优化
   - [ ] 工具调用显示优化
   - [ ] 加载状态显示

**验收标准**：
- 所有功能测试通过
- 安全测试无漏洞
- 响应时间 < 3秒（单次查询）
- 用户反馈良好

### 11.6 总体时间评估

| 阶段 | 工作量 | 时间 | 依赖 |
|------|--------|------|------|
| Phase 1 | 基础架构 | 1-2天 | 无 |
| Phase 2 | 核心工具 | 3-4天 | Phase 1 |
| Phase 3 | Agent配置 | 2-3天 | Phase 2 |
| Phase 4 | 前端UI | 3-4天 | Phase 1 |
| Phase 5 | 测试优化 | 2-3天 | Phase 2,3,4 |
| **总计** | | **11-16天** | |

**并行开发建议**：
- Phase 1 完成后，Phase 2 和 Phase 4 可以并行开发
- 总时间可以压缩到 **8-12天**

---

## 12. 测试验收标准

### 12.1 功能测试

**测试用例1：基本日志查询**
```
前置条件：
- 已选择业务线：永策测试
- 已切换到日志排查Agent

测试步骤：
1. 输入："查询vehicle-owner-server服务今天上午10点的ERROR日志"
2. 观察 AI 是否调用 search_logs 工具
3. 检查工具参数是否正确

期望结果：
- AI 成功调用 search_logs
- serverName = "vehicle-owner-server"
- keyword = "ERROR"
- 时间范围正确（今天上午10点前后1小时）
- businessLine 自动使用 "永策测试"
- 返回格式化的日志结果
```

**测试用例2：跨服务查询**
```
前置条件：同上

测试步骤：
1. 输入："开卡失败，帮我排查一下"
2. 观察 AI 是否进行多次查询

期望结果：
- AI 至少查询2个服务（vehicle-owner-server, card-service）
- 使用 trace_id 关联不同服务的日志
- 生成完整的调用链路分析
```

**测试用例3：业务线切换**
```
测试步骤：
1. 选择业务线：永策测试
2. 进行一次查询
3. 切换业务线：C端车主服务生产
4. 再次查询

期望结果：
- 两次查询使用不同的 businessLine
- 返回的日志来自不同环境
```

**测试用例4：私有化场景**
```
测试步骤：
1. 选择业务线：私有化
2. 选择集团：某商业广场
3. 进行查询

期望结果：
- businessLine = "私有化"
- privateServer = "某商业广场"
- 只返回该集团的日志
```

### 12.2 参数验证测试

**测试用例5：时间范围验证**
```
测试步骤：
1. 输入超过24小时的时间范围
   例如："查询12月1日到12月3日的日志"

期望结果：
- 工具返回错误："时间范围超过24小时限制"
- AI 提示用户缩小时间范围
```

**测试用例6：服务名白名单验证**
```
测试步骤：
1. 尝试让AI查询不在白名单中的服务
   例如："查询admin-backend-service的日志"

期望结果：
- 工具返回错误："serverName 必须是以下之一: ..."
- AI 自动修正为合法的服务名
```

### 12.3 安全性测试

**测试用例7：业务线隔离**
```
测试步骤：
1. 选择业务线：永策测试
2. 查询日志
3. 记录返回的日志内容
4. 切换业务线：C端车主服务生产
5. 使用相同查询条件

期望结果：
- 两次查询返回的日志完全不同
- 无数据泄露
```

**测试用例8：WebSocket抦截修改攻击**
```
测试步骤：
1. 使用浏览器开发者工具拦截WebSocket消息
2. 修改 agent_context 中的 businessLine 为非法值
3. 发送修改后的请求

期望结果：
- 后端验证失败
- 返回 403 Forbidden 或错误信息
- 不执行查询
```

### 12.4 性能测试

**测试用例9：单次查询性能**
```
测试指标：
- 单次日志查询响应时间 < 3秒
- API调用超时设置为30秒
- 大量日志返回时截断为500字符/条
```

**测试用例10：并发查询性能**
```
测试指标：
- 支持多个服务并行查询
- 总耗时接近最慢的单次查询，而非总和
```

### 12.5 用户体验测试

**测试用例11：配置持久化**
```
测试步骤：
1. 选择业务线：私有化
2. 选择集团：某商场
3. 刷新页面

期望结果：
- 配置保持不变
- 业务线仍为私有化
- 集团仍为某商场
```

**测试用例12：错误提示清晰性**
```
测试标准：
- 时间范围错误时，提示具体超过的小时数
- 服务名错误时，列出所有可用选项
- API错误时，给出明确的错误原因
```

### 12.6 集成测试

**测试用例13：完整流程测试**
```
测试步骤：
1. 打开对话页面
2. 切换到日志排查Agent
3. 选择业务线和集团
4. 提问："今天上午开卡失败，帮我排查"
5. 观寽AI执行过程
6. 查看最终诊断报告

期望结果：
- AI 成功查询多个服务的日志
- 分析出错误原因
- 定位到具体代码位置
- 评估业务影响面
- 给出解决方案
```

### 12.7 验收检查清单

**功能完整性**：
- [ ] 所有工具正常工作
- [ ] Agent正常响应查询
- [ ] 前端配置面板正常显示
- [ ] 参数正确传递

**安全性**：
- [ ] 业务线隔离有效
- [ ] 白名单验证有效
- [ ] 无越权漏洞
- [ ] 错误信息不泄露敏感信息

**性能**：
- [ ] 单次查询 < 3秒
- [ ] 支持并发查询
- [ ] 大量数据正常截断

**用户体验**：
- [ ] UI界面美观易用
- [ ] 错误提示明确
- [ ] 配置正常持久化
- [ ] 工具调用过程可视

---

## 附录

### 关键文件清单

**新增文件**：
- `backend/app/core/log_query_config.py`
- `backend/app/llm/langchain/log_tools.py`

**修改文件**：
- `backend/app/api/v1/llm_chat.py`
- `backend/app/services/chat/chat_service.py`
- `backend/app/llm/langchain/configs.py`
- `frontend/src/pages/ChatPage.tsx`
- `frontend/src/api/llm.ts`

### 外部依赖

**日志查询API**：
- 地址：https://ts.keytop.cn/cd-common-server/log-query/list
- 鉴权：appId + secretKey
- 文档：（如有请填写）

### 参考文档

- LangChain Tool 开发指南
- AgentRegistry 使用文档
- 现有 knowledge_qa Agent 实现

### 联系人

- 技术负责人：（请填写）
- 产品负责人：（请填写）
- 日志API负责人：（请填写）

---

**文档版本**: 1.0  
**最后更新**: 2024-12-03  
**状态**: 待开发


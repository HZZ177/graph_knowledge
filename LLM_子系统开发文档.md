# LLM 子系统开发文档（基于数据库配置 & crewai==0.177.0）

> 本文档用于指导开发者在当前 `graph_knowledge` 项目中，从 **数据库 → SQLAlchemy 模型 → Service → LLM 基础层（llm/）→ API** 全链路实现一个可落地的 LLM 子系统。
>
> 要求：
> - 不使用环境变量存储模型配置，**所有 LLM 配置全部存储在数据库**。
> - AI 调用基于 `crewai==0.177.0`，使用 `from crewai import LLM` 的真实用法。
> - 任意时刻仅允许 **一个激活的模型**，所有 LLM 业务统一走激活模型。
> - 本文档是唯一规范，其他人将严格按本文档实现代码，请保证接口与行为清晰、一致。

---

## 1. 总体架构与数据流

### 1.1 组件分层

本仓库现有后端分层回顾（简化）：

- `backend/app/models/`：SQLAlchemy ORM 模型
- `backend/app/schemas/`：Pydantic 请求/响应模型
- `backend/app/services/`：业务服务（面向用例）
- `backend/app/llm/`：**新增**，LLM 基础层（与 `db` 同级）
- `backend/app/api/v1/`：FastAPI 路由（HTTP API）

本次 LLM 子系统新增/调整部分如下：

- **数据库表**：`ai_models`
- **SQLAlchemy 模型**：`backend/app/models/ai_models.py` 中的 `AIModel`
- **Pydantic 模型**：`backend/app/schemas/ai_models.py`
- **Service 层**：`backend/app/services/ai_model_service.py` + 使用 LLM 的业务 service（如 `llm_service.py`）
- **LLM 基础层**：
  - `backend/app/llm/config.py`：从数据库读取“当前激活模型”配置
  - `backend/app/llm/base.py`：基于 `crewai.LLM` 构造可复用的 LLM 实例
- **API 层**：
  - `backend/app/api/v1/llm_models.py`：LLM 模型配置管理（供前端配置页使用）
  - 现有 `backend/app/api/v1/llm.py`：业务问答接口，内部通过 service 使用 LLM

### 1.2 请求/配置流转路径

1. **配置阶段（前端 LLM 配置页）**：
   - 前端页面通过 `/api/v1/llm-models*` 系列接口，对 `ai_models` 表进行 CRUD 和“激活某模型”。
   - 激活动作会确保数据库中只存在一个 `is_active = True` 的模型配置。

2. **业务调用阶段（任意 LLM 业务，比如流程问答）**：
   - 业务 Service（如 `llm_service.answer_question`）在收到请求后，通过 `Session` 调用 `AIModelService.get_active_llm_config(db)` 获取当前激活配置，并转换为 `LLMConfig`。
   - Service 调用 `backend/app/llm/base.get_crewai_llm(config)` 基于 `crewai.LLM` 实例化 LLM 客户端。
   - Service 基于该 LLM 组织 prompts / agents / crews，完成实际 AI 任务。
   - 响应通过 API 层返回给前端。

3. **热切换**：
   - 当前端在配置页激活新的模型时：
     - API 调用 `AIModelService.set_active_model(db, model_id)`，更新 `ai_models` 表中激活标记。
     - 不需要专门的内存缓存；业务 Service 每次请求都从 DB 读取当前激活配置，自然使用最新模型。

---

## 2. 数据库设计

### 2.1 新增数据表：`ai_models`

> 表名可根据团队习惯调整为 `llm_models` 等，但需与文档内代码保持一致。

#### 2.1.1 表字段

建议使用 SQLite（当前项目已有 `app.db`）中新增表：

```sql
CREATE TABLE ai_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                         -- 在配置页展示的名称，如 "生产 OpenAI GPT-4.1"
    provider TEXT NOT NULL,                     -- 提供商标识，如 openai / anthropic / google / openrouter / azureopenai 等
    model_name TEXT NOT NULL,                   -- 具体模型名，如 gpt-4.1-mini / gpt-4o / claude-3-opus 等
    api_key TEXT NOT NULL,                      -- 对应 provider 的 API Key（可后续加密存储）
    base_url TEXT,                              -- 可选，某些 OpenAI 兼容或自建网关所需，例如 https://api.openai.com/v1
    temperature REAL DEFAULT 0.7,               -- 默认温度
    max_tokens INTEGER,                         -- 可选最大输出 token 数
    is_active INTEGER NOT NULL DEFAULT 0,       -- 0/1，逻辑上保证全表最多一个 1
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

> 注意：
> - SQLite 无法直接做“部分唯一索引（where is_active = 1）”，激活唯一性将在 Service 中保证。
> - 如果后续需要 Embedding 模型，可复用本表或新增 `type` 字段区分 `chat` / `embedding`。

#### 2.1.2 迁移策略

- 当前项目使用 SQLite 直接建表即可，开发环境下可在 `backend/app/db/init_db.py` 中增加建表逻辑或独立迁移脚本。
- 生产环境建议通过 Alembic 等迁移工具管理，此处不展开。

---

## 3. SQLAlchemy 模型

文件：`backend/app/models/ai_models.py`

### 3.1 模型定义规范

- 使用现有 `backend/app/db/sqlite.py` 中的 `Base`；
- 字段命名与数据表一致；
- `is_active` 使用 `Boolean` 类型映射，底层为 0/1。

#### 3.1.1 示例结构（伪代码，仅作规范说明）

> 实现时请严格按字段列表和类型实现，不必完全照抄注释。

```python
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float
from datetime import datetime

from backend.app.db.sqlite import Base


class AIModel(Base):
    __tablename__ = "ai_models"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, comment="模型配置名称")
    provider = Column(String, nullable=False, comment="提供商标识，如 openai、anthropic 等")
    model_name = Column(String, nullable=False, comment="模型名称，如 gpt-4.1-mini")
    api_key = Column(Text, nullable=False, comment="API Key")
    base_url = Column(Text, nullable=True, comment="可选，自定义 Base URL")
    temperature = Column(Float, nullable=False, default=0.7, comment="默认温度")
    max_tokens = Column(Integer, nullable=True, comment="最大输出 token 数，可为空")
    is_active = Column(Boolean, nullable=False, default=False, comment="是否为当前激活模型")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

---

## 4. Pydantic 模型（schemas）

文件：`backend/app/schemas/ai_models.py`

### 4.1 需求概览

- 配置管理页需要：
  - 列表展示：`id`, `name`, `provider`, `model_name`, `is_active`, `updated_at` 等。
  - 创建 / 更新：提交 `name`, `provider`, `model_name`, `api_key`, `base_url`, `temperature`, `max_tokens`。
  - 激活：仅需要 `id`，不修改其他字段。
- 对外 API 不直接暴露 `api_key` 明文给前端（可只在创建 / 更新时从前端接收，在列表/详情响应中不返回明文 key）。

### 4.2 建议的 Pydantic 模型

```python
from datetime import datetime
from pydantic import BaseModel, Field


class AIModelBase(BaseModel):
    name: str = Field(..., description="配置名称")
    provider: str = Field(..., description="提供商标识")
    model_name: str = Field(..., description="模型名称")
    base_url: str | None = Field(None, description="可选 Base URL")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="温度")
    max_tokens: int | None = Field(None, description="最大输出 tokens")


class AIModelCreate(AIModelBase):
    api_key: str = Field(..., description="API Key")


class AIModelUpdate(AIModelBase):
    api_key: str | None = Field(None, description="可选，若为空则不更新")


class AIModelOut(AIModelBase):
    id: int
    is_active: bool
    updated_at: datetime

    class Config:
        orm_mode = True


class ActivateAIModelRequest(BaseModel):
    id: int
```

> 注意：
> - 列表/详情响应 `AIModelOut` 中 **不包含** `api_key` 字段，避免在前端泄露；
> - 创建/更新请求中可以携带明文 key，由服务端负责存储和保护。

---

## 5. Service 层：AIModelService

文件：`backend/app/services/ai_model_service.py`

### 5.1 职责

- 专职管理 `ai_models` 表：增删改查、激活、获取当前激活配置；
- 向 LLM 基础层暴露“与数据库解耦的配置视图”`LLMConfig`；
- **不直接依赖 crewai**，只做数据访问和转换。

### 5.2 关键方法规范

```python
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.app.models.ai_models import AIModel
from backend.app.schemas.ai_models import (
    AIModelCreate,
    AIModelUpdate,
    AIModelOut,
)
from backend.app.llm.config import LLMConfig


class AIModelService:
    """LLM 模型配置管理服务。"""

    @staticmethod
    def list_models(db: Session) -> List[AIModel]:
        ...

    @staticmethod
    def create_model(db: Session, data: AIModelCreate) -> AIModel:
        ...

    @staticmethod
    def update_model(db: Session, model_id: int, data: AIModelUpdate) -> Optional[AIModel]:
        ...

    @staticmethod
    def delete_model(db: Session, model_id: int) -> bool:
        """删除指定配置。如果是当前激活模型，可以选择禁止删除或先取消激活。"""
        ...

    @staticmethod
    def set_active_model(db: Session, model_id: int) -> Optional[AIModel]:
        """将指定模型设为激活状态，并取消其他模型的激活标记。"""
        ...

    @staticmethod
    def get_active_model(db: Session) -> Optional[AIModel]:
        """返回当前激活的 AIModel（若无则返回 None）。"""
        ...

    @staticmethod
    def get_active_llm_config(db: Session) -> LLMConfig:
        """从当前激活的 AIModel 构造 LLMConfig。

        若不存在激活模型，应抛出业务层可识别的异常（例如 RuntimeError 或自定义异常），
        由 API 层返回友好的错误提示，让前端跳转到 LLM 配置页进行配置。
        """
        ...
```

> 约定：
> - `set_active_model` 逻辑：先把所有 `is_active=True` 的记录改为 `False`，再把目标 ID 改为 `True`；
> - `get_active_llm_config` 只负责把 `AIModel` → `LLMConfig`，字段一一映射即可。

---

## 6. LLM 基础层（llm/）

### 6.1 config.py：LLMConfig 定义（已在上文引用）

文件：`backend/app/llm/config.py`

```python
from pydantic import BaseModel


class LLMConfig(BaseModel):
    provider: str
    model_name: str
    base_url: str | None = None
    api_key: str
    temperature: float = 0.7
    max_tokens: int | None = None
```

> 注意：此处不再从环境变量读取配置，**唯一入口是 `AIModelService.get_active_llm_config(db)`**。

### 6.2 base.py：基于 crewai.LLM 构造 LLM 实例

文件：`backend/app/llm/base.py`

#### 6.2.1 依赖说明

- 依赖 `crewai==0.177.0`：

```python
from crewai import LLM
```

- 根据官方文档和 issue 用法，`LLM` 支持以下关键参数：
  - `model`: `str`，模型名称或 `"provider/model_name"` 组合；
  - `api_key`: `str`，当前 provider 的 key；
  - `base_url`: `str | None`，可选自定义 Base URL（用于 OpenAI 兼容或代理网关）；
  - `temperature`: `float`；
  - `max_tokens`: `int | None`。

#### 6.2.2 工厂函数规范

```python
from sqlalchemy.orm import Session
from crewai import LLM

from backend.app.services.ai_model_service import AIModelService


def get_crewai_llm(db: Session) -> LLM:
    """基于当前激活的 AIModel 构造一个 crewai.LLM 实例。

    用法示例（在 service 层）：

        def answer_question(..., db: Session):
            llm = get_crewai_llm(db)
            # 后续可将 llm 传入 crewai.Agent / Crew 使用

    """
    config = AIModelService.get_active_llm_config(db)

    # 推荐做法：将 provider 与 model_name 拼成统一的 model 标识，便于 crewai 识别
    model_full_name = f"{config.provider}/{config.model_name}" if \
        "/" not in config.model_name else config.model_name

    llm = LLM(
        model=model_full_name,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
    return llm
```

> 说明：
> - `model_full_name` 组合方式参考了现有项目中的连接池实现以及社区实践，确保对多 provider 有较好兼容性；
> - 如后续发现某些 provider（例如 `anthropic`、`google`）在 crewai 中需要专门的 wrapper（如 `from crewai.llms import Anthropic`），可在此处按 `provider` 做条件分发，但接口保持不变。

---

## 7. 使用 LLM 的业务 Service 约定

文件示例：`backend/app/services/llm_service.py`

### 7.1 职责

- 面向具体业务场景（如“流程问答”、“骨架生成”）；
- 使用 `get_crewai_llm(db)` 获得当前激活 LLM；
- 基于 crewai 组装 Agents / Tasks / Crew 等；
- 对外暴露简单的 Python 函数给 API 层调用。

### 7.2 典型方法结构（流程问答示例）

> 以下为结构示意，实际业务 prompt / agent 流程由你们后续补充。

```python
from sqlalchemy.orm import Session
from crewai import Agent, Task, Crew, Process

from backend.app.llm.base import get_crewai_llm
from backend.app.services.graph_query_service import get_process_context


def answer_question_with_process_context(
    db: Session,
    question: str,
    process_id: str | None = None,
) -> dict:
    """示例：基于流程上下文 + crewai agents 进行问答。

    返回结构示例：{"answer": str, "process_id": str | None}
    """
    llm = get_crewai_llm(db)

    # 1. 准备业务上下文
    if process_id is not None:
        context = get_process_context(db, process_id)
    else:
        context = None

    # 2. 定义 Agent 和 Task（示意）
    system_prompt = "你是业务流程知识助手，回答问题时参考给定的流程上下文。"

    analyst = Agent(
        role="Process Analyst",
        goal="根据给定流程上下文，回答用户关于该流程的问题",
        backstory="你熟悉业务流程、系统和数据资源。",
        llm=llm,
    )

    task_description = f"用户问题：{question}\n流程上下文：{context}"

    qa_task = Task(
        description=task_description,
        agent=analyst,
        expected_output="一段清晰的中文回答，描述流程的关键步骤、涉及系统和数据资源。",
    )

    crew = Crew(
        agents=[analyst],
        tasks=[qa_task],
        process=Process.sequential,
        llm=llm,  # 也可以只在 Agent 上配置
    )

    result = crew.kickoff()
    # crewai 返回的 result 类型需要以实际版本为准，一般可通过 str(result) 获取文本

    return {
        "answer": str(result),
        "process_id": process_id,
    }
```

> 实际实现时：
> - 可以根据需要拆分为多个 Agents / Tasks；
> - 也可以在不需要复杂多 agent 流程时，仅使用 `llm` 直接生成回答。

---

## 8. API 层设计

### 8.1 LLM 模型配置管理 API：`backend/app/api/v1/llm_models.py`

提供给前端“LLM 配置页面”使用。

#### 8.1.1 路由与接口

```python
from fastapi import APIRouter, Depends, Body, Query
from sqlalchemy.orm import Session

from backend.app.db.sqlite import get_db
from backend.app.schemas.ai_models import (
    AIModelCreate,
    AIModelUpdate,
    AIModelOut,
    ActivateAIModelRequest,
)
from backend.app.services.ai_model_service import AIModelService
from backend.app.core.utils import success_response, error_response


router = APIRouter(prefix="/llm-models", tags=["llm-models"])


@router.get("/list", response_model=list[AIModelOut])
async def list_llm_models(db: Session = Depends(get_db)):
    ...  # 调用 AIModelService.list_models，返回转换为 AIModelOut


@router.post("/create", response_model=AIModelOut)
async def create_llm_model(
    payload: AIModelCreate = Body(...),
    db: Session = Depends(get_db),
):
    ...


@router.post("/update", response_model=AIModelOut)
async def update_llm_model(
    model_id: int = Query(...),
    payload: AIModelUpdate = Body(...),
    db: Session = Depends(get_db),
):
    ...


@router.post("/delete")
async def delete_llm_model(
    model_id: int = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    ...


@router.post("/activate")
async def activate_llm_model(
    payload: ActivateAIModelRequest = Body(...),
    db: Session = Depends(get_db),
):
    ...  # 调用 AIModelService.set_active_model；
         # 若成功，返回 success_response；若失败，返回 error_response
```

> 前端可基于上述接口实现：
> - 模型列表展示；
> - 创建/编辑模型配置；
> - 删除未激活模型；
> - 一键激活指定模型。

### 8.2 业务问答 API：`backend/app/api/v1/llm.py`

现有文件中已存在一个占位接口 `POST /api/v1/chat/ask`，建议调整为调用新的 `llm_service`：

```python
from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from backend.app.db.sqlite import get_db
from backend.app.schemas.llm import ChatRequest, ChatResponse
from backend.app.services.llm_service import answer_question_with_process_context
from backend.app.core.utils import success_response, error_response


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/ask", response_model=ChatResponse, summary="基于流程上下文的 LLM 问答接口")
async def chat(
    req: ChatRequest = Body(...),
    db: Session = Depends(get_db),
) -> dict:
    try:
        result = answer_question_with_process_context(
            db=db,
            question=req.question,
            process_id=req.process_id,
        )
        data = ChatResponse(
            answer=result["answer"],
            process_id=result.get("process_id"),
        )
        return success_response(data=data)
    except Exception as exc:
        return error_response(message=str(exc))
```

> `ChatRequest` / `ChatResponse` 的定义可以沿用当前 `backend/app/schemas/llm.py` 中的结构。

---

## 9. 前端集成要点（简述）

### 9.1 LLM 配置页面

- 使用 `frontend/src/api/llmModels.ts` 封装后端接口：
  - `GET /api/v1/llm-models/list`
  - `POST /api/v1/llm-models/create`
  - `POST /api/v1/llm-models/update`
  - `POST /api/v1/llm-models/delete`
  - `POST /api/v1/llm-models/activate`
- 页面功能：
  - 模型列表 + 当前激活标记；
  - 创建 / 编辑模型配置（包括 provider / model_name / base_url / api_key 等）；
  - 删除非激活模型；
  - 一键激活某条配置。

### 9.2 业务侧使用 LLM

- 现有的业务页面（如流程图、资源库、问答页面）在调用 `/api/v1/chat/ask` 时，无需感知底层用的是哪个模型；
- 切换模型只需在 LLM 配置页激活新的配置，所有后续 LLM 调用都会走新模型。

---

## 10. 实施顺序建议

1. 在 SQLite 中增加 `ai_models` 表；
2. 实现 `backend/app/models/ai_models.py`；
3. 实现 `backend/app/schemas/ai_models.py`；
4. 实现 `backend/app/services/ai_model_service.py`，并在单元测试中验证：
   - CRUD 正常；
   - `set_active_model` 能保证唯一激活；
   - `get_active_llm_config` 能正确构造 `LLMConfig`；
5. 实现 `backend/app/llm/config.py` 与 `backend/app/llm/base.py` 中的 `get_crewai_llm`；
6. 实现 `backend/app/services/llm_service.py` 中至少一个真实使用 crewai 的示例方法（如 `answer_question_with_process_context`）；
7. 实现 `backend/app/api/v1/llm_models.py` 与调整 `backend/app/api/v1/llm.py`；
8. 前端接入 LLM 配置管理页面与问答入口页面；
9. 在开发环境验证：
   - 可在配置页添加 openai / openrouter 等配置；
   - 激活后 `/api/v1/chat/ask` 能正常调用 crewai 并返回回答；
   - 切换激活配置后，新请求使用新模型（可通过返回内容或日志验证）。

---

## 11. 版本与依赖说明

- `crewai==0.177.0` 必须加入 `backend/requirements.txt`；
- 如使用 OpenAI 兼容模型，需保证：
  - `provider` 和 `base_url` 与实际网关一致；
  - `api_key` 具备正确权限；
- 如未来引入更多 provider（Anthropic、Google、Ollama 等），只需在：
  - `AIModel.provider` 中增加支持值；
  - `get_crewai_llm` 中按 `provider` 做必要的适配。

---

> 至此，LLM 子系统的数据库到 API 到 Service 再到 LLM 基础层的设计规范已经完整给出。
> 实现代码时，请严格按照本文件中约定的文件路径、类名与函数签名来组织，以保证后续协作与扩展的一致性。

"""工具共享模块

提供实体发现类工具使用的 LLM 选择器等共享功能。
"""

import json
from typing import List

from backend.app.db.sqlite import SessionLocal
from backend.app.llm.factory import get_lite_task_llm
from backend.app.core.logger import logger


# ============================================================
# 小 LLM 实体选择器
# ============================================================

ENTITY_SELECTOR_PROMPT = """你是一个实体匹配助手。根据用户的查询描述，从候选列表中选择最相关的实体。

## 用户查询
{query}

## 候选列表（JSON 格式）
```json
{candidates}
```

## 任务
请分析用户查询，从上述 JSON 候选列表中选择最相关的实体（最多选择 {limit} 个）。
只返回你认为相关的实体，如果没有相关的可以返回空列表。

## 输出格式
请严格按 JSON 格式返回选中的实体 ID 列表，例如：
{{"selected_ids": ["id1", "id2"]}}

## **重要** 严禁更改 id 的内容！必须从候选列表中原样复制 id 值！

只输出 JSON，不要有其他内容。"""


def call_selector_llm(query: str, candidates: List[dict], id_field: str, limit: int = 5) -> List[str]:
    """调用轻量 LLM 进行实体选择
    
    Args:
        query: 用户查询
        candidates: 候选列表（字典列表）
        id_field: ID 字段名（如 'process_id', 'impl_id' 等）
        limit: 最多选择数量
    
    Returns:
        选中的 ID 列表
    """
    db = SessionLocal()
    try:
        llm = get_lite_task_llm(db)
        
        # 将候选列表转为 JSON 字符串
        candidates_json = json.dumps(candidates, ensure_ascii=False, indent=2)
        
        prompt = ENTITY_SELECTOR_PROMPT.format(
            query=query,
            candidates=candidates_json,
            limit=limit,
        )
        
        logger.debug(f"[EntitySelector] 调用轻量模型")
        
        response = llm.invoke(prompt)
        result_text = response.content.strip()
        logger.debug(f"[EntitySelector] LLM 返回: {result_text}")
        
        # 检查是否为空
        if not result_text:
            logger.warning("[EntitySelector] LLM 返回空内容")
            return []
        
        # 解析 JSON
        if result_text.startswith("```"):
            lines = result_text.split("```")
            if len(lines) >= 2:
                result_text = lines[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
        
        result_text = result_text.strip()
        result = json.loads(result_text)
        return result.get("selected_ids", [])
        
    except Exception as e:
        logger.error(f"[EntitySelector] 调用失败: {e}", exc_info=True)
        return []
    finally:
        db.close()

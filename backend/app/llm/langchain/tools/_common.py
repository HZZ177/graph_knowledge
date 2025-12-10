"""工具共享模块

提供实体发现类工具使用的 LLM 选择器等共享功能。

核心组件：
- extract_keywords: 从用户查询中提取关键词，用于 SQL 预过滤
- call_selector_llm: 调用轻量模型进行实体精排

优化策略（针对大数据量场景）：
1. 关键词提取 → SQL LIKE 预过滤（几百条 → 几十条）
2. 精简候选字段（只传 id + name）
3. 小模型精排（从几十条中选 Top N）
"""

import json
import re
from typing import List

from backend.app.db.sqlite import SessionLocal
from backend.app.llm.factory import get_lite_task_llm
from backend.app.core.logger import logger


# ============================================================
# 关键词提取（用于 SQL 预过滤）
# ============================================================

# 停用词表：这些词对实体匹配没有区分度，过滤掉
_STOPWORDS = {
    # 通用停用词
    '的', '了', '是', '在', '有', '和', '与', '或', '等', '个', '这', '那', '什么', '怎么', '如何',
    # 实体搜索场景的无效词（用户常说但无区分度）
    '接口', '流程', '功能', '查询', '获取', '搜索', '查找', '相关', '信息', '数据', '记录',
    '表', '库', '服务', '系统', '模块', '方法', '函数', '处理', '操作', '业务', '逻辑',
}


def extract_keywords(query: str, max_keywords: int = 5) -> List[str]:
    """从用户查询中提取关键词
    
    用于 SQL LIKE 预过滤，将几百条候选缩减到几十条，再交给小模型精排。
    
    策略：
    1. 按标点符号和空格切分
    2. 过滤停用词（对实体匹配无区分度的词）
    3. 过滤太短的词（< 2字符）
    4. 最多返回 max_keywords 个关键词
    
    Args:
        query: 用户的自然语言查询，如 "月卡开通支付回调"
        max_keywords: 最多返回的关键词数量
    
    Returns:
        关键词列表，如 ["月卡", "开通", "支付", "回调"]
    
    Examples:
        >>> extract_keywords("月卡开通接口")
        ['月卡', '开通']
        >>> extract_keywords("查询用户订单信息")
        ['用户', '订单']
    """
    # 按标点符号和空格切分
    tokens = re.split(r'[\s,，。、/\-_()（）【】\[\]]+', query)
    
    # 过滤：去停用词、去短词、去空串
    keywords = [
        token.strip() 
        for token in tokens 
        if token.strip() and len(token.strip()) >= 2 and token.strip() not in _STOPWORDS
    ]
    
    # 去重并保持顺序
    seen = set()
    unique_keywords = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique_keywords.append(kw)
    
    result = unique_keywords[:max_keywords]
    logger.debug(f"[extract_keywords] '{query}' → {result}")
    return result


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

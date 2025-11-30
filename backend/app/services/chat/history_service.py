"""会话历史管理服务

负责 LangChain Agent 对话历史的管理：
- 获取/清除/截断历史
- 替换 AI 回复
- 生成会话标题
"""

from typing import Dict, Any, List

from sqlalchemy.orm import Session
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from backend.app.llm.factory import get_langchain_llm
from backend.app.models.conversation import Conversation
from backend.app.core.logger import logger


def _get_agent_config(thread_id: str) -> Dict[str, Any]:
    """获取 Agent 执行配置"""
    return {
        "configurable": {
            "thread_id": thread_id,
        },
        "recursion_limit": 80,
    }


async def get_conversation_history(thread_id: str) -> List[Dict[str, str]]:
    """获取会话历史
    
    Args:
        thread_id: 会话 ID
        
    Returns:
        消息列表 [{"role": "user"|"assistant"|"tool", "content": "..."}]
    """
    return await get_thread_history(thread_id)


async def clear_conversation(thread_id: str) -> bool:
    """清除会话历史
    
    Args:
        thread_id: 会话 ID
        
    Returns:
        是否成功
    """
    return await clear_thread_history(thread_id)


async def truncate_conversation(thread_id: str, keep_pairs: int) -> bool:
    """截断会话历史，只保留前 N 对对话
    
    Args:
        thread_id: 会话 ID
        keep_pairs: 保留的对话对数
        
    Returns:
        是否成功
    """
    return await truncate_thread_history(thread_id, keep_pairs)


async def clear_thread_history(thread_id: str) -> bool:
    """清除指定会话的对话历史
    
    Args:
        thread_id: 会话 ID
        
    Returns:
        是否成功清除
    """
    try:
        # 当前实现仅记录日志，不对底层检查点做实际删除操作
        # 如需真正清除，可在此处新增基于 AsyncSqliteSaver 的删除逻辑
        logger.info(f"[HistoryService] 清除会话历史: thread_id={thread_id}")
        return True
    except Exception as e:
        logger.error(f"[HistoryService] 清除会话历史失败: {e}")
        return False


async def truncate_thread_history(thread_id: str, keep_pairs: int) -> bool:
    """截断会话历史，只保留前 N 对对话
    
    Args:
        thread_id: 会话 ID
        keep_pairs: 保留的对话对数（一对 = 一个 user + 对应的 assistant/tool 消息）
        
    Returns:
        是否成功截断
    """
    try:
        async with AsyncSqliteSaver.from_conn_string("llm_checkpoints.db") as memory:
            config = _get_agent_config(thread_id)
            
            # 使用 aget_tuple 获取完整的检查点信息（包含 metadata）
            checkpoint_tuple = await memory.aget_tuple(config)
            
            if not checkpoint_tuple or not checkpoint_tuple.checkpoint:
                logger.warning(f"[HistoryService] 会话不存在: thread_id={thread_id}")
                return False
            
            checkpoint = checkpoint_tuple.checkpoint
            if "channel_values" not in checkpoint:
                logger.warning(f"[HistoryService] 检查点格式异常: thread_id={thread_id}")
                return False
            
            messages = checkpoint["channel_values"].get("messages", [])
            if not messages:
                return True
            
            # 统计对话对数，找到截断位置
            # 每遇到一个 human 消息算一对的开始
            pair_count = 0
            cut_index = 0
            
            for i, msg in enumerate(messages):
                msg_type = getattr(msg, "type", None)
                if msg_type == "human":
                    pair_count += 1
                    if pair_count > keep_pairs:
                        cut_index = i
                        break
            else:
                # 没有超出，无需截断
                return True
            
            # 截断消息列表
            truncated_messages = messages[:cut_index]
            checkpoint["channel_values"]["messages"] = truncated_messages
            
            # 使用原 checkpoint_tuple 的 config 和 metadata 来更新
            await memory.aput(
                checkpoint_tuple.config,
                checkpoint,
                checkpoint_tuple.metadata,
                {}  # new_versions
            )
            
            logger.info(f"[HistoryService] 截断会话历史: thread_id={thread_id}, 保留 {keep_pairs} 对, 原消息数 {len(messages)}, 截断后 {len(truncated_messages)}")
            return True
            
    except Exception as e:
        logger.error(f"[HistoryService] 截断会话历史失败: {e}")
        return False


async def get_thread_history(thread_id: str) -> list:
    """获取指定会话的对话历史
    
    Args:
        thread_id: 会话 ID
        
    Returns:
        消息列表，包含 user/assistant/tool 类型消息
        - role: "user" | "assistant" | "tool"
        - content: 消息内容
        - tool_name: 工具名称（仅 tool 类型）
        - tool_calls: 工具调用信息（仅 assistant 调用工具时）
    """
    try:
        # 为每次查询单独打开 AsyncSqliteSaver 上下文
        async with AsyncSqliteSaver.from_conn_string("llm_checkpoints.db") as memory:
            config = _get_agent_config(thread_id)
            
            # 尝试获取检查点（异步）
            checkpoint = await memory.aget(config)
        if checkpoint and "channel_values" in checkpoint:
            messages = checkpoint["channel_values"].get("messages", [])
            result = []
            for msg in messages:
                msg_type = getattr(msg, "type", None)
                content = getattr(msg, "content", "")
                
                if msg_type == "human":
                    result.append({"role": "user", "content": content})
                elif msg_type == "ai":
                    # 检查是否有工具调用
                    tool_calls = getattr(msg, "tool_calls", None)
                    if tool_calls:
                        # 有工具调用的 AI 消息
                        result.append({
                            "role": "assistant",
                            "content": content,
                            "tool_calls": [
                                {"name": tc.get("name", ""), "args": tc.get("args", {})}
                                for tc in tool_calls
                            ]
                        })
                    else:
                        # 普通 AI 消息
                        result.append({"role": "assistant", "content": content})
                elif msg_type == "tool":
                    # 工具返回消息
                    tool_name = getattr(msg, "name", "unknown")
                    result.append({
                        "role": "tool",
                        "content": content,
                        "tool_name": tool_name
                    })
            
            return result
        return []
    except Exception as e:
        logger.error(f"[HistoryService] 获取会话历史失败: {e}")
        return []


async def get_raw_messages(thread_id: str) -> list:
    """获取原始的 LangChain 消息对象列表
    
    Args:
        thread_id: 会话 ID
        
    Returns:
        原始消息对象列表
    """
    try:
        async with AsyncSqliteSaver.from_conn_string("llm_checkpoints.db") as memory:
            config = _get_agent_config(thread_id)
            checkpoint_tuple = await memory.aget_tuple(config)
            
            if not checkpoint_tuple or not checkpoint_tuple.checkpoint:
                return []
            
            return checkpoint_tuple.checkpoint.get("channel_values", {}).get("messages", [])
    except Exception as e:
        logger.error(f"[HistoryService] 获取原始消息失败: {e}")
        return []


async def replace_assistant_response(thread_id: str, user_msg_index: int, new_messages: list) -> bool:
    """替换指定用户消息对应的 AI 回复
    
    Args:
        thread_id: 会话 ID
        user_msg_index: 用户消息在"用户消息列表"中的索引（从0开始）
        new_messages: 新的 AI 回复消息列表（LangChain 消息对象）
        
    Returns:
        是否成功
    """
    try:
        async with AsyncSqliteSaver.from_conn_string("llm_checkpoints.db") as memory:
            config = _get_agent_config(thread_id)
            checkpoint_tuple = await memory.aget_tuple(config)
            
            if not checkpoint_tuple or not checkpoint_tuple.checkpoint:
                logger.warning(f"[HistoryService] 会话不存在: thread_id={thread_id}")
                return False
            
            checkpoint = checkpoint_tuple.checkpoint
            messages = checkpoint.get("channel_values", {}).get("messages", [])
            if not messages:
                return False
            
            # 找到第 N 个 human 消息的实际位置
            human_count = 0
            target_human_idx = -1
            for i, msg in enumerate(messages):
                if getattr(msg, "type", None) == "human":
                    if human_count == user_msg_index:
                        target_human_idx = i
                        break
                    human_count += 1
            
            if target_human_idx == -1:
                logger.warning(f"[HistoryService] 找不到用户消息 index={user_msg_index}")
                return False
            
            # 找到下一个 human 消息的位置（或消息末尾）
            next_human_idx = len(messages)
            for i in range(target_human_idx + 1, len(messages)):
                if getattr(messages[i], "type", None) == "human":
                    next_human_idx = i
                    break
            
            # 构建新的消息列表：前面 + 目标用户消息 + 新回复 + 后续消息
            new_message_list = (
                messages[:target_human_idx + 1] +  # 包含目标用户消息
                new_messages +                      # 新的 AI 回复
                messages[next_human_idx:]           # 后续消息（从下一个用户消息开始）
            )
            
            checkpoint["channel_values"]["messages"] = new_message_list
            
            await memory.aput(
                checkpoint_tuple.config,
                checkpoint,
                checkpoint_tuple.metadata,
                {}
            )
            
            logger.info(f"[HistoryService] 替换 AI 回复成功: thread_id={thread_id}, user_msg_index={user_msg_index}, 原消息数={len(messages)}, 新消息数={len(new_message_list)}")
            return True
            
    except Exception as e:
        logger.error(f"[HistoryService] 替换 AI 回复失败: {e}")
        return False


async def generate_conversation_title(db: Session, thread_id: str) -> str:
    """根据会话历史生成标题
    
    Args:
        db: 数据库会话
        thread_id: 会话 ID
        
    Returns:
        生成的标题（10字以内）
    """
    try:
        # 1. 获取历史记录
        history = await get_thread_history(thread_id)
        if not history:
            return "新对话"
            
        # 2. 找到第一条用户消息
        first_user_msg = next((m for m in history if m["role"] == "user"), None)
        if not first_user_msg:
            return "新对话"
            
        question = first_user_msg["content"]
        
        # 3. 调用 LLM 生成标题
        llm = get_langchain_llm(db)
        prompt = f"""
请根据以下用户问题，生成一个简短的会话标题（5个字以上，不超过15个字）。
只返回标题内容，不要包含引号或其他说明。

用户问题：{question}
标题：
"""
        
        response = await llm.ainvoke(prompt)
        title = response.content.strip().replace('"', '').replace('《', '').replace('》', '')
        
        # 再次截断以防万一
        title = title[:20]
        
        # 4. 更新数据库
        try:
            conv = db.query(Conversation).filter(Conversation.id == thread_id).first()
            if conv:
                conv.title = title
                db.commit()
        except Exception as e:
            logger.error(f"[HistoryService] 保存标题到数据库失败: {e}")
            
        return title
        
    except Exception as e:
        logger.error(f"[HistoryService] 生成标题失败: {e}")
        return "新对话"

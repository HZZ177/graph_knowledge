"""会话历史管理服务

负责 LangChain Agent 对话历史的管理：
- 获取/清除/截断历史
- 替换 AI 回复
- 生成会话标题
"""

from typing import Dict, List
import uuid

from sqlalchemy.orm import Session
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_core.messages import HumanMessage, AIMessage

from backend.app.llm.factory import get_lite_task_llm
from backend.app.models.chat import Conversation
from backend.app.core.logger import logger
from backend.app.llm.langchain.agent import get_agent_config


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
            config = get_agent_config(thread_id)
            
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
        - attachments: 文件附件（仅用户消息，从多模态 content 解析）
    """
    try:
        # 为每次查询单独打开 AsyncSqliteSaver 上下文
        async with AsyncSqliteSaver.from_conn_string("llm_checkpoints.db") as memory:
            config = get_agent_config(thread_id)
            
            # 尝试获取检查点（异步）
            checkpoint = await memory.aget(config)
        if checkpoint and "channel_values" in checkpoint:
            messages = checkpoint["channel_values"].get("messages", [])
            result = []
            for msg in messages:
                msg_type = getattr(msg, "type", None)
                content = getattr(msg, "content", "")
                
                if msg_type == "human":
                    # 优先从 additional_kwargs 获取原始附件信息
                    additional_kwargs = getattr(msg, "additional_kwargs", {}) or {}
                    original_attachments = additional_kwargs.get("original_attachments", [])
                    
                    if original_attachments:
                        # 有原始附件信息，直接使用
                        logger.info(f"[HistoryService] 从 additional_kwargs 恢复 {len(original_attachments)} 个原始附件")
                        # 解析 content 获取纯文本（过滤掉解析后的文档内容）
                        text_content = _extract_user_question(content)
                        msg_data = {"role": "user", "content": text_content}
                        msg_data["attachments"] = original_attachments
                        result.append(msg_data)
                    else:
                        # 没有原始附件信息，回退到从 content 解析（兼容旧消息）
                        logger.info(f"[HistoryService] Human message content type: {type(content)}")
                        text_content, attachments = _parse_multimodal_content(content)
                        logger.info(f"[HistoryService] Parsed: text_len={len(text_content) if text_content else 0}, attachments_count={len(attachments)}")
                        msg_data = {"role": "user", "content": text_content}
                        if attachments:
                            msg_data["attachments"] = attachments
                        result.append(msg_data)
                elif msg_type == "ai":
                    # 检查是否有工具调用
                    tool_calls = getattr(msg, "tool_calls", None)
                    # AI 消息 content 也可能是数组（多模态），提取文本
                    text_content = _extract_text_from_content(content)
                    if tool_calls:
                        # 有工具调用的 AI 消息
                        result.append({
                            "role": "assistant",
                            "content": text_content,
                            "tool_calls": [
                                {"name": tc.get("name", ""), "args": tc.get("args", {})}
                                for tc in tool_calls
                            ]
                        })
                    else:
                        # 普通 AI 消息
                        result.append({"role": "assistant", "content": text_content})
                elif msg_type == "tool":
                    # 工具返回消息
                    tool_name = getattr(msg, "name", "unknown")
                    result.append({
                        "role": "tool",
                        "content": content if isinstance(content, str) else str(content),
                        "tool_name": tool_name
                    })
            
            return result
        return []
    except Exception as e:
        logger.error(f"[HistoryService] 获取会话历史失败: {e}")
        return []


def _parse_multimodal_content(content) -> tuple:
    """解析多模态 content，提取文本和附件
    
    Args:
        content: HumanMessage 的 content，可能是字符串或数组
        
    Returns:
        (text_content, attachments) 元组
    """
    if isinstance(content, str):
        return content, []
    
    if not isinstance(content, list):
        return str(content), []
    
    text_parts = []
    attachments = []
    
    for item in content:
        if not isinstance(item, dict):
            continue
            
        item_type = item.get("type", "")
        
        if item_type == "text":
            text = item.get("text", "")
            # 过滤掉附件引用文本（以 "[附件:" 开头）
            if text and not text.strip().startswith("[附件:"):
                text_parts.append(text)
        
        elif item_type == "image_url":
            image_url = item.get("image_url", {})
            url = image_url.get("url", "") if isinstance(image_url, dict) else ""
            if url:
                # 从 URL 提取文件名
                filename = url.split("/")[-1].split("?")[0] if "/" in url else "image"
                attachments.append({
                    "file_id": "",  # 历史记录中没有 file_id
                    "url": url,
                    "type": "image",
                    "filename": filename,
                    "content_type": "image/png"  # 默认
                })
    
    return "".join(text_parts), attachments


def _extract_text_from_content(content) -> str:
    """从 content 中提取纯文本
    
    Args:
        content: 消息的 content，可能是字符串或数组
        
    Returns:
        文本内容
    """
    if isinstance(content, str):
        return content
    
    if not isinstance(content, list):
        return str(content)
    
    text_parts = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            text_parts.append(item.get("text", ""))
    
    return "".join(text_parts)


def _extract_user_question(content) -> str:
    """从 content 中提取用户的原始问题（过滤掉解析后的文档内容）
    
    Args:
        content: HumanMessage 的 content，可能是字符串或数组
        
    Returns:
        用户的原始问题文本
    """
    if isinstance(content, str):
        return content
    
    if not isinstance(content, list):
        return str(content)
    
    text_parts = []
    for item in content:
        if not isinstance(item, dict):
            continue
        
        if item.get("type") == "text":
            text = item.get("text", "")
            # 过滤掉文档内容（以 "--- 文档:" 开头的块）
            if text and not text.strip().startswith("--- 文档:") and not text.strip().startswith("\n\n--- 文档:"):
                # 也过滤掉附件引用和文档解析失败的提示
                if not text.strip().startswith("[附件:") and not text.strip().startswith("[文档"):
                    text_parts.append(text)
    
    return "".join(text_parts).strip()


async def get_raw_messages(thread_id: str) -> list:
    """获取原始的 LangChain 消息对象列表
    
    Args:
        thread_id: 会话 ID
        
    Returns:
        原始消息对象列表
    """
    try:
        async with AsyncSqliteSaver.from_conn_string("llm_checkpoints.db") as memory:
            config = get_agent_config(thread_id)
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
            config = get_agent_config(thread_id)
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


def _extract_ai_summary(content: str, max_length: int = 300) -> str:
    """从 AI 回复中提取纯正文摘要（去除 think 块和工具占位符）
    
    Args:
        content: AI 回复原始内容
        max_length: 最大字符数
        
    Returns:
        提取的正文摘要
    """
    import re
    
    if not content:
        return ""
    
    # 移除 <think>...</think> 块
    text = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
    # 移除未闭合的 <think> 块（流式输出中断的情况）
    text = re.sub(r'<think>.*', '', text, flags=re.DOTALL)
    # 移除工具占位符 <!--TOOL:xxx:n-->
    text = re.sub(r'<!--TOOL:[^>]+-->', '', text)
    # 清理多余空白
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    
    if len(text) > max_length:
        text = text[:max_length] + "..."
    
    return text


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
        
        # 3. 提取 AI 回复的正文摘要（去除 think/tool，最多 300 字）
        first_ai_msg = next((m for m in history if m["role"] == "assistant"), None)
        ai_summary = _extract_ai_summary(first_ai_msg["content"], 300) if first_ai_msg else ""
        
        # 4. 调用轻量 LLM 生成标题
        llm = get_lite_task_llm(db)
        
        if ai_summary:
            prompt = f"""请根据以下对话内容，生成一个简短的会话标题（5个字以上，不超过15个字）。
只返回标题内容，不要包含引号或其他说明。

用户问题：{question}

AI回复摘要：{ai_summary}

标题："""
        else:
            prompt = f"""请根据以下用户问题，生成一个简短的会话标题（5个字以上，不超过15个字）。
只返回标题内容，不要包含引号或其他说明。

用户问题：{question}
标题："""
        
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


async def save_error_to_history(
    thread_id: str,
    question: str,
    partial_response: str,
    error_message: str,
) -> bool:
    """将报错信息保存到对话历史
    
    当对话中途报错时，将用户问题、已生成的部分回复和错误信息一起保存，
    以便恢复历史对话时能看到报错的那次对话。
    
    Args:
        thread_id: 会话 ID
        question: 用户问题
        partial_response: 已生成的部分 AI 回复
        error_message: 错误消息
        
    Returns:
        是否成功保存
    """
    try:
        async with AsyncSqliteSaver.from_conn_string("llm_checkpoints.db") as memory:
            config = get_agent_config(thread_id)
            checkpoint_tuple = await memory.aget_tuple(config)
            
            # 构造错误提示内容（与前端显示一致，不泄露堆栈）
            if partial_response:
                error_content = f"{partial_response}\n\n---\n\n对话中断：{error_message}"
            else:
                error_content = f"对话失败：{error_message}"
            
            # 构造消息
            user_msg = HumanMessage(content=question)
            ai_msg = AIMessage(content=error_content)
            
            if checkpoint_tuple and checkpoint_tuple.checkpoint:
                # 已有 checkpoint，只追加 AI 错误响应（用户消息已由 Agent 保存）
                checkpoint = checkpoint_tuple.checkpoint
                messages = checkpoint.get("channel_values", {}).get("messages", [])
                # 不再追加 user_msg，因为 Agent 执行时已经保存了用户消息
                messages.append(ai_msg)
                checkpoint["channel_values"]["messages"] = messages
                
                await memory.aput(
                    checkpoint_tuple.config,
                    checkpoint,
                    checkpoint_tuple.metadata,
                    {}
                )
            else:
                # 新会话，创建 checkpoint
                new_checkpoint = {
                    "v": 1,
                    "id": str(uuid.uuid4()),
                    "ts": str(uuid.uuid4()),
                    "channel_values": {
                        "messages": [user_msg, ai_msg]
                    },
                    "channel_versions": {},
                    "versions_seen": {},
                }
                await memory.aput(
                    config,
                    new_checkpoint,
                    {"source": "error_recovery", "step": 0},
                    {}
                )
            
            logger.info(f"[HistoryService] 保存错误到历史成功: thread_id={thread_id}, partial_len={len(partial_response)}")
            return True
            
    except Exception as e:
        logger.error(f"[HistoryService] 保存错误到历史失败: {e}")
        return False

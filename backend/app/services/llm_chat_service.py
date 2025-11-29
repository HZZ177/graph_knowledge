"""LLM Chat 服务 - 基于 LangChain 的知识图谱问答

支持：
- 自然语言实体发现（业务流程、接口、数据资源）
- 图上下文获取和探索
- 多轮对话（通过 thread_id 管理会话历史）
- 流式输出
"""

import json
import uuid
import time
from typing import Any, Dict, Optional, List

from sqlalchemy.orm import Session
from starlette.websockets import WebSocket
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from datetime import datetime, timezone
from backend.app.models.conversation import Conversation
from backend.app.llm.langchain_chat_agent import (
    create_chat_agent,
    get_agent_config,
    get_thread_history,
    clear_thread_history,
    truncate_thread_history,
    get_raw_messages,
    replace_assistant_response,
)
from backend.app.core.logger import logger


# 所有工具名列表，用于分离拼接的工具名
TOOL_NAMES = [
    "search_code_context",
    "list_directory",
    "read_file_range",  # 必须在 read_file 之前，因为是更长的前缀
    "read_file",
    "search_businesses",
    "search_implementations",
    "search_data_resources",
    "search_steps",
    "get_business_context",
    "get_implementation_context",
    "get_implementation_business_usages",
    "get_resource_context",
    "get_resource_business_usages",
    "get_neighbors",
    "get_path_between_entities",
]


def _split_concatenated_tool_name(name: str) -> List[str]:
    """分离被拼接的工具名称
    
    例如 'search_stepssearch_implementations' -> ['search_steps', 'search_implementations']
    """
    if not name:
        return []
    
    # 先检查是否是有效的单个工具名
    if name in TOOL_NAMES:
        return [name]
    
    # 尝试分离拼接的工具名
    result = []
    remaining = name
    
    while remaining:
        found = False
        # 按工具名长度从长到短尝试匹配
        for tool_name in sorted(TOOL_NAMES, key=len, reverse=True):
            if remaining.startswith(tool_name):
                result.append(tool_name)
                remaining = remaining[len(tool_name):]
                found = True
                break
        
        if not found:
            # 无法继续分离，可能有未知工具名
            if remaining:
                logger.warning(f"[Chat] 无法分离工具名片段: {remaining}")
                result.append(remaining)
            break
    
    if len(result) > 1:
        logger.info(f"[Chat] 成功分离拼接的工具名: {name} -> {result}")
    
    return result


def _generate_tool_summaries(tool_name: str, tool_input: dict, tool_output: str) -> tuple[str, str]:
    """根据工具名称生成输入摘要和输出摘要
    
    Returns:
        (input_summary, output_summary)
    """
    input_summary = ""
    output_summary = ""
    
    # 尝试解析输出为 JSON
    output_data = None
    try:
        output_data = json.loads(tool_output)
    except (json.JSONDecodeError, TypeError):
        pass
    
    # ========== 搜索类工具 ==========
    if tool_name in ("search_businesses", "search_steps", "search_implementations", 
                     "search_data_resources", "search_code_context"):
        # 输入摘要
        query = tool_input.get("query", "")
        if query:
            input_summary = f"关键词: {query}"
        
        # 输出摘要
        if output_data:
            if "candidates" in output_data:
                count = len(output_data["candidates"])
                total = output_data.get("total_count", count)
                if count > 0:
                    output_summary = f"找到 {count} 个结果" + (f" (共 {total} 个)" if total > count else "")
                else:
                    output_summary = output_data.get("message", "未找到结果")
            elif "results" in output_data:
                count = len(output_data["results"])
                output_summary = f"找到 {count} 个相关代码片段" if count > 0 else "未找到相关代码"
            elif "error" in output_data:
                output_summary = f"查询失败"
        
    # ========== 文件读取类工具 ==========
    elif tool_name == "read_file":
        path = tool_input.get("path", "")
        if path:
            # 只显示文件名
            filename = path.split("/")[-1].split("\\")[-1]
            input_summary = f"文件: {filename}"
        
        if output_data:
            if "content" in output_data:
                lines = output_data["content"].count("\n") + 1
                output_summary = f"读取成功 ({lines} 行)"
            elif "error" in output_data:
                output_summary = "读取失败"
        elif tool_output and not tool_output.startswith("{"):
            lines = tool_output.count("\n") + 1
            output_summary = f"读取成功 ({lines} 行)"
    
    elif tool_name == "read_file_range":
        path = tool_input.get("path", "")
        start_line = tool_input.get("start_line", 0)
        end_line = tool_input.get("end_line", 0)
        if path:
            filename = path.split("/")[-1].split("\\")[-1]
            input_summary = f"文件: {filename} (L{start_line}-{end_line})"
        
        if tool_output and "error" not in tool_output.lower():
            output_summary = f"读取成功 ({end_line - start_line + 1} 行)"
        else:
            output_summary = "读取失败"
    
    elif tool_name == "list_directory":
        path = tool_input.get("path", "/")
        depth = tool_input.get("max_depth", 2)
        input_summary = f"目录: {path}" + (f" (深度 {depth})" if depth != 2 else "")
        
        if output_data:
            if "entries" in output_data:
                count = len(output_data["entries"])
                output_summary = f"列出 {count} 个条目"
            elif "error" in output_data:
                output_summary = "列出失败"
    
    # ========== 上下文获取类工具（支持批量查询）==========
    elif tool_name == "get_business_context":
        process_ids = tool_input.get("process_ids", [])
        count = len(process_ids)
        input_summary = f"批量查询 {count} 个业务" if count > 1 else f"业务ID: {process_ids[0][:20] if process_ids else ''}"
        
        if output_data:
            if "results" in output_data:
                total = output_data.get("total", 0)
                output_summary = f"获取 {total} 个业务上下文"
            elif "error" in output_data:
                output_summary = "获取失败"
    
    elif tool_name == "get_implementation_context":
        impl_ids = tool_input.get("impl_ids", [])
        count = len(impl_ids)
        input_summary = f"批量查询 {count} 个接口" if count > 1 else f"接口ID: {impl_ids[0][:20] if impl_ids else ''}"
        
        if output_data:
            if "results" in output_data:
                total = output_data.get("total", 0)
                output_summary = f"获取 {total} 个接口上下文"
            elif "error" in output_data:
                output_summary = "获取失败"
    
    elif tool_name == "get_implementation_business_usages":
        impl_ids = tool_input.get("impl_ids", [])
        count = len(impl_ids)
        input_summary = f"批量查询 {count} 个接口使用情况" if count > 1 else f"接口ID: {impl_ids[0][:20] if impl_ids else ''}"
        
        if output_data:
            if "results" in output_data:
                total = output_data.get("total", 0)
                output_summary = f"获取 {total} 个接口的业务使用"
            elif "error" in output_data:
                output_summary = "查询失败"
    
    elif tool_name == "get_resource_context":
        resource_ids = tool_input.get("resource_ids", [])
        count = len(resource_ids)
        input_summary = f"批量查询 {count} 个资源" if count > 1 else f"资源ID: {resource_ids[0][:20] if resource_ids else ''}"
        
        if output_data:
            if "results" in output_data:
                total = output_data.get("total", 0)
                output_summary = f"获取 {total} 个资源上下文"
            elif "error" in output_data:
                output_summary = "获取失败"
    
    elif tool_name == "get_resource_business_usages":
        resource_ids = tool_input.get("resource_ids", [])
        count = len(resource_ids)
        input_summary = f"批量查询 {count} 个资源使用情况" if count > 1 else f"资源ID: {resource_ids[0][:20] if resource_ids else ''}"
        
        if output_data:
            if "results" in output_data:
                total = output_data.get("total", 0)
                output_summary = f"获取 {total} 个资源的业务使用"
            elif "error" in output_data:
                output_summary = "查询失败"
    
    # ========== 图遍历类工具 ==========
    elif tool_name == "get_neighbors":
        node_ids = tool_input.get("node_ids", [])
        depth = tool_input.get("depth", 1)
        count = len(node_ids)
        input_summary = f"批量查询 {count} 个节点邻居" if count > 1 else f"节点: {node_ids[0][:20] if node_ids else ''}"
        if depth > 1:
            input_summary += f" (深度 {depth})"
        
        if output_data:
            if "neighbors" in output_data:
                neighbor_count = len(output_data["neighbors"])
                output_summary = f"找到 {neighbor_count} 个邻居节点"
            elif "error" in output_data:
                output_summary = "查询失败"
    
    elif tool_name == "get_path_between_entities":
        source_id = tool_input.get("source_id", "")
        target_id = tool_input.get("target_id", "")
        input_summary = f"路径查询"
        
        if output_data:
            if "path" in output_data:
                path_len = len(output_data["path"])
                output_summary = f"找到路径 ({path_len} 跳)"
            elif "error" in output_data or output_data.get("path") is None:
                output_summary = "未找到路径"
    
    # 默认处理
    if not input_summary and tool_input:
        # 取第一个参数作为摘要
        first_key = next(iter(tool_input.keys()), None)
        if first_key:
            first_val = str(tool_input[first_key])
            input_summary = f"{first_key}: {first_val[:30]}..." if len(first_val) > 30 else f"{first_key}: {first_val}"
    
    if not output_summary:
        if output_data and "error" in output_data:
            output_summary = "执行失败"
        elif len(tool_output) > 0:
            output_summary = "执行完成"
        else:
            output_summary = "无结果"
    
    return input_summary, output_summary


async def streaming_chat(
    db: Session,
    question: str,
    websocket: WebSocket,
    thread_id: Optional[str] = None,
) -> str:
    """基于 LangChain 的流式问答
    
    使用 LangChain Agent + 8 个工具实现自然语言问答。
    支持多轮对话，通过 thread_id 管理会话历史。
    
    Args:
        db: 数据库会话
        question: 用户问题
        websocket: WebSocket 连接，用于流式输出
        thread_id: 会话 ID，用于多轮对话。如果为空则创建新会话。
        
    Returns:
        完整的回答文本
    """
    # 生成请求 ID 和会话 ID
    request_id = str(uuid.uuid4())
    if not thread_id:
        thread_id = str(uuid.uuid4())
        
    # 维护 Conversation 元数据
    try:
        conv = db.query(Conversation).filter(Conversation.id == thread_id).first()
        if not conv:
            conv = Conversation(id=thread_id, title="新对话")
            db.add(conv)
        else:
            conv.updated_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        logger.error(f"保存会话元数据失败: {e}")
        # 不阻断主流程
    
    logger.info(f"[Chat] 开始处理问题: {question[:100]}..., request_id={request_id}, thread_id={thread_id}")
    
    try:
        # 发送开始消息
        await websocket.send_text(json.dumps({
            "type": "start",
            "request_id": request_id,
            "thread_id": thread_id,
        }, ensure_ascii=False))
        
        # 打开 AsyncSqliteSaver 作为检查点存储
        async with AsyncSqliteSaver.from_conn_string("llm_checkpoints.db") as checkpointer:
            # 创建 Agent
            agent = create_chat_agent(db, checkpointer=checkpointer)
            config = get_agent_config(thread_id)
            
            # 构造输入
            inputs = {
                "messages": [HumanMessage(content=question)]
            }
            
            # 流式执行
            full_response = ""
            tool_calls_info: List[Dict[str, Any]] = []
            # 用于跟踪工具调用耗时和输入
            tool_start_times: Dict[str, float] = {}
            tool_inputs: Dict[str, dict] = {}  # run_id -> tool_input
            llm_call_count = 0
            tool_placeholder_id = 0  # 工具占位符 ID 计数器
            # tool_call_id -> placeholder_id 映射，用于关联 tool_start/end 和占位符
            tool_call_to_placeholder: Dict[str, int] = {}
            
            logger.info(f"[Chat] 开始流式执行, thread_id={thread_id}, recursion_limit={config.get('recursion_limit', 25)}")
            
            async for event in agent.astream_events(inputs, config, version="v2"):
                event_type = event.get("event")
                event_name = event.get("name", "")
                
                # 检查是否有错误
                if "error" in event:
                    error_info = event.get("error")
                    logger.error(f"[Chat] 事件包含错误: {error_info}")
                    raise Exception(f"Agent 执行错误: {error_info}")
                
                # ========== LLM 事件 ==========
                if event_type == "on_chat_model_start":
                    # LLM 开始调用
                    llm_call_count += 1
                    input_data = event.get("data", {}).get("input", {})
                    messages = input_data.get("messages", [[]])
                    msg_count = len(messages[0]) if messages else 0
                    logger.info(f"[Chat] LLM调用#{llm_call_count} 开始: model={event_name}, 输入消息数={msg_count}，消息内容={messages[0][-1].content[:100]}...")
                    
                elif event_type == "on_chat_model_stream":
                    # LLM 流式输出
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        content = chunk.content
                        full_response += content
                        # DEBUG: 记录每个 chunk 的内容
                        content_preview = content.replace('\n', '\\n')[:100]
                        logger.info(f"[Chat] Stream chunk: len={len(content)}, content={content_preview}")
                        await websocket.send_text(json.dumps({
                            "type": "stream",
                            "content": content,
                        }, ensure_ascii=False))
                        
                elif event_type == "on_chat_model_end":
                    # LLM 调用结束
                    output = event.get("data", {}).get("output")
                    output_len = len(output.content) if output and hasattr(output, "content") else 0
                    # DEBUG: 打印当前累计的完整响应
                    full_preview = full_response.replace('\n', '\\n')[:500]
                    logger.info(f"[Chat] LLM调用#{llm_call_count} 当前 full_response: len={len(full_response)}, content={full_preview}...")
                    # 检查是否有工具调用
                    tool_calls = getattr(output, "tool_calls", []) if output else []
                    if tool_calls:
                        tool_names = [tc.get("name", "unknown") for tc in tool_calls]
                        logger.info(f"[Chat] LLM调用#{llm_call_count} 结束: 输出长度={output_len}, 工具调用={tool_names}")
                        logger.debug(f"[Chat] 工具调用原始数据: {tool_calls}")
                        
                        # 关键改动：在 LLM 决定调用工具时，立即发送工具占位符
                        # 这样可以保证占位符在正确的位置（当前 LLM 输出之后、下一轮 LLM 之前）
                        for tc in tool_calls:
                            tool_name = tc.get("name", "unknown")
                            tool_call_id = tc.get("id", "")  # LangChain 的 tool_call id
                            tool_placeholder_id += 1
                            placeholder = f"<!--TOOL:{tool_name}:{tool_placeholder_id}-->"
                            full_response += placeholder
                            # 记录映射关系
                            tool_call_to_placeholder[tool_call_id] = tool_placeholder_id
                            logger.info(f"[Chat] 发送工具占位符: {placeholder}, tool_call_id={tool_call_id}")
                            await websocket.send_text(json.dumps({
                                "type": "stream",
                                "content": placeholder,
                            }, ensure_ascii=False))
                    else:
                        logger.info(f"[Chat] LLM调用#{llm_call_count} 结束: 输出长度={output_len}")
                
                # ========== 工具事件 ==========
                elif event_type == "on_tool_start":
                    # 工具开始调用
                    tool_name = event.get("name", "unknown")
                    tool_input = event.get("data", {}).get("input", {})
                    run_id = event.get("run_id", "")
                    tool_start_times[run_id] = time.time()
                    tool_inputs[run_id] = tool_input  # 保存输入供结束时使用
                    
                    # 尝试找到对应的 placeholder_id（通过 tool_call_id 映射）
                    # 注意：run_id 和 tool_call_id 可能不同，需要通过工具名和顺序匹配
                    # 简化处理：按顺序匹配，第一个未匹配的工具
                    placeholder_id = None
                    for tc_id, p_id in list(tool_call_to_placeholder.items()):
                        # 找到就使用并移除，避免重复匹配
                        placeholder_id = p_id
                        del tool_call_to_placeholder[tc_id]
                        break
                    
                    # 截断过长的输入用于日志
                    input_str = json.dumps(tool_input, ensure_ascii=False) if isinstance(tool_input, dict) else str(tool_input)
                    input_preview = input_str[:300] + "..." if len(input_str) > 300 else input_str
                    logger.info(f"[Chat] 工具调用开始: {tool_name}, placeholder_id={placeholder_id}, 输入: {input_preview}")
                    await websocket.send_text(json.dumps({
                        "type": "tool_start",
                        "tool_name": tool_name,
                        "tool_id": placeholder_id,  # 新增：关联占位符 ID
                        "tool_input": tool_input,
                    }, ensure_ascii=False))
                    
                elif event_type == "on_tool_end":
                    # 工具调用结束
                    tool_name = event.get("name", "unknown")
                    tool_output = event.get("data", {}).get("output", "")
                    run_id = event.get("run_id", "")
                    # 计算耗时
                    elapsed = time.time() - tool_start_times.pop(run_id, time.time())
                    # 获取之前保存的输入
                    tool_input = tool_inputs.pop(run_id, {})
                    # tool_output 可能是 ToolMessage 对象，需要转换为字符串
                    output_str = str(tool_output.content) if hasattr(tool_output, "content") else str(tool_output)
                    output_len = len(output_str)
                    # 截断过长的输出用于日志
                    output_preview = output_str[:200] + "..." if len(output_str) > 200 else output_str
                    logger.info(f"[Chat] 工具调用结束: {tool_name}, 耗时={elapsed:.2f}s, 输出长度={output_len}")
                    logger.debug(f"[Chat] 工具输出预览: {output_preview}")
                    
                    # 生成摘要
                    input_summary, output_summary = _generate_tool_summaries(tool_name, tool_input, output_str)
                    
                    tool_calls_info.append({
                        "name": tool_name,
                        "output_length": output_len,
                        "elapsed": round(elapsed, 2),
                        "input_summary": input_summary,
                        "output_summary": output_summary,
                    })
                    await websocket.send_text(json.dumps({
                        "type": "tool_end",
                        "tool_name": tool_name,
                        "input_summary": input_summary,
                        "output_summary": output_summary,
                        "elapsed": round(elapsed, 2),
                    }, ensure_ascii=False))
                
                # ========== Chain 事件 ==========
                elif event_type == "on_chain_start":
                    # Chain 开始（通常是 Agent 内部的子链）
                    logger.debug(f"[Chat] Chain开始: {event_name}")
                    
                elif event_type == "on_chain_end":
                    # Chain 结束
                    logger.debug(f"[Chat] Chain结束: {event_name}")
                    
                elif event_type == "on_chain_error":
                    # 链式错误
                    error_data = event.get("data", {})
                    logger.error(f"[Chat] Chain错误: name={event_name}, error={error_data}")
                    raise Exception(f"Chain 执行错误: {error_data}")
                
                # ========== 其他事件 ==========
                else:
                    # 其他事件类型（retriever, prompt 等）
                    if event_type in ("on_retriever_start", "on_retriever_end"):
                        logger.debug(f"[Chat] Retriever事件: {event_type}, name={event_name}")
                    elif event_type in ("on_prompt_start", "on_prompt_end"):
                        logger.debug(f"[Chat] Prompt事件: {event_type}, name={event_name}")
                    else:
                        logger.debug(f"[Chat] 其他事件: {event_type}, name={event_name}")
        
        # 发送最终结果消息
        await websocket.send_text(json.dumps({
            "type": "result",
            "request_id": request_id,
            "thread_id": thread_id,
            "content": full_response,
            "tool_calls": tool_calls_info,
        }, ensure_ascii=False))
        
        logger.info(f"[Chat] 问答完成, request_id={request_id}, 输出长度: {len(full_response)}, 工具调用: {len(tool_calls_info)}")
        return full_response
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error("[Chat] 问答失败: " + str(e) + "\n" + error_traceback)
        await websocket.send_text(json.dumps({
            "type": "error",
            "request_id": request_id,
            "thread_id": thread_id,
            "error": str(e),
            "traceback": error_traceback,
        }, ensure_ascii=False))
        raise


async def get_conversation_history(thread_id: str) -> List[Dict[str, str]]:
    """获取会话历史
    
    Args:
        thread_id: 会话 ID
        
    Returns:
        消息列表 [{"role": "user"|"assistant", "content": "..."}]
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


async def streaming_regenerate(
    db: Session,
    thread_id: str,
    user_msg_index: int,
    websocket: WebSocket,
) -> str:
    """精准重新生成指定用户消息对应的 AI 回复
    
    Args:
        db: 数据库会话
        thread_id: 会话 ID
        user_msg_index: 用户消息索引（第几个用户消息，从0开始）
        websocket: WebSocket 连接
        
    Returns:
        新生成的回答文本
    """
    request_id = str(uuid.uuid4())
    logger.info(f"[Regenerate] 开始重新生成: thread_id={thread_id}, user_msg_index={user_msg_index}")
    
    try:
        # 1. 获取原始消息列表
        raw_messages = await get_raw_messages(thread_id)
        if not raw_messages:
            raise Exception("会话不存在或消息为空")
        
        # 2. 找到目标用户消息
        human_count = 0
        target_human_idx = -1
        target_question = ""
        for i, msg in enumerate(raw_messages):
            if getattr(msg, "type", None) == "human":
                if human_count == user_msg_index:
                    target_human_idx = i
                    target_question = getattr(msg, "content", "")
                    break
                human_count += 1
        
        if target_human_idx == -1:
            raise Exception(f"找不到用户消息 index={user_msg_index}")
        
        # 3. 发送开始消息
        await websocket.send_text(json.dumps({
            "type": "start",
            "request_id": request_id,
            "thread_id": thread_id,
        }, ensure_ascii=False))
        
        # 4. 使用临时会话生成新回复
        temp_thread_id = f"regen_{thread_id}_{uuid.uuid4().hex[:8]}"
        
        async with AsyncSqliteSaver.from_conn_string("llm_checkpoints.db") as checkpointer:
            # 创建 Agent
            agent = create_chat_agent(db, checkpointer=checkpointer)
            temp_config = get_agent_config(temp_thread_id)
            
            # 构造输入：截断到目标用户消息之前的历史 + 目标用户消息
            history_messages = list(raw_messages[:target_human_idx])  # 不包含目标用户消息
            inputs = {
                "messages": history_messages + [HumanMessage(content=target_question)]
            }
            
            # 流式执行并收集新生成的消息
            full_response = ""
            tool_calls_info: List[Dict[str, Any]] = []
            tool_start_times: Dict[str, float] = {}
            tool_inputs: Dict[str, dict] = {}  # run_id -> tool_input
            llm_call_count = 0
            tool_placeholder_id = 0  # 工具占位符 ID 计数器
            tool_call_to_placeholder: Dict[str, int] = {}  # tool_call_id -> placeholder_id
            
            logger.info(f"[Regenerate] 开始流式执行, temp_thread_id={temp_thread_id}, 历史消息数={len(history_messages)}")
            
            async for event in agent.astream_events(inputs, temp_config, version="v2"):
                event_type = event.get("event")
                event_name = event.get("name", "")
                
                # ========== LLM 事件 ==========
                if event_type == "on_chat_model_start":
                    llm_call_count += 1
                    input_data = event.get("data", {}).get("input", {})
                    messages = input_data.get("messages", [[]])
                    msg_count = len(messages[0]) if messages else 0
                    logger.info(f"[Regenerate] LLM调用#{llm_call_count} 开始: model={event_name}, 输入消息数={msg_count}")
                
                elif event_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        content = chunk.content
                        full_response += content
                        await websocket.send_text(json.dumps({
                            "type": "stream",
                            "content": content,
                        }, ensure_ascii=False))
                
                elif event_type == "on_chat_model_end":
                    output = event.get("data", {}).get("output")
                    output_len = len(output.content) if output and hasattr(output, "content") else 0
                    tool_calls = getattr(output, "tool_calls", []) if output else []
                    if tool_calls:
                        tool_names = [tc.get("name", "unknown") for tc in tool_calls]
                        logger.info(f"[Regenerate] LLM调用#{llm_call_count} 结束: 输出长度={output_len}, 工具调用={tool_names}")
                        
                        # 关键改动：在 LLM 决定调用工具时，立即发送工具占位符
                        for tc in tool_calls:
                            tool_name = tc.get("name", "unknown")
                            tool_call_id = tc.get("id", "")
                            tool_placeholder_id += 1
                            placeholder = f"<!--TOOL:{tool_name}:{tool_placeholder_id}-->"
                            full_response += placeholder
                            tool_call_to_placeholder[tool_call_id] = tool_placeholder_id
                            logger.info(f"[Regenerate] 发送工具占位符: {placeholder}")
                            await websocket.send_text(json.dumps({
                                "type": "stream",
                                "content": placeholder,
                            }, ensure_ascii=False))
                    else:
                        logger.info(f"[Regenerate] LLM调用#{llm_call_count} 结束: 输出长度={output_len}")
                
                # ========== 工具事件 ==========
                elif event_type == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_input = event.get("data", {}).get("input", {})
                    run_id = event.get("run_id", "")
                    tool_start_times[run_id] = time.time()
                    tool_inputs[run_id] = tool_input
                    
                    # 找到对应的 placeholder_id
                    placeholder_id = None
                    for tc_id, p_id in list(tool_call_to_placeholder.items()):
                        placeholder_id = p_id
                        del tool_call_to_placeholder[tc_id]
                        break
                    
                    input_str = json.dumps(tool_input, ensure_ascii=False) if isinstance(tool_input, dict) else str(tool_input)
                    input_preview = input_str[:300] + "..." if len(input_str) > 300 else input_str
                    logger.info(f"[Regenerate] 工具调用开始: {tool_name}, placeholder_id={placeholder_id}, 输入: {input_preview}")
                    await websocket.send_text(json.dumps({
                        "type": "tool_start",
                        "tool_name": tool_name,
                        "tool_id": placeholder_id,
                        "tool_input": tool_input,
                    }, ensure_ascii=False))
                    
                elif event_type == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    tool_output = event.get("data", {}).get("output", "")
                    run_id = event.get("run_id", "")
                    elapsed = time.time() - tool_start_times.pop(run_id, time.time())
                    tool_input = tool_inputs.pop(run_id, {})
                    output_str = str(tool_output.content) if hasattr(tool_output, "content") else str(tool_output)
                    output_len = len(output_str)
                    logger.info(f"[Regenerate] 工具调用结束: {tool_name}, 耗时={elapsed:.2f}s, 输出长度={output_len}")
                    
                    # 生成摘要
                    input_summary, output_summary = _generate_tool_summaries(tool_name, tool_input, output_str)
                    
                    tool_calls_info.append({
                        "name": tool_name,
                        "output_length": output_len,
                        "elapsed": round(elapsed, 2),
                        "input_summary": input_summary,
                        "output_summary": output_summary,
                    })
                    await websocket.send_text(json.dumps({
                        "type": "tool_end",
                        "tool_name": tool_name,
                        "input_summary": input_summary,
                        "output_summary": output_summary,
                        "elapsed": round(elapsed, 2),
                    }, ensure_ascii=False))
                
                # ========== 错误事件 ==========
                elif event_type == "on_chain_error":
                    error_data = event.get("data", {})
                    logger.error(f"[Regenerate] Chain错误: name={event_name}, error={error_data}")
                    raise Exception(f"Chain 执行错误: {error_data}")
            
            # 5. 获取临时会话生成的新消息
            temp_checkpoint = await checkpointer.aget(temp_config)
            if temp_checkpoint and "channel_values" in temp_checkpoint:
                temp_messages = temp_checkpoint["channel_values"].get("messages", [])
                # 提取新生成的 AI 回复（跳过历史和用户消息）
                new_ai_messages = temp_messages[len(history_messages) + 1:]  # +1 跳过用户消息
                
                # 6. 更新原会话的检查点
                success = await replace_assistant_response(thread_id, user_msg_index, new_ai_messages)
                if not success:
                    logger.warning(f"[Regenerate] 更新检查点失败")
        
        # 7. 发送最终结果
        await websocket.send_text(json.dumps({
            "type": "result",
            "request_id": request_id,
            "thread_id": thread_id,
            "content": full_response,
            "tool_calls": tool_calls_info,
            "user_msg_index": user_msg_index,
        }, ensure_ascii=False))
        
        logger.info(f"[Regenerate] 重新生成完成: thread_id={thread_id}, 输出长度={len(full_response)}")
        return full_response
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"[Regenerate] 失败: {e}\n{error_traceback}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "request_id": request_id,
            "thread_id": thread_id,
            "error": str(e),
        }, ensure_ascii=False))
        raise

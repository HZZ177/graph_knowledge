"""Chat 服务 - 基于 LangChain 的知识图谱问答

支持：
- 自然语言实体发现（业务流程、接口、数据资源）
- 图上下文获取和探索
- 多轮对话（通过 thread_id 管理会话历史）
- 流式输出
"""

import json
import re
import uuid
import time
from typing import Any, Dict, Optional, List

from sqlalchemy.orm import Session
from starlette.websockets import WebSocket
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from datetime import datetime, timezone
from backend.app.models.chat import Conversation
from backend.app.llm.langchain.registry import (
    AgentRegistry,
    get_agent_run_config,
)
from backend.app.services.chat.history_service import (
    get_raw_messages,
    replace_assistant_response,
    save_error_to_history,
)
from backend.app.core.logger import logger


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
                     "search_data_resources"):
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
    
    # ========== 代码上下文搜索 ==========
    elif tool_name == "search_code_context":
        # 输入摘要：显示代码库名称和查询
        workspace = tool_input.get("workspace", "")
        query = tool_input.get("query", "")
        parts = []
        if workspace:
            parts.append(f"代码库: {workspace}")
        if query:
            # 查询可能较长，截断显示
            display_query = query[:40] + "..." if len(query) > 40 else query
            parts.append(f"查询: {display_query}")
        input_summary = " | ".join(parts) if parts else ""
        
        # 输出摘要
        if output_data:
            if "content" in output_data and isinstance(output_data["content"], list):
                count = len(output_data["content"])
                output_summary = f"找到 {count} 个相关代码片段" if count > 0 else "未找到相关代码"
            elif "error" in output_data:
                output_summary = "查询失败"
            elif "text" in output_data:
                output_summary = "找到相关代码"
            else:
                output_summary = "执行完成"
        
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
    
    # ========== 代码精确搜索 ==========
    elif tool_name == "grep_code":
        pattern = tool_input.get("pattern", "")
        workspace = tool_input.get("workspace", "")
        file_pattern = tool_input.get("file_pattern", "")
        
        parts = []
        if workspace:
            parts.append(f"代码库: {workspace}")
        if pattern:
            display_pattern = pattern[:30] + "..." if len(pattern) > 30 else pattern
            parts.append(f"搜索: {display_pattern}")
        if file_pattern:
            parts.append(f"文件: {file_pattern}")
        input_summary = " | ".join(parts) if parts else ""
        
        if output_data:
            if "matches" in output_data:
                count = len(output_data["matches"])
                output_summary = f"找到 {count} 处匹配" if count > 0 else "未找到匹配"
            elif "error" in output_data:
                output_summary = "搜索失败"
    
    # ========== 日志查询工具 ==========
    elif tool_name == "search_logs":
        # 输入摘要：服务名 + 关键词 + 时间范围
        server_name = tool_input.get("server_name", "")
        keyword = tool_input.get("keyword", "")
        keyword2 = tool_input.get("keyword2", "")
        start_time = tool_input.get("start_time", "")
        end_time = tool_input.get("end_time", "")
        
        parts = []
        if server_name:
            parts.append(f"服务: {server_name}")
        if keyword:
            display_kw = keyword[:20] + "..." if len(keyword) > 20 else keyword
            parts.append(f"关键词: {display_kw}")
        if keyword2:
            parts.append(f"+ {keyword2[:15]}")
        if start_time and end_time:
            # 只显示时间部分，去掉日期
            start_short = start_time.split(" ")[-1] if " " in start_time else start_time
            end_short = end_time.split(" ")[-1] if " " in end_time else end_time
            parts.append(f"时间: {start_short}~{end_short}")
        input_summary = " | ".join(parts) if parts else ""
        
        # 输出摘要：从纯文本中解析
        # 格式: "[server] 共X条 第Y/Z页\n..."
        if tool_output:
            # 检查是否是错误响应（JSON格式）
            if output_data and "error" in output_data:
                output_summary = f"查询失败: {output_data.get('error', '')[:30]}"
            else:
                # 解析纯文本格式
                match = re.search(r'共(\d+)条\s*第(\d+)/(\d+)页', tool_output)
                if match:
                    total = match.group(1)
                    page = match.group(2)
                    total_pages = match.group(3)
                    output_summary = f"找到 {total} 条日志 (第{page}/{total_pages}页)"
                elif "无日志" in tool_output or "(无日志)" in tool_output:
                    output_summary = "未找到日志"
                else:
                    # 尝试统计行数
                    lines = tool_output.strip().split("\n")
                    log_lines = len([l for l in lines if l.strip() and not l.startswith("[")])
                    output_summary = f"返回 {log_lines} 条日志" if log_lines > 0 else "查询完成"
    
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
    agent_type: str = "knowledge_qa",
    agent_context: Optional[Dict[str, Any]] = None,
    attachments: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """基于 LangChain 的流式问答（支持多模态）
    
    使用 LangChain Agent + 工具实现自然语言问答。
    支持多轮对话，通过 thread_id 管理会话历史。
    支持多 Agent 类型，通过 agent_type 切换不同的 Agent。
    支持多模态输入（图片、文档等附件）。
    
    Args:
        db: 数据库会话
        question: 用户问题
        websocket: WebSocket 连接，用于流式输出
        thread_id: 会话 ID，用于多轮对话。如果为空则创建新会话。
        agent_type: Agent 类型标识，默认为 "knowledge_qa"
        agent_context: 动态上下文配置，用于注入到 Agent 和工具（如日志查询的业务线配置）
        attachments: 文件附件列表（多模态支持）
        
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
            conv = Conversation(id=thread_id, title="新对话", agent_type=agent_type)
            db.add(conv)
        else:
            conv.updated_at = datetime.now(timezone.utc)
            # 如果 agent_type 变更，也更新（支持同一会话切换 agent）
            if conv.agent_type != agent_type:
                conv.agent_type = agent_type
        db.commit()
    except Exception as e:
        logger.error(f"保存会话元数据失败: {e}")
        # 不阻断主流程
    
    # 记录附件信息
    from backend.app.services.chat.multimodal import extract_attachments_summary
    attachments_summary = extract_attachments_summary(attachments)
    logger.info(f"[Chat] 开始处理问题: {question[:100]}..., request_id={request_id}, thread_id={thread_id}, agent_type={agent_type}, 附件={attachments_summary}")
    
    # 在 try 外初始化，便于 except 块访问
    full_response = ""
    
    try:
        # 发送开始消息
        await websocket.send_text(json.dumps({
            "type": "start",
            "request_id": request_id,
            "thread_id": thread_id,
            "agent_type": agent_type,
        }, ensure_ascii=False))
        
        # 打开 AsyncSqliteSaver 作为检查点存储
        async with AsyncSqliteSaver.from_conn_string("llm_checkpoints.db") as checkpointer:
            # 从 AgentRegistry 获取 Agent（每次请求需重新绑定 checkpointer）
            registry = AgentRegistry.get_instance()
            agent = registry.get_agent(agent_type, db, checkpointer, agent_context)
            
            # 获取运行时配置（包含 agent_context，供工具使用）
            config = get_agent_run_config(thread_id, agent_context)
            
            # 构造多模态消息（异步版本，支持文档解析）
            from backend.app.services.chat.multimodal import build_multimodal_message_async
            human_message = await build_multimodal_message_async(question, attachments)
            
            # 构造输入
            inputs = {
                "messages": [human_message]
            }
            
            # 如果有附件，关联文件到对话
            if attachments:
                from backend.app.models.chat import FileUpload
                for att in attachments:
                    file_id = att.get('file_id')
                    if file_id:
                        try:
                            file_record = db.query(FileUpload).filter(FileUpload.id == file_id).first()
                            if file_record and not file_record.conversation_id:
                                file_record.conversation_id = thread_id
                                db.commit()
                                logger.info(f"[Chat] 文件关联到对话: {file_record.filename} -> {thread_id}")
                        except Exception as e:
                            logger.warning(f"[Chat] 文件关联失败: {e}")
            
            # 流式执行
            tool_calls_info: List[Dict[str, Any]] = []
            llm_call_count = 0
            llm_first_token_logged = False  # 标记当前 LLM 调用是否已打印首 token 日志
            tool_placeholder_id = 0  # 工具占位符 ID 计数器
            tool_batch_id = 0  # 批量工具调用的批次 ID
            # tool_call_id -> 工具调用信息映射（包含 placeholder_id, tool_name, tool_args, start_time, batch_id）
            tool_call_to_placeholder: Dict[str, Dict[str, Any]] = {}
            
            logger.info(f"[Chat] 开始流式执行, thread_id={thread_id}, recursion_limit={config.get('recursion_limit', 25)}")
            
            # 使用 astream_events 获取 token 级流式响应
            async for event in agent.astream_events(inputs, config, version="v2"):
                event_type = event.get("event")
                event_name = event.get("name", "")
                
                # ========== LLM 开始事件 ==========
                if event_type == "on_chat_model_start":
                    llm_call_count += 1
                    llm_first_token_logged = False  # 重置首 token 日志标记
                    input_data = event.get("data", {}).get("input", {})
                    messages = input_data.get("messages", [[]])
                    msg_count = len(messages[0]) if messages else 0
                    logger.info(f"[Chat] LLM调用 round-{llm_call_count} 开始: model={event_name}, 历史消息数={msg_count}")
                
                # ========== LLM 流式输出事件（token 级）==========
                elif event_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        content = chunk.content
                        full_response += content
                        
                        # 首 token 日志（每轮 LLM 调用只打印一次）
                        if not llm_first_token_logged:
                            llm_first_token_logged = True
                            logger.info(f"[Chat] LLM调用 round-{llm_call_count} 接收到首字响应：开始流式输出")
                        
                        # 发送流式内容（逐 token）
                        await websocket.send_text(json.dumps({
                            "type": "stream",
                            "content": content,
                        }, ensure_ascii=False))
                
                # ========== LLM 结束事件（可能包含工具调用）==========
                elif event_type == "on_chat_model_end":
                    output = event.get("data", {}).get("output")
                    output_len = len(output.content) if output and hasattr(output, "content") else 0
                    
                    # 检查是否有工具调用
                    tool_calls = getattr(output, "tool_calls", []) if output else []
                    if tool_calls:
                        tool_names = [tc.get("name", "unknown") for tc in tool_calls]
                        batch_size = len(tool_calls)
                        is_batch = batch_size > 1
                        
                        if is_batch:
                            logger.info(f"[Chat] LLM调用 round-{llm_call_count} 工具批量调用({batch_size}个): {tool_names}")
                        else:
                            logger.info(f"[Chat] LLM调用 round-{llm_call_count} 请求工具调用: {tool_names}")
                        logger.debug(f"[Chat] LLM调用工具原始参数: {tool_calls}")
                        
                        # 为这一批工具调用分配批次 ID
                        tool_batch_id += 1
                        current_batch_id = tool_batch_id
                        
                        # 发送工具占位符和 tool_start 消息
                        for idx, tc in enumerate(tool_calls):
                            tool_name = tc.get("name", "unknown")
                            tool_call_id = tc.get("id", "")
                            tool_args = tc.get("args", {})
                            tool_placeholder_id += 1
                            placeholder = f"<!--TOOL:{tool_name}:{tool_placeholder_id}-->"
                            full_response += placeholder
                            # 记录映射关系（包含批次信息）
                            tool_call_to_placeholder[tool_call_id] = {
                                "placeholder_id": tool_placeholder_id,
                                "tool_name": tool_name,
                                "tool_args": tool_args,
                                "start_time": time.time(),
                                "batch_id": current_batch_id,
                                "batch_size": batch_size,
                                "batch_index": idx,
                            }
                            logger.debug(f"[Chat] 发送工具占位符: {placeholder}, tool_call_id={tool_call_id}, batch={current_batch_id}/{batch_size}")
                            # 先发送 tool_start 消息（包含批次信息）- 确保前端先收到batch信息
                            await websocket.send_text(json.dumps({
                                "type": "tool_start",
                                "tool_name": tool_name,
                                "tool_id": tool_placeholder_id,
                                "tool_input": tool_args,
                                "batch_id": current_batch_id,
                                "batch_size": batch_size,
                                "batch_index": idx,
                            }, ensure_ascii=False))
                            # 再发送占位符到前端（通过 stream 消息）
                            await websocket.send_text(json.dumps({
                                "type": "stream",
                                "content": placeholder,
                            }, ensure_ascii=False))
                    else:
                        content_preview = (output.content[:200] if output and output.content else "").replace('\n', '\\n')
                        logger.info(f"[Chat] LLM调用 round-{llm_call_count} 结束: 输出长度={output_len}, preview={content_preview}...")
                
                # ========== 工具开始事件 ==========
                elif event_type == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_input = event.get("data", {}).get("input", {})
                    run_id = event.get("run_id", "")
                    
                    # 记录开始时间和输入参数（用于 on_tool_end 时计算耗时和生成摘要）
                    tool_call_to_placeholder[f"run_{run_id}"] = {
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "start_time": time.time(),
                    }
                    
                    input_str = json.dumps(tool_input, ensure_ascii=False) if isinstance(tool_input, dict) else str(tool_input)
                    input_preview = input_str[:300] + "..." if len(input_str) > 300 else input_str
                    logger.info(f"[Chat] 工具执行开始: {tool_name}, run_id={run_id}, 输入: {input_preview}")
                
                # ========== 工具结束事件 ==========
                elif event_type == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    tool_output = event.get("data", {}).get("output", "")
                    run_id = event.get("run_id", "")
                    
                    # 获取之前保存的运行时信息
                    run_info = tool_call_to_placeholder.pop(f"run_{run_id}", {})
                    tool_input = run_info.get("tool_input", {})
                    start_time = run_info.get("start_time", time.time())
                    elapsed = time.time() - start_time
                    
                    # 通过工具名查找对应的 placeholder 信息（包含批次信息）
                    placeholder_id = None
                    batch_id = None
                    batch_size = 1
                    batch_index = 0
                    tool_args = tool_input
                    
                    # 查找匹配的 tool_call 记录
                    for tc_id, info in list(tool_call_to_placeholder.items()):
                        if not tc_id.startswith("run_") and info.get("tool_name") == tool_name:
                            placeholder_id = info.get("placeholder_id")
                            tool_args = info.get("tool_args", tool_input)
                            batch_id = info.get("batch_id")
                            batch_size = info.get("batch_size", 1)
                            batch_index = info.get("batch_index", 0)
                            start_time = info.get("start_time", start_time)
                            elapsed = time.time() - start_time
                            del tool_call_to_placeholder[tc_id]
                            break
                    
                    output_str = str(tool_output.content) if hasattr(tool_output, "content") else str(tool_output)
                    output_len = len(output_str)
                    output_preview = output_str[:200] + "..." if len(output_str) > 200 else output_str
                    
                    logger.info(f"[Chat] 工具调用结束: {tool_name}, placeholder_id={placeholder_id}, batch={batch_id}/{batch_size}, 耗时={elapsed:.2f}s, 输出长度={output_len}")
                    logger.debug(f"[Chat] 工具输出预览: {output_preview}")
                    
                    # 生成摘要
                    input_summary, output_summary = _generate_tool_summaries(tool_name, tool_args, output_str)
                    
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
                        "tool_id": placeholder_id,
                        "input_summary": input_summary,
                        "output_summary": output_summary,
                        "elapsed": round(elapsed, 2),
                        "batch_id": batch_id,
                        "batch_size": batch_size,
                        "batch_index": batch_index,
                    }, ensure_ascii=False))
                
                # ========== 错误事件 ==========
                elif event_type == "on_chain_error":
                    error_data = event.get("data", {})
                    logger.error(f"[Chat] Chain错误: name={event_name}, error={error_data}")
                    # 不立即抛出，让流程继续尝试完成
        
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
        
        # 保存错误到对话历史，确保即使报错也能恢复
        await save_error_to_history(
            thread_id=thread_id,
            question=question,
            partial_response=full_response,
            error_message=str(e),
        )
        
        await websocket.send_text(json.dumps({
            "type": "error",
            "request_id": request_id,
            "thread_id": thread_id,
            "error": str(e),
        }, ensure_ascii=False))
        # 不再 raise，避免 WebSocket 异常关闭导致前端重复触发 onError


async def streaming_regenerate(
    db: Session,
    thread_id: str,
    user_msg_index: int,
    websocket: WebSocket,
    agent_type: str = "knowledge_qa",
) -> str:
    """精准重新生成指定用户消息对应的 AI 回复
    
    Args:
        db: 数据库会话
        thread_id: 会话 ID
        user_msg_index: 用户消息索引（第几个用户消息，从0开始）
        websocket: WebSocket 连接
        agent_type: Agent 类型标识，默认为 "knowledge_qa"
        
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
        target_human_msg = None  # 保留原始消息对象（包含多模态内容）
        for i, msg in enumerate(raw_messages):
            if getattr(msg, "type", None) == "human":
                if human_count == user_msg_index:
                    target_human_idx = i
                    target_human_msg = msg  # 保留原始消息对象
                    break
                human_count += 1
        
        if target_human_idx == -1 or target_human_msg is None:
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
            # 从 AgentRegistry 获取 Agent（每次请求需重新绑定 checkpointer）
            registry = AgentRegistry.get_instance()
            agent = registry.get_agent(agent_type, db, checkpointer)
            
            # 获取运行时配置
            temp_config = get_agent_run_config(temp_thread_id)
            
            # 构造输入：截断到目标用户消息之前的历史 + 目标用户消息（保留多模态内容）
            history_messages = list(raw_messages[:target_human_idx])  # 不包含目标用户消息
            inputs = {
                "messages": history_messages + [target_human_msg]  # 使用原始消息对象，保留多模态内容
            }
            
            # 流式执行并收集新生成的消息
            full_response = ""
            tool_calls_info: List[Dict[str, Any]] = []
            tool_start_times: Dict[str, float] = {}
            tool_inputs: Dict[str, dict] = {}  # run_id -> tool_input
            tool_placeholder_id = 0
            tool_call_to_placeholder: Dict[str, dict] = {}  # tool_call_id -> {placeholder_id, batch_id, batch_size, batch_index}
            run_id_to_tool_info: Dict[str, dict] = {}  # run_id -> {placeholder_id, batch_id, batch_size, batch_index}
            llm_call_count = 0
            
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
                    logger.info(f"[Regenerate] LLM调用#{llm_call_count} 开始: model={event_name}, 历史消息数={msg_count}")
                
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
                        
                        # 生成批次信息
                        current_batch_id = None
                        batch_size = len(tool_calls)
                        if batch_size > 1:
                            current_batch_id = llm_call_count  # 使用LLM调用次数作为批次ID
                        
                        # 关键改动：在 LLM 决定调用工具时，立即发送工具占位符和batch信息
                        for idx, tc in enumerate(tool_calls):
                            tool_name = tc.get("name", "unknown")
                            tool_call_id = tc.get("id", "")
                            tool_args = tc.get("args", {})
                            tool_placeholder_id += 1
                            placeholder = f"<!--TOOL:{tool_name}:{tool_placeholder_id}-->"
                            full_response += placeholder
                            
                            # 记录批次信息到映射表
                            tool_call_to_placeholder[tool_call_id] = {
                                "placeholder_id": tool_placeholder_id,
                                "batch_id": current_batch_id,
                                "batch_size": batch_size,
                                "batch_index": idx,
                            }
                            
                            logger.debug(f"[Regenerate] 发送工具占位符: {placeholder}, batch={current_batch_id}/{batch_size}")
                            
                            # 先发送 tool_start（包含batch信息）
                            await websocket.send_text(json.dumps({
                                "type": "tool_start",
                                "tool_name": tool_name,
                                "tool_id": tool_placeholder_id,
                                "tool_input": tool_args,
                                "batch_id": current_batch_id,
                                "batch_size": batch_size,
                                "batch_index": idx,
                            }, ensure_ascii=False))
                            
                            # 再发送占位符
                            await websocket.send_text(json.dumps({
                                "type": "stream",
                                "content": placeholder,
                            }, ensure_ascii=False))
                    else:
                        logger.info(f"[Regenerate] LLM调用 round-{llm_call_count} 结束: 输出长度={output_len}")
                
                # ========== 工具事件 ==========
                elif event_type == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_input = event.get("data", {}).get("input", {})
                    run_id = event.get("run_id", "")
                    tool_start_times[run_id] = time.time()
                    tool_inputs[run_id] = tool_input
                    
                    input_str = json.dumps(tool_input, ensure_ascii=False) if isinstance(tool_input, dict) else str(tool_input)
                    input_preview = input_str[:300] + "..." if len(input_str) > 300 else input_str
                    logger.info(f"[Regenerate] 工具调用开始: {tool_name}, 输入: {input_preview}")
                    
                    # 注意：tool_start 消息已经在 on_chat_model_end 时发送，这里不再重复发送
                    
                elif event_type == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    tool_output = event.get("data", {}).get("output", "")
                    run_id = event.get("run_id", "")
                    elapsed = time.time() - tool_start_times.pop(run_id, time.time())
                    tool_input = tool_inputs.pop(run_id, {})
                    output_str = str(tool_output.content) if hasattr(tool_output, "content") else str(tool_output)
                    output_len = len(output_str)
                    
                    # 查找对应的批次信息
                    placeholder_id = None
                    batch_id = None
                    batch_size = 1
                    batch_index = 0
                    for tc_id, info in list(tool_call_to_placeholder.items()):
                        if info.get("placeholder_id"):
                            # 找到第一个未使用的工具调用记录（按顺序匹配）
                            placeholder_id = info.get("placeholder_id")
                            batch_id = info.get("batch_id")
                            batch_size = info.get("batch_size", 1)
                            batch_index = info.get("batch_index", 0)
                            del tool_call_to_placeholder[tc_id]
                            break
                    
                    logger.info(f"[Regenerate] 工具调用结束: {tool_name}, placeholder_id={placeholder_id}, batch={batch_id}/{batch_size}, 耗时={elapsed:.2f}s, 输出长度={output_len}")
                    
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
                        "tool_id": placeholder_id,
                        "input_summary": input_summary,
                        "output_summary": output_summary,
                        "elapsed": round(elapsed, 2),
                        "batch_id": batch_id,
                        "batch_size": batch_size,
                        "batch_index": batch_index,
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
        # 不再 raise，避免 WebSocket 异常关闭导致前端重复触发 onError

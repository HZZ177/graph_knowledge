"""修复流式响应中 tool_call index 字段错误的 ChatOpenAI 包装类

问题背景：
某些 API 网关在返回流式 tool_call 时，所有 chunks 的 index 都是 0，
导致 langchain_core 把多个工具调用错误地合并成一个。

解决方案：
在 _astream 阶段拦截 tool_call_chunks，根据 id 字段自动修正 index。
"""

from typing import Any, AsyncIterator, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk

from backend.app.core.logger import logger


class PatchedChatOpenAI(ChatOpenAI):
    """修复 tool_call index 的 ChatOpenAI 子类
    
    自动检测并修正流式响应中 tool_call_chunks 的 index 字段，
    确保不同工具调用有不同的 index。
    """
    
    async def _astream(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        """重写流式生成方法，修正 tool_call_chunks 的 index"""
        
        # 跟踪已见过的 tool_call id -> 分配的 index
        id_to_index: dict[str, int] = {}
        next_index = 0
        
        async for chunk in super()._astream(*args, **kwargs):
            # 检查是否有 tool_call_chunks 需要修正
            if hasattr(chunk, 'message') and isinstance(chunk.message, AIMessageChunk):
                message = chunk.message
                
                if hasattr(message, 'tool_call_chunks') and message.tool_call_chunks:
                    # 修正每个 tool_call_chunk 的 index
                    patched_chunks = []
                    for tc_chunk in message.tool_call_chunks:
                        tc_id = tc_chunk.get('id')
                        original_index = tc_chunk.get('index')
                        
                        if tc_id is not None:
                            # 新的工具调用（有 id）
                            if tc_id not in id_to_index:
                                # 首次见到这个 id，分配新 index
                                id_to_index[tc_id] = next_index
                                next_index += 1
                            
                            new_index = id_to_index[tc_id]
                        else:
                            # 续传的参数（没有 id），使用最后一个已知的 index
                            # 这种情况下，应该沿用上一个 chunk 的 index
                            # 通常是当前最大的 index - 1（最近添加的那个）
                            new_index = max(id_to_index.values()) if id_to_index else 0
                        
                        if new_index != original_index:
                            # 需要修正
                            patched_chunk = dict(tc_chunk)
                            patched_chunk['index'] = new_index
                            patched_chunks.append(patched_chunk)
                            
                            if tc_id:
                                logger.debug(
                                    f"[PatchedChatOpenAI] 修正 tool_call index: "
                                    f"id={tc_id[:20]}..., {original_index} -> {new_index}"
                                )
                        else:
                            patched_chunks.append(tc_chunk)
                    
                    # 如果有修正，创建新的 message 和 chunk
                    if patched_chunks != list(message.tool_call_chunks):
                        # 创建新的 AIMessageChunk
                        new_message = AIMessageChunk(
                            content=message.content,
                            additional_kwargs=message.additional_kwargs,
                            response_metadata=getattr(message, 'response_metadata', {}),
                            tool_call_chunks=patched_chunks,
                            id=message.id,
                        )
                        
                        # 创建新的 ChatGenerationChunk
                        chunk = ChatGenerationChunk(
                            message=new_message,
                            generation_info=chunk.generation_info,
                        )
            
            yield chunk

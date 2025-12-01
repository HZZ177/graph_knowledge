"""Chat 服务模块

包含：
- chat_service: 流式对话主逻辑
- history_service: 会话历史管理
"""

from backend.app.services.chat.chat_service import (
    streaming_chat,
    streaming_regenerate,
)
from backend.app.services.chat.history_service import (
    get_conversation_history,
    clear_conversation,
    truncate_conversation,
    generate_conversation_title,
    get_raw_messages,
    replace_assistant_response,
    save_error_to_history,
)

__all__ = [
    "streaming_chat",
    "streaming_regenerate",
    "get_conversation_history",
    "clear_conversation",
    "truncate_conversation",
    "generate_conversation_title",
    "get_raw_messages",
    "replace_assistant_response",
    "save_error_to_history",
]

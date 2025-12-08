"""Chat 服务模块

包含：
- chat_service: 流式对话主逻辑
- history_service: 会话历史管理
- multimodal: 多模态消息构造
- document_parser: 文档解析
- storage: 文件存储服务
- models: 数据模型 (Conversation, FileUpload)
- schemas: Pydantic Schema 定义
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
from backend.app.services.chat.storage import (
    init_storage_service,
    get_storage_service,
    FileStorageService,
    StorageConfig,
)
from backend.app.models.chat import (
    Conversation,
    FileUpload,
)

__all__ = [
    # 核心服务
    "streaming_chat",
    "streaming_regenerate",
    # 历史管理
    "get_conversation_history",
    "clear_conversation",
    "truncate_conversation",
    "generate_conversation_title",
    "get_raw_messages",
    "replace_assistant_response",
    "save_error_to_history",
    # 文件存储
    "init_storage_service",
    "get_storage_service",
    "FileStorageService",
    "StorageConfig",
    # 数据模型
    "Conversation",
    "FileUpload",
]

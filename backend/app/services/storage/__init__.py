"""文件存储模块

重新组织后的存储服务，位于 chat 模块下。
"""

from .service import FileStorageService, init_storage_service, get_storage_service
from .config import StorageConfig

__all__ = [
    "FileStorageService",
    "init_storage_service",
    "get_storage_service",
    "StorageConfig",
]

"""文件存储模块"""

from .service import FileStorageService, init_storage_service, get_storage_service
from .config import StorageConfig

__all__ = [
    "FileStorageService",
    "init_storage_service",
    "get_storage_service",
    "StorageConfig",
]

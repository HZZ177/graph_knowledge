"""文件存储服务"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from loguru import logger

from .config import StorageConfig
from .providers import IStorageProvider, AliyunOSSProvider, S3Provider, QiniuProvider, MinIOProvider


class FileStorageService:
    """文件存储服务（单例）"""
    
    def __init__(self, config: StorageConfig):
        self.config = config
        self.provider = self._init_provider()
    
    def _init_provider(self) -> IStorageProvider:
        """根据配置初始化 Provider"""
        provider_name = self.config.provider_name
        provider_config = self.config.provider_config
        
        provider_map = {
            "aliyun_oss": AliyunOSSProvider,
            "s3": S3Provider,
            "qiniu": QiniuProvider,
            "minio": MinIOProvider,
        }
        
        provider_class = provider_map.get(provider_name)
        if not provider_class:
            raise ValueError(f"不支持的存储提供商: {provider_name}")
        
        logger.info(f"[FileStorage] 使用存储提供商: {provider_name}")
        return provider_class(provider_config)
    
    def validate_file(self, filename: str, file_size: int) -> None:
        """验证文件"""
        # 验证文件大小
        if file_size > self.config.max_file_size:
            max_mb = self.config.max_file_size / (1024 * 1024)
            raise ValueError(f"文件大小超过限制 ({max_mb:.1f}MB)")
        
        # 验证文件扩展名
        ext = Path(filename).suffix.lstrip('.').lower()
        if ext not in self.config.allowed_extensions:
            raise ValueError(f"不支持的文件类型: .{ext}")
    
    def generate_file_key(self, filename: str) -> str:
        """生成文件存储 Key
        
        格式: {date}/{uuid}/{filename}
        例如: 2024-12-07/a1b2c3d4.../screenshot.png
        """
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_uuid = uuid.uuid4().hex[:12]
        
        # 保留原始文件名（防止重名冲突）
        safe_filename = Path(filename).name
        
        return f"{date_str}/{file_uuid}/{safe_filename}"
    
    async def upload_file(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str
    ) -> tuple[str, str]:
        """上传文件
        
        Args:
            file_bytes: 文件字节内容
            filename: 原始文件名
            content_type: MIME 类型
        
        Returns:
            (file_key, url) - 文件 Key 和永久访问 URL
        """
        # 验证文件
        self.validate_file(filename, len(file_bytes))
        
        # 生成 file_key
        file_key = self.generate_file_key(filename)
        
        # 上传到 OSS
        url = await self.provider.upload(file_bytes, file_key, content_type)
        
        logger.info(f"[FileStorage] 文件上传成功: {filename} -> {file_key}")
        return file_key, url
    
    async def delete_file(self, file_key: str) -> bool:
        """删除文件"""
        return await self.provider.delete(file_key)


# 全局单例
_storage_service: Optional[FileStorageService] = None


def init_storage_service(config_path) -> FileStorageService:
    """初始化文件存储服务（单例）"""
    global _storage_service
    
    if _storage_service is None:
        config = StorageConfig(config_path)
        _storage_service = FileStorageService(config)
        logger.info("[FileStorage] 文件存储服务初始化完成")
    
    return _storage_service


def get_storage_service() -> FileStorageService:
    """获取文件存储服务实例"""
    if _storage_service is None:
        raise RuntimeError("文件存储服务未初始化，请先调用 init_storage_service()")
    
    return _storage_service

"""文件存储提供商实现（所有 OSS 实现集中在此文件）"""

from abc import ABC, abstractmethod
from typing import Optional
from loguru import logger


# ========== 抽象接口 ==========

class IStorageProvider(ABC):
    """存储提供商抽象接口"""
    
    @abstractmethod
    async def upload(self, file_bytes: bytes, file_key: str, content_type: str) -> str:
        """上传文件，返回永久访问 URL"""
        pass
    
    @abstractmethod
    async def delete(self, file_key: str) -> bool:
        """删除文件"""
        pass


# ========== 阿里云 OSS ==========

class AliyunOSSProvider(IStorageProvider):
    """阿里云 OSS 实现"""
    
    def __init__(self, config: dict):
        try:
            import oss2
        except ImportError:
            raise ImportError("请安装 oss2: pip install oss2")
        
        self.bucket_name = config['bucket']
        self.endpoint = config['endpoint']
        
        auth = oss2.Auth(config['access_key'], config['secret_key'])
        self.bucket = oss2.Bucket(auth, self.endpoint, self.bucket_name)
        
        logger.info(f"[AliyunOSS] 初始化成功: bucket={self.bucket_name}, endpoint={self.endpoint}")
    
    async def upload(self, file_bytes: bytes, file_key: str, content_type: str) -> str:
        """上传文件到阿里云 OSS"""
        self.bucket.put_object(file_key, file_bytes, headers={'Content-Type': content_type})
        
        # 返回永久访问 URL（假设 bucket 已设置公开读）
        url = f"{self.endpoint}/{self.bucket_name}/{file_key}"
        logger.info(f"[AliyunOSS] 文件上传成功: {file_key}")
        return url
    
    async def delete(self, file_key: str) -> bool:
        """删除文件"""
        try:
            self.bucket.delete_object(file_key)
            logger.info(f"[AliyunOSS] 文件删除成功: {file_key}")
            return True
        except Exception as e:
            logger.error(f"[AliyunOSS] 文件删除失败: {e}")
            return False


# ========== AWS S3 ==========

class S3Provider(IStorageProvider):
    """AWS S3 实现"""
    
    def __init__(self, config: dict):
        try:
            import boto3
        except ImportError:
            raise ImportError("请安装 boto3: pip install boto3")
        
        self.bucket_name = config['bucket']
        self.region = config['region']
        
        self.client = boto3.client(
            's3',
            region_name=self.region,
            aws_access_key_id=config['access_key'],
            aws_secret_access_key=config['secret_key'],
            endpoint_url=config.get('endpoint')
        )
        
        logger.info(f"[S3] 初始化成功: bucket={self.bucket_name}, region={self.region}")
    
    async def upload(self, file_bytes: bytes, file_key: str, content_type: str) -> str:
        """上传文件到 S3"""
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=file_key,
            Body=file_bytes,
            ContentType=content_type,
            ACL='public-read'  # 公开读，返回永久 URL
        )
        
        # 返回永久访问 URL
        url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{file_key}"
        logger.info(f"[S3] 文件上传成功: {file_key}")
        return url
    
    async def delete(self, file_key: str) -> bool:
        """删除文件"""
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=file_key)
            logger.info(f"[S3] 文件删除成功: {file_key}")
            return True
        except Exception as e:
            logger.error(f"[S3] 文件删除失败: {e}")
            return False


# ========== 七牛云 ==========

class QiniuProvider(IStorageProvider):
    """七牛云实现"""
    
    def __init__(self, config: dict):
        try:
            from qiniu import Auth, put_data
        except ImportError:
            raise ImportError("请安装 qiniu: pip install qiniu")
        
        self.bucket_name = config['bucket']
        self.domain = config['domain']
        
        self.auth = Auth(config['access_key'], config['secret_key'])
        self.put_data = put_data
        
        logger.info(f"[Qiniu] 初始化成功: bucket={self.bucket_name}, domain={self.domain}")
    
    async def upload(self, file_bytes: bytes, file_key: str, content_type: str) -> str:
        """上传文件到七牛云"""
        token = self.auth.upload_token(self.bucket_name, file_key)
        ret, info = self.put_data(token, file_key, file_bytes)
        
        if info.status_code != 200:
            raise Exception(f"七牛云上传失败: {info}")
        
        # 返回永久访问 URL
        url = f"{self.domain}/{file_key}"
        logger.info(f"[Qiniu] 文件上传成功: {file_key}")
        return url
    
    async def delete(self, file_key: str) -> bool:
        """删除文件"""
        try:
            from qiniu import BucketManager
            
            bucket_manager = BucketManager(self.auth)
            ret, info = bucket_manager.delete(self.bucket_name, file_key)
            logger.info(f"[Qiniu] 文件删除成功: {file_key}")
            return info.status_code == 200
        except Exception as e:
            logger.error(f"[Qiniu] 文件删除失败: {e}")
            return False


# ========== MinIO ==========

class MinIOProvider(IStorageProvider):
    """MinIO 实现（兼容 S3 API，本地开发推荐）"""
    
    def __init__(self, config: dict):
        try:
            from minio import Minio
        except ImportError:
            raise ImportError("请安装 minio: pip install minio")
        
        self.bucket_name = config['bucket']
        self.endpoint_url = config['endpoint']
        
        # MinIO endpoint 格式: localhost:9000
        endpoint = self.endpoint_url.replace('http://', '').replace('https://', '')
        
        self.client = Minio(
            endpoint,
            access_key=config['access_key'],
            secret_key=config['secret_key'],
            secure=config.get('secure', False)
        )
        
        # 确保 bucket 存在
        if not self.client.bucket_exists(self.bucket_name):
            self.client.make_bucket(self.bucket_name)
            logger.info(f"[MinIO] Bucket 创建成功: {self.bucket_name}")
        
        # 设置 bucket 为公开读（可选）
        try:
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{self.bucket_name}/*"]
                    }
                ]
            }
            import json
            self.client.set_bucket_policy(self.bucket_name, json.dumps(policy))
        except Exception as e:
            logger.warning(f"[MinIO] 设置公开读权限失败（可能已设置）: {e}")
        
        logger.info(f"[MinIO] 初始化成功: bucket={self.bucket_name}, endpoint={endpoint}")
    
    async def upload(self, file_bytes: bytes, file_key: str, content_type: str) -> str:
        """上传文件到 MinIO"""
        from io import BytesIO
        
        self.client.put_object(
            self.bucket_name,
            file_key,
            BytesIO(file_bytes),
            length=len(file_bytes),
            content_type=content_type
        )
        
        # 返回永久访问 URL
        url = f"{self.endpoint_url}/{self.bucket_name}/{file_key}"
        logger.info(f"[MinIO] 文件上传成功: {file_key}")
        return url
    
    async def delete(self, file_key: str) -> bool:
        """删除文件"""
        try:
            self.client.remove_object(self.bucket_name, file_key)
            logger.info(f"[MinIO] 文件删除成功: {file_key}")
            return True
        except Exception as e:
            logger.error(f"[MinIO] 文件删除失败: {e}")
            return False

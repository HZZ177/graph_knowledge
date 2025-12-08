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


# ========== OpenList REST API ==========

class OpenListS3Provider(IStorageProvider):
    """OpenList REST API 实现
    
    使用 OpenList 的 REST API（而非 S3 接口）上传文件，兼容性更好。
    API:
    - PUT /api/fs/put - 上传文件
    - POST /api/fs/get - 获取文件信息
    - POST /api/fs/remove - 删除文件
    """
    
    def __init__(self, config: dict):
        import httpx
        
        self.base_url = config['endpoint'].rstrip('/')  # OpenList 主站地址
        self.upload_path = config.get('upload_path', '/chat-files')  # 上传目录
        self.token = config.get('token', '')  # API Token
        self.username = config.get('username', '')
        self.password = config.get('password', '')
        
        logger.info(f"[OpenListAPI] 初始化: base_url={self.base_url}, username={self.username}, has_token={bool(self.token)}")
        
        # 创建 HTTP 客户端
        self.client = httpx.Client(timeout=60.0, verify=False)
        
        # 如果没有 token 但有用户名密码，则登录获取 token
        if not self.token and self.username and self.password:
            logger.info(f"[OpenListAPI] 开始登录...")
            self._login()
        elif not self.token:
            logger.warning(f"[OpenListAPI] 未配置 token 或用户名密码，可能无法上传文件")
        
        logger.info(f"[OpenListAPI] 初始化完成: has_token={bool(self.token)}")
    
    def _login(self):
        """登录获取 token"""
        try:
            logger.debug(f"[OpenListAPI] 登录请求: {self.base_url}/api/auth/login")
            resp = self.client.post(
                f"{self.base_url}/api/auth/login",
                json={"username": self.username, "password": self.password},
                headers={"Content-Type": "application/json"}
            )
            logger.debug(f"[OpenListAPI] 登录响应状态: {resp.status_code}")
            data = resp.json()
            logger.debug(f"[OpenListAPI] 登录响应: code={data.get('code')}, message={data.get('message')}")
            
            if data.get('code') == 200:
                token = data['data']['token']
                # 确保 token 是完整格式
                self.token = token
                logger.info(f"[OpenListAPI] 登录成功，token长度: {len(self.token)}")
            else:
                logger.error(f"[OpenListAPI] 登录失败: {data}")
                raise RuntimeError(f"OpenList 登录失败: {data.get('message')}")
        except Exception as e:
            logger.error(f"[OpenListAPI] 登录异常: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"[OpenListAPI] 登录堆栈:\n{traceback.format_exc()}")
            raise
    
    def _get_headers(self):
        """获取请求头"""
        headers = {}
        if self.token:
            # OpenList 使用 Bearer token 格式
            headers['Authorization'] = self.token if self.token.startswith('Bearer ') else self.token
        return headers
    
    def _is_token_expired(self, data: dict) -> bool:
        """检测响应是否表示 token 过期"""
        # OpenList token 过期的可能错误码/消息
        code = data.get('code')
        message = str(data.get('message', '')).lower()
        
        # 常见的 token 过期标识
        if code in [401, 403]:
            return True
        if 'token' in message and ('expired' in message or 'invalid' in message or '过期' in message or '无效' in message):
            return True
        if 'login' in message or '登录' in message:
            return True
        
        return False
    
    def _refresh_token(self):
        """刷新 token（重新登录）"""
        if self.username and self.password:
            logger.info(f"[OpenListAPI] Token 过期，尝试重新登录...")
            self._login()
            logger.info(f"[OpenListAPI] Token 刷新成功")
        else:
            raise RuntimeError("Token 过期且无法刷新（未配置用户名密码）")
    
    async def upload(self, file_bytes: bytes, file_key: str, content_type: str) -> str:
        """上传文件到 OpenList（支持 token 过期自动刷新）"""
        import asyncio
        from urllib.parse import quote
        
        # 完整路径
        full_path = f"{self.upload_path}/{file_key}"
        
        # 最多重试一次（token 过期时刷新后重试）
        for attempt in range(2):
            try:
                # OpenList PUT /api/fs/put 接口
                # 需要在 URL 参数或 Header 中指定路径
                headers = self._get_headers()
                headers['Content-Type'] = 'application/octet-stream'
                headers['File-Path'] = quote(full_path, safe='/')
                
                # 使用同步请求（在异步上下文中）
                resp = await asyncio.to_thread(
                    self.client.put,
                    f"{self.base_url}/api/fs/put",
                    content=file_bytes,
                    headers=headers
                )
                
                data = resp.json()
                
                # 检查是否 token 过期
                if data.get('code') != 200:
                    if attempt == 0 and self._is_token_expired(data):
                        self._refresh_token()
                        continue  # 重试
                    raise RuntimeError(f"上传失败: {data.get('message')}")
                
                # 构造下载 URL（OpenList 的公开下载链接格式）
                encoded_path = quote(full_path, safe='/')
                url = f"{self.base_url}/d{encoded_path}"
                
                logger.debug(f"[OpenListAPI] 上传成功: {full_path}")
                return url
                
            except RuntimeError:
                raise
            except Exception as e:
                logger.error(f"[OpenListAPI] 上传失败: {type(e).__name__}: {e}")
                raise
        
        raise RuntimeError("上传失败：重试次数超限")
    
    async def delete(self, file_key: str) -> bool:
        """删除文件（支持 token 过期自动刷新）"""
        import asyncio
        
        full_path = f"{self.upload_path}/{file_key}"
        
        # 最多重试一次（token 过期时刷新后重试）
        for attempt in range(2):
            try:
                headers = self._get_headers()
                headers['Content-Type'] = 'application/json'
                
                resp = await asyncio.to_thread(
                    self.client.post,
                    f"{self.base_url}/api/fs/remove",
                    json={"names": [full_path.split('/')[-1]], "dir": '/'.join(full_path.split('/')[:-1])},
                    headers=headers
                )
                
                data = resp.json()
                
                # 检查是否 token 过期
                if data.get('code') != 200:
                    if attempt == 0 and self._is_token_expired(data):
                        self._refresh_token()
                        continue  # 重试
                    logger.warning(f"[OpenListAPI] OSS删除失败: {data.get('message')}")
                    return False
                
                logger.debug(f"[OpenListAPI] OSS删除成功: {full_path}")
                return True
                
            except Exception as e:
                logger.error(f"[OpenListAPI] 文件删除失败: {e}")
                return False
        
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

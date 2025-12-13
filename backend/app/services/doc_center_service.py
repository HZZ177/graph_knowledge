"""
文档中心服务

提供以下功能：
1. 从帮助中心数据库获取目录树结构
2. 同步文档（获取内容、处理图片、保存本地）
3. 文档状态管理

配置暂时硬编码，参考 test/file_process/doc_image_processor.py
"""

import os
import re
import hashlib
import mimetypes
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse, unquote, quote
from uuid import uuid4

import httpx
import pymysql

from sqlalchemy.orm import Session

from backend.app.core.logger import logger
from backend.app.models.doc_center import DocCenterDocument, DocCenterFolder


# ============== 硬编码配置（参考 doc_image_processor.py）==============

# 帮助中心数据库配置
HELP_CENTER_DB_CONFIG = {
    "host": "122.112.252.51",
    "port": 3386,
    "user": "cdai",
    "password": "stC#pso76v15mk",
    "database": "ktops_help_center",
    "charset": "utf8mb4",
}

# 帮助中心 API 配置
HELP_API_BASE = "https://yunwei-help.keytop.cn/helpApi"
HELP_API_TOKEN = "5iw61f16wtjh2p46ue38h19tloo5pftw9fupsd7omeyd6b9uj1jyv4pv6po5ohyx2ciidgrcnx605zqryljg6ifw3j03ph9dnx03wm8pej1mj144lmcekmy810od185r26xvjzkgxl4zkhfr"

# OSS 配置（OpenList）
OSS_CONFIG = {
    "endpoint": "https://openlist.heshouyi.com",
    "upload_path": "/hsy/OSS/doc-images",
    "username": "admin",
    "password": "19981208@qwer",
}

# 本地文档存储目录
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DOCS_OUTPUT_DIR = _PROJECT_ROOT / "docs"

# 默认 projectId
DEFAULT_PROJECT_ID = 55


# ============== OSS 客户端（复用 doc_image_processor 逻辑）==============

class SimpleOSSClient:
    """简化的 OSS 客户端（基于 OpenList REST API）- 异步实现"""

    def __init__(self, config: dict):
        self.base_url = config["endpoint"].rstrip("/")
        self.upload_path = config["upload_path"]
        self.username = config["username"]
        self.password = config["password"]
        self.token = None
        self.client = httpx.AsyncClient(timeout=60.0, verify=False)

    async def _login(self):
        """登录获取 token"""
        logger.debug("[OSS] 登录 OpenList...")
        resp = await self.client.post(
            f"{self.base_url}/api/auth/login",
            json={"username": self.username, "password": self.password},
            headers={"Content-Type": "application/json"}
        )
        data = resp.json()
        if data.get("code") == 200:
            self.token = data["data"]["token"]
            logger.debug("[OSS] 登录成功")
        else:
            raise RuntimeError(f"OSS 登录失败: {data.get('message')}")

    async def ensure_login(self):
        """确保已登录"""
        if not self.token:
            await self._login()

    async def upload(self, file_bytes: bytes, filename: str, content_type: str) -> str:
        """上传文件，返回永久 URL"""
        import uuid

        await self.ensure_login()

        # 生成文件路径: /upload_path/2024-12-12/uuid/filename
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_uuid = uuid.uuid4().hex[:12]
        full_path = f"{self.upload_path}/{date_str}/{file_uuid}/{filename}"

        headers = {
            "Authorization": self.token,
            "Content-Type": "application/octet-stream",
            "File-Path": quote(full_path, safe="/"),
        }

        resp = await self.client.put(
            f"{self.base_url}/api/fs/put",
            content=file_bytes,
            headers=headers,
        )
        data = resp.json()

        if data.get("code") != 200:
            raise RuntimeError(f"上传失败: {data.get('message')}")

        # 返回下载 URL
        encoded_path = quote(full_path, safe="/")
        return f"{self.base_url}/d{encoded_path}"

    async def close(self):
        """关闭客户端"""
        if self.client:
            await self.client.aclose()


# ============== 帮助中心 API 客户端 ==============

class HelpCenterAPIClient:
    """帮助中心 API 客户端 - 异步实现"""

    def __init__(self, base_url: str = HELP_API_BASE, token: str = HELP_API_TOKEN):
        self.base_url = base_url
        self.token = token
        self.client = httpx.AsyncClient(timeout=30.0, verify=False)

    async def get_share_url(self, doc_id: str) -> Optional[str]:
        """获取文档分享码"""
        resp = await self.client.post(
            f"{self.base_url}/HelpDoc/getShareShowUrl",
            json={"docId": doc_id},
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}" if self.token else "",
                "token": self.token,
            }
        )
        data = resp.json()
        if data.get("resCode") == 0:
            return data["data"]["showUrl"]
        else:
            logger.warning(f"[HelpAPI] 获取分享码失败: {data.get('resMsg')}")
            return None

    async def get_doc_content(self, share_url: str) -> Optional[dict]:
        """通过分享码获取文档内容"""
        resp = await self.client.post(
            f"{self.base_url}/HelpDoc/getShareDocInfo",
            json={"shareUrl": share_url},
            headers={"Content-Type": "application/json"}
        )
        data = resp.json()
        if data.get("resCode") == 0:
            return {
                "md": data["data"].get("md", ""),
                "text": data["data"].get("text", ""),
            }
        else:
            logger.warning(f"[HelpAPI] 获取文档内容失败: {data.get('resMsg')}")
            return None

    async def close(self):
        """关闭客户端"""
        if self.client:
            await self.client.aclose()


# ============== 图片处理函数（复用 doc_image_processor 逻辑）==============

def extract_image_urls(content: str) -> List[str]:
    """从 Markdown 内容中提取图片 URL"""
    pattern = r'!\[[^\]]*\]\(([^)]+)\)'
    urls = re.findall(pattern, content)

    # 过滤掉非 http 链接和已经是我们 OSS 的链接
    filtered = []
    for url in urls:
        if url.startswith(("http://", "https://")):
            if "openlist.heshouyi.com" not in url:
                filtered.append(url)

    return list(set(filtered))


def get_filename_from_url(url: str) -> str:
    """从 URL 提取文件名"""
    parsed = urlparse(url)
    path = unquote(parsed.path)
    filename = Path(path).name

    if not filename or "." not in filename:
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        filename = f"{url_hash}.png"

    return filename


def get_content_type(filename: str) -> str:
    """根据文件名获取 MIME 类型"""
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or "image/png"


async def download_image(url: str, client: httpx.AsyncClient) -> Optional[bytes]:
    """下载图片"""
    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code == 200:
            return resp.content
        else:
            logger.warning(f"[下载] 失败 ({resp.status_code}): {url[:80]}...")
            return None
    except Exception as e:
        logger.warning(f"[下载] 异常: {e}")
        return None


def sanitize_filename(name: str) -> str:
    """清理文件名，移除非法字符"""
    illegal_chars = r'[<>:"/\\|?*]'
    name = re.sub(illegal_chars, '_', name)
    if len(name) > 100:
        name = name[:100]
    return name.strip() or "untitled"


# ============== 文档中心服务类 ==============

class DocCenterService:
    """文档中心服务 - 前端只与本地数据库交互"""

    # ============== 同步功能：从帮助中心拉取到本地 ==============

    @staticmethod
    def sync_structure_from_help_center(
        db: Session,
        project_id: int = DEFAULT_PROJECT_ID
    ) -> Dict[str, Any]:
        """
        从帮助中心同步目录结构和文档列表到本地数据库
        
        Returns:
            {folders_synced: int, documents_synced: int}
        """
        logger.info(f"[DocCenter] 开始同步结构, projectId={project_id}")

        conn = pymysql.connect(**HELP_CENTER_DB_CONFIG)
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 获取所有菜单项
                sql = """
                    SELECT 
                        menuId as id,
                        text as title,
                        parentId as parent_id,
                        menuType as menu_type,
                        sort as sort_order
                    FROM help_doc_menu
                    WHERE projectId = %s
                    ORDER BY sort ASC
                """
                cursor.execute(sql, (project_id,))
                rows = cursor.fetchall()

            folders_synced = 0
            documents_synced = 0

            for row in rows:
                menu_id = str(row["id"])
                title = row["title"] or ""
                parent_id = str(row["parent_id"]) if row["parent_id"] else "0"
                is_folder = row["menu_type"] == 1  # 0=文章, 1=文件夹
                sort_order = int(row["sort_order"] or 0)

                if is_folder:
                    # 同步目录
                    existing = db.query(DocCenterFolder).filter(
                        DocCenterFolder.source_menu_id == menu_id
                    ).first()

                    if existing:
                        existing.title = title
                        existing.source_parent_id = parent_id
                        existing.sort_order = sort_order
                    else:
                        folder = DocCenterFolder(
                            source_menu_id=menu_id,
                            source_parent_id=parent_id,
                            source_project_id=project_id,
                            title=title,
                            sort_order=sort_order,
                        )
                        db.add(folder)
                    folders_synced += 1
                else:
                    # 同步文档（只同步结构，不下载内容）
                    existing = db.query(DocCenterDocument).filter(
                        DocCenterDocument.source_doc_id == menu_id
                    ).first()

                    if existing:
                        existing.title = title
                        existing.source_parent_id = parent_id
                    else:
                        doc = DocCenterDocument(
                            source_doc_id=menu_id,
                            source_parent_id=parent_id,
                            source_project_id=project_id,
                            title=title,
                            sync_status="pending",  # 内容待同步
                        )
                        db.add(doc)
                    documents_synced += 1

            db.commit()
            logger.info(f"[DocCenter] 结构同步完成: {folders_synced} 目录, {documents_synced} 文档")

            return {
                "folders_synced": folders_synced,
                "documents_synced": documents_synced,
            }

        finally:
            conn.close()

    # ============== 本地数据读取 ==============

    @staticmethod
    def get_directory_tree(db: Session) -> List[Dict[str, Any]]:
        """
        从本地数据库获取目录树结构
        
        Returns:
            树形结构列表
        """
        # 获取所有目录
        folders = db.query(DocCenterFolder).order_by(DocCenterFolder.sort_order).all()
        # 获取所有文档
        documents = db.query(DocCenterDocument).all()

        nodes_map = {}
        root_nodes = []

        # 添加目录节点
        for folder in folders:
            node = {
                "id": folder.source_menu_id,
                "title": folder.title,
                "parent_id": folder.source_parent_id,
                "is_folder": True,
                "children": [],
            }
            nodes_map[node["id"]] = node

        # 添加文档节点
        for doc in documents:
            node = {
                "id": doc.source_doc_id,
                "local_id": doc.id,
                "title": doc.title,
                "parent_id": doc.source_parent_id,
                "is_folder": False,
                "sync_status": doc.sync_status,
                "index_status": doc.index_status,
                "children": [],
            }
            nodes_map[node["id"]] = node

        # 建立父子关系
        for node_id, node in nodes_map.items():
            parent_id = node["parent_id"]
            if parent_id and parent_id != "0" and parent_id in nodes_map:
                nodes_map[parent_id]["children"].append(node)
            else:
                root_nodes.append(node)

        return root_nodes

    @staticmethod
    def get_documents(
        db: Session,
        parent_id: Optional[str] = None,
        sync_status: Optional[str] = None,
        index_status: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        从本地数据库获取文档列表
        """
        query = db.query(DocCenterDocument)

        if parent_id:
            query = query.filter(DocCenterDocument.source_parent_id == parent_id)
        if sync_status:
            # 支持逗号分隔的多状态筛选
            statuses = [s.strip() for s in sync_status.split(',') if s.strip()]
            if len(statuses) == 1:
                query = query.filter(DocCenterDocument.sync_status == statuses[0])
            elif len(statuses) > 1:
                query = query.filter(DocCenterDocument.sync_status.in_(statuses))
        if index_status:
            # 支持逗号分隔的多状态筛选
            statuses = [s.strip() for s in index_status.split(',') if s.strip()]
            if len(statuses) == 1:
                query = query.filter(DocCenterDocument.index_status == statuses[0])
            elif len(statuses) > 1:
                query = query.filter(DocCenterDocument.index_status.in_(statuses))
        if keyword:
            query = query.filter(DocCenterDocument.title.ilike(f"%{keyword}%"))

        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()

        return {
            "items": [
                {
                    "id": doc.id,
                    "source_doc_id": doc.source_doc_id,
                    "title": doc.title,
                    "parent_id": doc.source_parent_id,
                    "sync_status": doc.sync_status,
                    "synced_at": doc.synced_at.isoformat() if doc.synced_at else None,
                    "index_status": doc.index_status,
                    "extraction_progress": doc.extraction_progress,
                    "entities_total": doc.entities_total,
                    "entities_done": doc.entities_done,
                    "relations_total": doc.relations_total,
                    "relations_done": doc.relations_done,
                }
                for doc in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    def get_document_by_id(db: Session, doc_id: str) -> Optional[DocCenterDocument]:
        """根据ID获取文档"""
        return db.query(DocCenterDocument).filter(DocCenterDocument.id == doc_id).first()

    @staticmethod
    def get_document_by_source_id(db: Session, source_doc_id: str) -> Optional[DocCenterDocument]:
        """根据来源ID获取文档"""
        return db.query(DocCenterDocument).filter(
            DocCenterDocument.source_doc_id == source_doc_id
        ).first()

    @staticmethod
    async def sync_document(
        db: Session,
        source_doc_id: str,
        title: str,
        parent_id: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        同步单个文档

        流程：
        1. 获取分享URL
        2. 获取文档内容
        3. 处理图片（下载→上传OSS→替换链接）
        4. 保存到本地
        5. 更新数据库记录

        Args:
            progress_callback: 进度回调函数，签名: async def callback(phase, current, total, detail)

        Returns:
            {success: bool, document: {...}, error: str}
        """
        async def report_progress(phase: str, current: int, total: int, detail: str = ""):
            if progress_callback:
                await progress_callback(phase, current, total, detail)
        logger.info(f"[DocCenter] 开始同步文档: {source_doc_id} - {title}")

        # 检查是否已存在
        existing = DocCenterService.get_document_by_source_id(db, source_doc_id)
        if existing:
            doc = existing
            doc.sync_status = "syncing"
            doc.sync_error = None
            db.commit()
        else:
            # 创建新记录
            doc = DocCenterDocument(
                id=uuid4().hex,
                source_doc_id=source_doc_id,
                source_parent_id=parent_id,
                title=title,
                sync_status="syncing",
            )
            db.add(doc)
            db.commit()

        try:
            # 1. 获取分享URL
            help_client = HelpCenterAPIClient()
            share_url = await help_client.get_share_url(source_doc_id)
            if not share_url:
                raise Exception("获取分享码失败")

            # 保存云端地址（拼接成完整的帮助中心分享链接）
            doc.source_url = f"https://yunwei-help.keytop.cn/helpCenter/shareDoc/{share_url}"

            # 2. 获取文档内容
            doc_data = await help_client.get_doc_content(share_url)
            if not doc_data or not doc_data.get("md"):
                raise Exception("获取文档内容失败")

            content = doc_data["md"]
            logger.info(f"[DocCenter] 获取内容成功, 长度={len(content)}")

            # 3. 处理图片
            image_urls = extract_image_urls(content)
            if image_urls:
                logger.info(f"[DocCenter] 发现 {len(image_urls)} 张图片，开始处理...")
                await report_progress("image_processing", 0, len(image_urls), "开始处理图片")
                oss_client = SimpleOSSClient(OSS_CONFIG)

                async with httpx.AsyncClient(timeout=30.0, verify=False) as http_client:
                    url_mapping = {}
                    for i, url in enumerate(image_urls, 1):
                        logger.debug(f"[DocCenter] [{i}/{len(image_urls)}] 处理图片: {url[:60]}...")
                        await report_progress("image_processing", i, len(image_urls), f"处理图片 {i}/{len(image_urls)}")

                        # 下载
                        image_bytes = await download_image(url, http_client)
                        if not image_bytes:
                            continue

                        # 上传到 OSS
                        try:
                            filename = get_filename_from_url(url)
                            content_type = get_content_type(filename)
                            new_url = await oss_client.upload(image_bytes, filename, content_type)
                            url_mapping[url] = new_url
                            logger.debug(f"[DocCenter] 图片上传成功: {new_url[:60]}...")
                        except Exception as e:
                            logger.warning(f"[DocCenter] 图片上传失败: {e}")

                await oss_client.close()

                # 替换 URL
                for old_url, new_url in url_mapping.items():
                    content = content.replace(old_url, new_url)

                doc.image_count = len(url_mapping)
                logger.info(f"[DocCenter] 图片处理完成: {len(url_mapping)}/{len(image_urls)}")

            # 4. 保存到数据库
            doc.content = content
            doc.content_hash = hashlib.md5(content.encode()).hexdigest()
            doc.sync_status = "synced"
            doc.synced_at = datetime.utcnow()
            doc.sync_error = None
            db.commit()
            logger.info(f"[DocCenter] 文档内容已保存到数据库, 长度={len(content)}")

            await help_client.close()

            return {
                "success": True,
                "document": {
                    "id": doc.id,
                    "source_doc_id": doc.source_doc_id,
                    "title": doc.title,
                    "sync_status": doc.sync_status,
                    "image_count": doc.image_count,
                },
                "error": None,
            }

        except Exception as e:
            logger.error(f"[DocCenter] 同步失败: {e}")
            doc.sync_status = "failed"
            doc.sync_error = str(e)
            db.commit()

            return {
                "success": False,
                "document": {
                    "id": doc.id,
                    "source_doc_id": doc.source_doc_id,
                    "title": doc.title,
                    "sync_status": doc.sync_status,
                },
                "error": str(e),
            }

    @staticmethod
    def get_document_content(db: Session, doc_id: str) -> Optional[str]:
        """获取文档内容（从数据库）"""
        doc = DocCenterService.get_document_by_id(db, doc_id)
        if not doc or not doc.content:
            return None
        return doc.content

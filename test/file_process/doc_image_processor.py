"""
文档图片持久化处理脚本

功能：
1. 从数据库获取文档 ID 列表
2. 通过接口获取文档最新内容（包含有效图片链接）
3. 下载图片并上传到自有 OSS
4. 用永久链接替换临时链接
5. 保存处理后的 Markdown 文件到 docs 目录

使用方法：
    python test/file_process/doc_image_processor.py

注意：
    - 这是测试脚本，所有配置硬编码
    - 需要填入有效的 API Token
"""

import os
import re
import sys
import asyncio
import hashlib
import mimetypes
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, unquote

import httpx
import pymysql

# ============== 项目路径设置 ==============
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ============== 硬编码配置 ==============

# 数据库配置
DB_CONFIG = {
    "host": "122.112.252.51",
    "port": 3386,
    "user": "cdai",
    "password": "stC#pso76v15mk",
    "database": "ktops_help_center",  # 根据实际情况调整
    "charset": "utf8mb4",
}

# 帮助中心 API 配置
HELP_API_BASE = "https://yunwei-help.keytop.cn/helpApi"
HELP_API_TOKEN = "5iw61f16wtjh2p46ue38h19tloo5pftw9fupsd7omeyd6b9uj1jyv4pv6po5ohyx2ciidgrcnx605zqryljg6ifw3j03ph9dnx03wm8pej1mj144lmcekmy810od185r26xvjzkgxl4zkhfr"

# OSS 配置（OpenList）
OSS_CONFIG = {
    "endpoint": "https://openlist.heshouyi.com",
    "upload_path": "/hsy/OSS/doc-images",  # 文档图片专用目录
    "username": "admin",
    "password": "19981208@qwer",
}

# 输出目录
OUTPUT_DIR = PROJECT_ROOT / "docs"

# 处理限制
LIMIT = None  # 设置为数字限制处理数量，None 表示处理全部


# ============== OSS 客户端（简化版，直接复用 OpenList 逻辑） ==============

class SimpleOSSClient:
    """简化的 OSS 客户端（基于 OpenList REST API）"""
    
    def __init__(self, config: dict):
        self.base_url = config["endpoint"].rstrip("/")
        self.upload_path = config["upload_path"]
        self.username = config["username"]
        self.password = config["password"]
        self.token = None
        self.client = httpx.Client(timeout=60.0, verify=False)
        
        # 登录获取 token
        self._login()
    
    def _login(self):
        """登录获取 token"""
        print(f"[OSS] 登录 OpenList...")
        resp = self.client.post(
            f"{self.base_url}/api/auth/login",
            json={"username": self.username, "password": self.password},
            headers={"Content-Type": "application/json"}
        )
        data = resp.json()
        if data.get("code") == 200:
            self.token = data["data"]["token"]
            print(f"[OSS] 登录成功")
        else:
            raise RuntimeError(f"OSS 登录失败: {data.get('message')}")
    
    def upload(self, file_bytes: bytes, filename: str, content_type: str) -> str:
        """上传文件，返回永久 URL"""
        from urllib.parse import quote
        from datetime import datetime
        import uuid
        
        # 生成文件路径: /upload_path/2024-12-12/uuid/filename
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_uuid = uuid.uuid4().hex[:12]
        full_path = f"{self.upload_path}/{date_str}/{file_uuid}/{filename}"
        
        headers = {
            "Authorization": self.token,
            "Content-Type": "application/octet-stream",
            "File-Path": quote(full_path, safe="/"),
        }
        
        resp = self.client.put(
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


# ============== 帮助中心 API 客户端 ==============

class HelpCenterClient:
    """帮助中心 API 客户端"""
    
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.token = token
        self.client = httpx.Client(timeout=30.0, verify=False)
    
    def get_share_url(self, doc_id: str) -> Optional[str]:
        """获取文档分享码"""
        resp = self.client.post(
            f"{self.base_url}/HelpDoc/getShareShowUrl",
            json={"docId": doc_id},
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}" if self.token else "",
                "token": self.token,  # 兼容不同格式
            }
        )
        data = resp.json()
        if data.get("resCode") == 0:
            return data["data"]["showUrl"]
        else:
            print(f"[API] 获取分享码失败: {data.get('resMsg')}")
            return None
    
    def get_doc_content(self, share_url: str) -> Optional[dict]:
        """通过分享码获取文档内容"""
        resp = self.client.post(
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
            print(f"[API] 获取文档内容失败: {data.get('resMsg')}")
            return None


# ============== 图片处理逻辑 ==============

def extract_image_urls(content: str) -> list[str]:
    """从 Markdown 内容中提取图片 URL"""
    # 匹配 Markdown 图片语法: ![alt](url)
    pattern = r'!\[[^\]]*\]\(([^)]+)\)'
    urls = re.findall(pattern, content)
    
    # 过滤掉非 http 链接和已经是我们 OSS 的链接
    filtered = []
    for url in urls:
        if url.startswith(("http://", "https://")):
            # 排除已经是我们 OSS 的链接
            if "openlist.heshouyi.com" not in url:
                filtered.append(url)
    
    return list(set(filtered))  # 去重


def get_filename_from_url(url: str) -> str:
    """从 URL 提取文件名"""
    parsed = urlparse(url)
    path = unquote(parsed.path)
    filename = Path(path).name
    
    # 如果文件名为空或没有扩展名，生成一个
    if not filename or "." not in filename:
        # 用 URL hash 作为文件名
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
            print(f"[下载] 失败 ({resp.status_code}): {url[:80]}...")
            return None
    except Exception as e:
        print(f"[下载] 异常: {e}")
        return None


async def process_document_images(
    content: str,
    oss_client: SimpleOSSClient,
) -> str:
    """处理文档中的所有图片，返回替换后的内容"""
    
    # 提取图片 URL
    image_urls = extract_image_urls(content)
    if not image_urls:
        return content
    
    print(f"   发现 {len(image_urls)} 张图片")
    
    # 下载并上传图片
    url_mapping = {}
    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        for i, url in enumerate(image_urls, 1):
            print(f"   [{i}/{len(image_urls)}] 处理: {url[:60]}...")
            
            # 下载
            image_bytes = await download_image(url, client)
            if not image_bytes:
                continue
            
            # 上传到 OSS
            try:
                filename = get_filename_from_url(url)
                content_type = get_content_type(filename)
                new_url = oss_client.upload(image_bytes, filename, content_type)
                url_mapping[url] = new_url
                print(f"       ✓ 上传成功")
            except Exception as e:
                print(f"       ✗ 上传失败: {e}")
    
    # 替换 URL
    new_content = content
    for old_url, new_url in url_mapping.items():
        new_content = new_content.replace(old_url, new_url)
    
    print(f"   替换完成: {len(url_mapping)}/{len(image_urls)} 张图片")
    return new_content


# ============== 主流程 ==============

def get_doc_ids_from_db() -> list[tuple[str, str]]:
    """从数据库获取文档 ID 和名称列表
    
    Returns:
        list of (docId, text) tuples
    """
    print("[DB] 连接数据库...")
    
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT docId, text
                FROM help_doc_data_info hddi
                LEFT JOIN help_doc_menu hdm ON hddi.docId = hdm.menuId
                WHERE projectId = 55
            """
            if LIMIT:
                sql += f" LIMIT {LIMIT}"
            
            cursor.execute(sql)
            rows = cursor.fetchall()
            # 返回 (docId, text) 元组列表
            docs = [(str(row[0]), str(row[1]) if row[1] else "") for row in rows]
            print(f"[DB] 获取到 {len(docs)} 个文档")
            return docs
    finally:
        conn.close()


def get_existing_docs(output_dir: Path) -> set[str]:
    """获取已存在的文档名称集合（不含扩展名）"""
    if not output_dir.exists():
        return set()
    
    existing = set()
    for f in output_dir.glob("*.md"):
        # 去掉 .md 扩展名
        name = f.stem
        # 去掉可能的 _1, _2 后缀（重名文件）
        if name.endswith(tuple(f"_{i}" for i in range(1, 100))):
            name = "_".join(name.split("_")[:-1])
        existing.add(name)
    
    return existing


def sanitize_filename(name: str) -> str:
    """清理文件名，移除非法字符"""
    # 移除或替换 Windows 文件名非法字符
    illegal_chars = r'[<>:"/\\|?*]'
    name = re.sub(illegal_chars, '_', name)
    # 限制长度
    if len(name) > 100:
        name = name[:100]
    return name.strip() or "untitled"


async def process_single_doc(
    doc_id: str,
    help_client: HelpCenterClient,
    oss_client: SimpleOSSClient,
    output_dir: Path,
) -> bool:
    """处理单个文档"""
    print(f"\n{'='*50}")
    print(f"处理文档: {doc_id}")
    
    # 1. 获取分享码
    share_url = help_client.get_share_url(doc_id)
    if not share_url:
        print("   ✗ 获取分享码失败，跳过")
        return False
    
    # 2. 获取文档内容
    doc_data = help_client.get_doc_content(share_url)
    if not doc_data or not doc_data.get("md"):
        print("   ✗ 获取文档内容失败，跳过")
        return False
    
    content = doc_data["md"]
    title = doc_data.get("text") or doc_id
    print(f"   标题: {title}")
    print(f"   内容长度: {len(content)} 字符")
    
    # 3. 处理图片
    new_content = await process_document_images(content, oss_client)
    
    # 4. 保存文件
    safe_title = sanitize_filename(title)
    output_path = output_dir / f"{safe_title}.md"
    
    # 避免重名
    counter = 1
    while output_path.exists():
        output_path = output_dir / f"{safe_title}_{counter}.md"
        counter += 1
    
    output_path.write_text(new_content, encoding="utf-8")
    print(f"   ✓ 保存到: {output_path.name}")
    
    return True


async def main():
    print("=" * 60)
    print("   文档图片持久化处理脚本")
    print("=" * 60)
    
    # 检查 Token
    if not HELP_API_TOKEN:
        print("\n❌ 错误: 请在脚本中填入 HELP_API_TOKEN")
        print("   找到 HELP_API_TOKEN = \"\" 这行，填入有效的 Token")
        return
    
    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n输出目录: {OUTPUT_DIR}")
    
    # 初始化客户端
    print("\n[初始化] 创建客户端...")
    oss_client = SimpleOSSClient(OSS_CONFIG)
    help_client = HelpCenterClient(HELP_API_BASE, HELP_API_TOKEN)
    
    # 获取文档列表
    docs = get_doc_ids_from_db()
    if not docs:
        print("没有需要处理的文档")
        return
    
    # 获取已存在的文档，用于跳过
    existing_docs = get_existing_docs(OUTPUT_DIR)
    print(f"[跳过] 已存在 {len(existing_docs)} 个文档")
    
    # 过滤出需要处理的文档
    docs_to_process = []
    for doc_id, text in docs:
        # 使用与保存时相同的文件名清理逻辑
        safe_name = sanitize_filename(text) if text else doc_id
        if safe_name in existing_docs:
            print(f"   跳过已存在: {safe_name}")
        else:
            docs_to_process.append((doc_id, text))
    
    print(f"[待处理] {len(docs_to_process)} 个文档")
    
    if not docs_to_process:
        print("\n所有文档都已处理完成！")
        return
    
    # 处理每个文档
    success_count = 0
    fail_count = 0
    skip_count = len(docs) - len(docs_to_process)
    
    for i, (doc_id, text) in enumerate(docs_to_process, 1):
        print(f"\n[{i}/{len(docs_to_process)}]", end="")
        try:
            success = await process_single_doc(doc_id, help_client, oss_client, OUTPUT_DIR)
            if success:
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            print(f"   ✗ 处理异常: {e}")
            fail_count += 1
    
    # 汇总
    print("\n" + "=" * 60)
    print(f"处理完成!")
    print(f"   跳过: {skip_count}")
    print(f"   成功: {success_count}")
    print(f"   失败: {fail_count}")
    print(f"   输出目录: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

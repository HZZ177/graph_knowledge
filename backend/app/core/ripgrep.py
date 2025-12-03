"""Ripgrep 自动安装管理

服务启动时自动检测并安装 ripgrep，用于代码精确搜索。
"""

import os
import platform
import zipfile
import tarfile
import urllib.request
from pathlib import Path
from typing import Optional

from backend.app.core.logger import logger

# ripgrep 版本
RG_VERSION = "14.1.1"

# 下载地址
RG_DOWNLOAD_URLS = {
    "Windows": f"https://github.com/BurntSushi/ripgrep/releases/download/{RG_VERSION}/ripgrep-{RG_VERSION}-x86_64-pc-windows-msvc.zip",
    "Linux": f"https://github.com/BurntSushi/ripgrep/releases/download/{RG_VERSION}/ripgrep-{RG_VERSION}-x86_64-unknown-linux-musl.tar.gz",
    "Darwin": f"https://github.com/BurntSushi/ripgrep/releases/download/{RG_VERSION}/ripgrep-{RG_VERSION}-x86_64-apple-darwin.tar.gz",
}

# 本地存放路径: backend/resource/
RESOURCE_DIR = Path(__file__).parent.parent.parent / "resource"
RG_EXECUTABLE = "rg.exe" if platform.system() == "Windows" else "rg"
RG_PATH = RESOURCE_DIR / RG_EXECUTABLE


def get_ripgrep_path() -> str:
    """获取 ripgrep 可执行文件路径
    
    Returns:
        ripgrep 绝对路径
        
    Raises:
        RuntimeError: ripgrep 不可用
    """
    if not RG_PATH.exists():
        raise RuntimeError(
            f"ripgrep 未安装，请先调用 ensure_ripgrep_installed() 或手动下载到 {RG_PATH}"
        )
    return str(RG_PATH.absolute())


def is_ripgrep_installed() -> bool:
    """检查 ripgrep 是否已安装"""
    return RG_PATH.exists()


def ensure_ripgrep_installed() -> bool:
    """确保 ripgrep 已安装，未安装则自动下载
    
    Returns:
        True 表示已安装或安装成功，False 表示安装失败
    """
    if RG_PATH.exists():
        logger.info(f"[ripgrep] 已安装: {RG_PATH}")
        return True
    
    logger.info(f"[ripgrep] 未检测到 ripgrep，开始自动下载...")
    
    try:
        _download_and_install()
        logger.info(f"[ripgrep] 安装成功: {RG_PATH}")
        return True
    except Exception as e:
        logger.error(f"[ripgrep] 自动安装失败: {e}", exc_info=True)
        return False


def _download_and_install():
    """下载并安装 ripgrep"""
    system = platform.system()
    url = RG_DOWNLOAD_URLS.get(system)
    
    if not url:
        raise RuntimeError(f"不支持的操作系统: {system}")
    
    # 创建 resource 目录
    RESOURCE_DIR.mkdir(parents=True, exist_ok=True)
    
    # 确定压缩包路径
    is_zip = url.endswith(".zip")
    archive_name = "rg_temp.zip" if is_zip else "rg_temp.tar.gz"
    archive_path = RESOURCE_DIR / archive_name
    
    try:
        # 下载
        logger.info(f"[ripgrep] 正在从 GitHub 下载 v{RG_VERSION}...")
        urllib.request.urlretrieve(url, archive_path)
        
        # 解压
        logger.info(f"[ripgrep] 下载完成，正在解压...")
        
        if is_zip:
            _extract_from_zip(archive_path)
        else:
            _extract_from_tar(archive_path)
            
    finally:
        # 清理临时文件
        if archive_path.exists():
            archive_path.unlink()


def _extract_from_zip(archive_path: Path):
    """从 zip 文件解压 rg.exe (Windows)"""
    with zipfile.ZipFile(archive_path, 'r') as zf:
        for name in zf.namelist():
            if name.endswith("rg.exe"):
                with zf.open(name) as src, open(RG_PATH, 'wb') as dst:
                    dst.write(src.read())
                return
    raise RuntimeError("在压缩包中未找到 rg.exe")


def _extract_from_tar(archive_path: Path):
    """从 tar.gz 文件解压 rg (Linux/macOS)"""
    with tarfile.open(archive_path, 'r:gz') as tf:
        for member in tf.getmembers():
            if member.name.endswith("/rg") or member.name == "rg":
                # 直接读取内容写入目标路径
                f = tf.extractfile(member)
                if f:
                    with open(RG_PATH, 'wb') as dst:
                        dst.write(f.read())
                    # 添加执行权限
                    os.chmod(RG_PATH, 0o755)
                    return
    raise RuntimeError("在压缩包中未找到 rg")

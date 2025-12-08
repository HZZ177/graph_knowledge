"""文件上传 API"""

import uuid
from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.orm import Session
from loguru import logger

from backend.app.db.sqlite import SessionLocal
from backend.app.models.chat import FileUpload
from backend.app.services.chat.storage import get_storage_service
from backend.app.core.utils import success_response, error_response


router = APIRouter(prefix="/files", tags=["files"])


# ========== Dependency ==========

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ========== API Routes ==========

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """上传文件
    
    支持的文件类型：
    - 图片: jpg, png, webp, gif
    - 文档: pdf, txt, md, log, json
    - 代码: py, js, ts, java, cpp, c, go
    
    限制：
    - 最大文件大小: 10MB
    """
    logger.info(f"[FileAPI] 收到上传请求: {file.filename}, {file.content_type}")
    
    try:
        # 读取文件内容
        file_bytes = await file.read()
        
        # 获取存储服务
        try:
            storage = get_storage_service()
        except Exception as e:
            logger.error(f"[FileAPI] 获取存储服务失败: {e}")
            raise RuntimeError(f"存储服务未初始化: {e}")
        
        # 上传到 OSS
        try:
            file_key, url = await storage.upload_file(
                file_bytes=file_bytes,
                filename=file.filename,
                content_type=file.content_type or "application/octet-stream"
            )
        except Exception as e:
            logger.error(f"[FileAPI] OSS 上传失败: {type(e).__name__}: {e}")
            raise
        
        # 保存文件元数据到数据库
        file_id = str(uuid.uuid4())
        file_record = FileUpload(
            id=file_id,
            file_key=file_key,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            size=len(file_bytes),
            url=url,
            conversation_id=None  # 初始未关联
        )
        
        db.add(file_record)
        db.commit()
        
        logger.info(f"[FileAPI] 上传完成: {file.filename} ({len(file_bytes)} bytes) -> {file_id}")
        
        return success_response(
            message="上传成功",
            data={
                "file_id": file_id,
                "url": url,
                "filename": file.filename,
                "size": len(file_bytes),
                "content_type": file.content_type or "application/octet-stream"
            }
        )
    
    except ValueError as e:
        # 验证错误（文件大小、类型等）
        logger.warning(f"[FileAPI] 文件验证失败: {e}")
        return error_response(message=str(e))
    except Exception as e:
        logger.error(f"[FileAPI] 文件上传失败: {type(e).__name__}: {e}")
        return error_response(message=f"文件上传失败: {str(e)}")


@router.get("/{file_id}")
async def get_file_info(
    file_id: str,
    db: Session = Depends(get_db)
):
    """获取文件信息"""
    file_record = db.query(FileUpload).filter(FileUpload.id == file_id).first()
    
    if not file_record:
        return error_response(message="文件不存在")
    
    return success_response(data={
        "file_id": file_record.id,
        "url": file_record.url,
        "filename": file_record.filename,
        "size": file_record.size,
        "content_type": file_record.content_type,
        "conversation_id": file_record.conversation_id,
        "uploaded_at": file_record.uploaded_at.isoformat()
    })


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    db: Session = Depends(get_db)
):
    """删除文件"""
    logger.info(f"[FileAPI] 收到删除请求: file_id={file_id}")
    
    file_record = db.query(FileUpload).filter(FileUpload.id == file_id).first()
    
    if not file_record:
        logger.warning(f"[FileAPI] 删除失败: 文件不存在 file_id={file_id}")
        return error_response(message="文件不存在")
    
    logger.info(f"[FileAPI] 开始删除: {file_record.filename} (key={file_record.file_key})")
    
    try:
        # 从 OSS 删除
        storage = get_storage_service()
        await storage.delete_file(file_record.file_key)
        
        # 从数据库删除
        db.delete(file_record)
        db.commit()
        
        logger.info(f"[FileAPI] 删除完成: {file_record.filename}")
        
        return success_response(message="文件删除成功")
    
    except Exception as e:
        logger.error(f"[FileAPI] 删除失败: {file_record.filename}, error={e}")
        return error_response(message=f"文件删除失败: {str(e)}")


@router.get("/")
async def list_files(
    conversation_id: str = None,
    db: Session = Depends(get_db)
):
    """列出文件（可按会话 ID 筛选）"""
    query = db.query(FileUpload)
    
    if conversation_id:
        query = query.filter(FileUpload.conversation_id == conversation_id)
    
    files = query.order_by(FileUpload.uploaded_at.desc()).limit(100).all()
    
    return success_response(data=[
        {
            "file_id": f.id,
            "url": f.url,
            "filename": f.filename,
            "size": f.size,
            "content_type": f.content_type,
            "conversation_id": f.conversation_id,
            "uploaded_at": f.uploaded_at.isoformat()
        }
        for f in files
    ])

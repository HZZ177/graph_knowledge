"""文件上传 API"""

import uuid
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from loguru import logger

from backend.app.db.sqlite import SessionLocal
from backend.app.models.file_upload import FileUpload
from backend.app.services.file_storage import get_storage_service


router = APIRouter(prefix="/files", tags=["files"])


# ========== Schemas ==========

class FileUploadResponse(BaseModel):
    """文件上传响应"""
    file_id: str
    url: str
    filename: str
    size: int
    content_type: str


class FileInfoResponse(BaseModel):
    """文件信息响应"""
    file_id: str
    url: str
    filename: str
    size: int
    content_type: str
    conversation_id: str | None
    uploaded_at: str


# ========== Dependency ==========

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ========== API Routes ==========

@router.post("/upload", response_model=FileUploadResponse)
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
    try:
        # 读取文件内容
        file_bytes = await file.read()
        
        # 获取存储服务
        storage = get_storage_service()
        
        # 上传到 OSS
        file_key, url = await storage.upload_file(
            file_bytes=file_bytes,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream"
        )
        
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
        
        logger.info(f"[FileAPI] 文件上传成功: {file.filename} ({len(file_bytes)} bytes)")
        
        return FileUploadResponse(
            file_id=file_id,
            url=url,
            filename=file.filename,
            size=len(file_bytes),
            content_type=file.content_type or "application/octet-stream"
        )
    
    except ValueError as e:
        # 验证错误（文件大小、类型等）
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[FileAPI] 文件上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@router.get("/{file_id}", response_model=FileInfoResponse)
async def get_file_info(
    file_id: str,
    db: Session = Depends(get_db)
):
    """获取文件信息"""
    file_record = db.query(FileUpload).filter(FileUpload.id == file_id).first()
    
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    return FileInfoResponse(
        file_id=file_record.id,
        url=file_record.url,
        filename=file_record.filename,
        size=file_record.size,
        content_type=file_record.content_type,
        conversation_id=file_record.conversation_id,
        uploaded_at=file_record.uploaded_at.isoformat()
    )


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    db: Session = Depends(get_db)
):
    """删除文件"""
    file_record = db.query(FileUpload).filter(FileUpload.id == file_id).first()
    
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    try:
        # 从 OSS 删除
        storage = get_storage_service()
        await storage.delete_file(file_record.file_key)
        
        # 从数据库删除
        db.delete(file_record)
        db.commit()
        
        logger.info(f"[FileAPI] 文件删除成功: {file_record.filename}")
        
        return {"message": "文件删除成功"}
    
    except Exception as e:
        logger.error(f"[FileAPI] 文件删除失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件删除失败: {str(e)}")


@router.get("/", response_model=List[FileInfoResponse])
async def list_files(
    conversation_id: str = None,
    db: Session = Depends(get_db)
):
    """列出文件（可按会话 ID 筛选）"""
    query = db.query(FileUpload)
    
    if conversation_id:
        query = query.filter(FileUpload.conversation_id == conversation_id)
    
    files = query.order_by(FileUpload.uploaded_at.desc()).limit(100).all()
    
    return [
        FileInfoResponse(
            file_id=f.id,
            url=f.url,
            filename=f.filename,
            size=f.size,
            content_type=f.content_type,
            conversation_id=f.conversation_id,
            uploaded_at=f.uploaded_at.isoformat()
        )
        for f in files
    ]

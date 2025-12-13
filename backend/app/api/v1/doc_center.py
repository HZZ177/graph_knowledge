"""
文档中心 API 路由

前端只与本地数据库交互，通过同步按钮从帮助中心拉取数据

接口：
- POST /sync              从帮助中心同步目录+文档结构到本地
- GET  /tree              获取本地目录树
- GET  /documents         获取本地文档列表
- GET  /documents/{id}    获取文档详情
- GET  /documents/{id}/content  获取文档内容
- POST /documents/{id}/sync-content  同步单个文档内容
- POST /index             提交索引任务
- GET  /index/status      获取索引队列状态
- WS   /ws                WebSocket 进度推送
"""

import asyncio
import json
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.db.sqlite import get_db
from backend.app.core.logger import logger
from backend.app.services.doc_center_service import DocCenterService
from backend.app.services.lightrag_index_service import LightRAGIndexService


router = APIRouter(prefix="/doc-center", tags=["文档中心"])


# ============== 请求/响应模型 ==============

class SyncRequest(BaseModel):
    """同步请求"""
    documents: List[dict]  # [{source_doc_id, title, parent_id}]


class IndexRequest(BaseModel):
    """索引请求"""
    document_ids: List[str]  # 本地文档ID列表
    priority: int = 0


class DocumentResponse(BaseModel):
    """文档响应"""
    id: str
    source_doc_id: str
    title: str
    path: Optional[str] = None
    sync_status: str
    synced_at: Optional[str] = None
    index_status: str
    # 图片增强结果
    image_enhance_total: int = 0
    image_enhance_success: int = 0
    # 三阶段进度
    extraction_progress: int = 0
    entities_total: int = 0
    entities_done: int = 0
    relations_total: int = 0
    relations_done: int = 0
    created_at: Optional[str] = None


# ============== 同步接口 ==============

@router.post("/sync")
async def sync_from_help_center(db: Session = Depends(get_db)):
    """
    从帮助中心同步目录结构和文档列表到本地
    
    只同步结构，不下载文档内容
    """
    try:
        result = DocCenterService.sync_structure_from_help_center(db)
        return {
            "code": 0,
            "data": result,
            "message": f"同步完成: {result['folders_synced']} 目录, {result['documents_synced']} 文档"
        }
    except Exception as e:
        logger.error(f"[DocCenterAPI] 同步失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== 本地数据接口 ==============

@router.get("/tree")
async def get_directory_tree(db: Session = Depends(get_db)):
    """
    获取本地目录树结构
    """
    try:
        tree = DocCenterService.get_directory_tree(db)
        return {"code": 0, "data": tree, "message": "success"}
    except Exception as e:
        logger.error(f"[DocCenterAPI] 获取目录树失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents")
async def get_documents(
    parent_id: Optional[str] = None,
    sync_status: Optional[str] = None,
    index_status: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db)
):
    """
    获取本地文档列表
    
    参数:
    - keyword: 按标题模糊搜索
    - sync_status: 同步状态筛选 (pending/syncing/synced/failed)
    - index_status: 索引状态筛选 (pending/queued/indexing/indexed/failed)
    """
    try:
        result = DocCenterService.get_documents(
            db, parent_id, sync_status, index_status, keyword, page, page_size
        )
        return {"code": 0, "data": result, "message": "success"}
    except Exception as e:
        logger.error(f"[DocCenterAPI] 获取文档列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str, db: Session = Depends(get_db)):
    """获取文档详情"""
    doc = DocCenterService.get_document_by_id(db, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    return {
        "code": 0,
        "data": {
            "id": doc.id,
            "source_doc_id": doc.source_doc_id,
            "title": doc.title,
            "path": doc.path,
            "sync_status": doc.sync_status,
            "sync_error": doc.sync_error,
            "synced_at": doc.synced_at.isoformat() if doc.synced_at else None,
            "image_count": doc.image_count,
            "index_status": doc.index_status,
            "extraction_progress": doc.extraction_progress,
            "entities_total": doc.entities_total,
            "entities_done": doc.entities_done,
            "relations_total": doc.relations_total,
            "relations_done": doc.relations_done,
            "index_error": doc.index_error,
            "chunk_count": doc.chunk_count,
            "entity_count": doc.entity_count,
            "relation_count": doc.relation_count,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        },
        "message": "success"
    }


@router.get("/documents/{doc_id}/content")
async def get_document_content(doc_id: str, db: Session = Depends(get_db)):
    """获取文档内容（Markdown）"""
    content = DocCenterService.get_document_content(db, doc_id)
    if content is None:
        raise HTTPException(status_code=404, detail="文档内容不存在")

    return {"code": 0, "data": {"content": content}, "message": "success"}


@router.post("/documents/{doc_id}/sync-content")
async def sync_document_content(doc_id: str, db: Session = Depends(get_db)):
    """
    同步单个文档内容
    
    从帮助中心下载文档内容，处理图片，保存到本地
    """
    doc = DocCenterService.get_document_by_id(db, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 进度回调：通过 WebSocket 广播
    async def progress_callback(phase: str, current: int, total: int, detail: str):
        await ws_manager.broadcast({
            "type": "sync_progress",
            "document_id": doc_id,
            "title": doc.title,
            "phase": phase,
            "current": current,
            "total": total,
            "detail": detail,
        })

    try:
        result = await DocCenterService.sync_document(
            db, doc.source_doc_id, doc.title, doc.source_parent_id,
            progress_callback=progress_callback
        )
        # 同步完成后广播完成状态（包含图片增强结果）
        # 重新查询获取最新数据
        db.refresh(doc)
        await ws_manager.broadcast({
            "type": "sync_progress",
            "document_id": doc_id,
            "title": doc.title,
            "phase": "completed" if result["success"] else "failed",
            "current": 0,
            "total": 0,
            "detail": "同步完成" if result["success"] else result.get("error", "同步失败"),
            "image_enhance_total": doc.image_enhance_total or 0,
            "image_enhance_success": doc.image_enhance_success or 0,
        })
        return {"code": 0, "data": result, "message": "success" if result["success"] else result.get("error")}
    except Exception as e:
        logger.error(f"[DocCenterAPI] 同步文档内容失败: {doc_id}, {e}")
        await ws_manager.broadcast({
            "type": "sync_progress",
            "document_id": doc_id,
            "title": doc.title,
            "phase": "failed",
            "current": 0,
            "total": 0,
            "detail": str(e),
        })
        raise HTTPException(status_code=500, detail=str(e))


# ============== 索引接口 ==============

@router.post("/index")
async def create_index_tasks(
    request: IndexRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    创建索引任务
    
    将文档加入索引队列
    """
    if not request.document_ids:
        raise HTTPException(status_code=400, detail="文档ID列表不能为空")

    tasks = []
    for doc_id in request.document_ids:
        doc = DocCenterService.get_document_by_id(db, doc_id)
        if not doc:
            tasks.append({"document_id": doc_id, "success": False, "error": "文档不存在"})
            continue

        if doc.sync_status != "synced":
            tasks.append({"document_id": doc_id, "success": False, "error": "文档未同步"})
            continue

        try:
            task = LightRAGIndexService.create_task(db, doc_id, request.priority)
            tasks.append({
                "document_id": doc_id,
                "task_id": task.id,
                "success": True,
            })
        except Exception as e:
            tasks.append({"document_id": doc_id, "success": False, "error": str(e)})

    # 在后台启动队列处理
    background_tasks.add_task(LightRAGIndexService.process_queue)

    return {
        "code": 0,
        "data": {"tasks": tasks},
        "message": f"已创建 {sum(1 for t in tasks if t['success'])} 个任务"
    }


@router.get("/index/status")
async def get_index_status(db: Session = Depends(get_db)):
    """获取索引队列状态"""
    status = LightRAGIndexService.get_queue_status(db)
    return {"code": 0, "data": status, "message": "success"}


@router.post("/index/process")
async def trigger_process_queue(background_tasks: BackgroundTasks):
    """手动触发队列处理"""
    background_tasks.add_task(LightRAGIndexService.process_queue)
    return {"code": 0, "message": "已触发队列处理"}


@router.delete("/index/{doc_id}")
async def cancel_index_task(doc_id: str, db: Session = Depends(get_db)):
    """取消排队中的索引任务"""
    result = LightRAGIndexService.cancel_task(db, doc_id)
    if result["success"]:
        return {"code": 0, "data": result, "message": "已取消索引任务"}
    else:
        raise HTTPException(status_code=400, detail=result["error"])


@router.post("/index/stop/{doc_id}")
async def stop_index_task(doc_id: str, db: Session = Depends(get_db)):
    """停止正在运行的索引任务"""
    result = await LightRAGIndexService.stop_running_task(db, doc_id)
    if result["success"]:
        return {"code": 0, "data": result, "message": "已请求停止索引"}
    else:
        raise HTTPException(status_code=400, detail=result["error"])


# ============== WebSocket 进度推送 ==============

class ConnectionManager:
    """WebSocket 连接管理"""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"[DocCenterWS] 客户端连接: {client_id}")

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)
        logger.info(f"[DocCenterWS] 客户端断开: {client_id}")

    async def send_message(self, client_id: str, message: dict):
        websocket = self.active_connections.get(client_id)
        if websocket:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.warning(f"[DocCenterWS] 发送消息失败: {e}")

    async def broadcast(self, message: dict):
        for client_id, websocket in list(self.active_connections.items()):
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.warning(f"[DocCenterWS] 广播失败 ({client_id}): {e}")
                self.disconnect(client_id)


ws_manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 进度推送
    
    客户端连接后，会自动接收索引进度更新
    """
    import uuid
    client_id = str(uuid.uuid4())[:8]

    await ws_manager.connect(websocket, client_id)

    # 注册进度回调
    async def progress_callback(message: dict):
        await ws_manager.send_message(client_id, {
            "type": "index_progress",
            **message
        })

    LightRAGIndexService.subscribe_progress(client_id, progress_callback)

    try:
        # 发送初始状态
        db = next(get_db())
        status = LightRAGIndexService.get_queue_status(db)
        db.close()
        await ws_manager.send_message(client_id, {
            "type": "queue_status",
            **status
        })

        # 保持连接
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # 处理心跳或命令
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await ws_manager.send_message(client_id, {"type": "pong"})
            except asyncio.TimeoutError:
                # 发送心跳
                await ws_manager.send_message(client_id, {"type": "heartbeat"})
            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        pass
    finally:
        LightRAGIndexService.unsubscribe_progress(client_id)
        ws_manager.disconnect(client_id)

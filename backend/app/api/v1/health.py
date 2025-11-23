from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.db.sqlite import get_db
from backend.app.services.graph_sync_service import check_neo4j_health
from backend.app.models.resource_graph import Business
from backend.app.core.logger import logger


router = APIRouter(prefix="/health", tags=["health"])


@router.get("/check_neo4j")
async def check_neo4j() -> dict:
    """检查Neo4j连接健康状态"""
    logger.info("执行Neo4j健康检查")
    result = check_neo4j_health()
    logger.info(f"Neo4j健康检查结果: connected={result['connected']}")
    return result


@router.get("/get_sync_status/{process_id}")
async def get_sync_status(process_id: str, db: Session = Depends(get_db)) -> dict:
    """获取指定流程的同步状态
    
    Returns:
        包含SQLite和Neo4j的状态信息
    """
    logger.info(f"获取同步状态 process_id={process_id}")
    
    process = db.query(Business).filter(Business.process_id == process_id).first()
    
    if not process:
        return {
            "process_id": process_id,
            "sqlite_status": "not_found",
            "neo4j_status": "unknown",
            "message": "流程不存在"
        }
    
    return {
        "process_id": process_id,
        "process_name": process.name,
        "sqlite_status": "saved",
        "neo4j_status": process.sync_status or "never_synced",
        "last_sync_at": process.last_sync_at.isoformat() if process.last_sync_at else None,
        "sync_error": process.sync_error,
        "message": "查询成功"
    }


@router.get("/get_system_health")
async def system_health(db: Session = Depends(get_db)) -> dict:
    """获取系统整体健康状态
    
    Returns:
        包含SQLite和Neo4j的整体状态
    """
    logger.info("执行系统健康检查")
    
    # 检查SQLite
    sqlite_status = "healthy"
    try:
        db.execute("SELECT 1")
    except Exception as e:
        sqlite_status = "unhealthy"
        logger.error(f"SQLite健康检查失败: {e}")
    
    # 检查Neo4j
    neo4j_result = check_neo4j_health()
    
    # 统计同步状态
    try:
        total_processes = db.query(Business).count()
        synced_count = db.query(Business).filter(Business.sync_status == "synced").count()
        failed_count = db.query(Business).filter(Business.sync_status == "failed").count()
        never_synced_count = db.query(Business).filter(
            (Business.sync_status == "never_synced") | (Business.sync_status == None)
        ).count()
    except Exception as e:
        logger.error(f"统计同步状态失败: {e}")
        total_processes = 0
        synced_count = 0
        failed_count = 0
        never_synced_count = 0
    
    return {
        "sqlite": {
            "status": sqlite_status,
            "message": "SQLite连接正常" if sqlite_status == "healthy" else "SQLite连接异常"
        },
        "neo4j": {
            "status": "healthy" if neo4j_result["connected"] else "unhealthy",
            "connected": neo4j_result["connected"],
            "message": neo4j_result["message"],
            "database": neo4j_result["database"],
            "error": neo4j_result["error"]
        },
        "sync_stats": {
            "total_processes": total_processes,
            "synced": synced_count,
            "failed": failed_count,
            "never_synced": never_synced_count
        }
    }

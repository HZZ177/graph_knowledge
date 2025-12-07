"""文件清理任务（定时清理未关联对话的临时文件）"""

from datetime import datetime, timedelta, timezone
from loguru import logger
from sqlalchemy.orm import Session

from backend.app.db.sqlite import SessionLocal
from backend.app.models.file_upload import FileUpload
from backend.app.services.file_storage import get_storage_service


async def cleanup_orphan_files(retention_days: int = 7):
    """清理未关联对话的临时文件
    
    Args:
        retention_days: 保留天数，超过此天数的未关联文件将被删除
    """
    db = SessionLocal()
    
    try:
        # 计算过期时间
        expired_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        
        # 查询未关联对话且过期的文件
        orphan_files = db.query(FileUpload).filter(
            FileUpload.uploaded_at < expired_date,
            FileUpload.conversation_id == None
        ).all()
        
        if not orphan_files:
            logger.info(f"[FileCleanup] 无需清理的文件（保留期: {retention_days}天）")
            return
        
        logger.info(f"[FileCleanup] 发现 {len(orphan_files)} 个待清理文件")
        
        # 获取存储服务
        storage = get_storage_service()
        
        # 删除文件
        success_count = 0
        fail_count = 0
        
        for file_record in orphan_files:
            try:
                # 从 OSS 删除
                await storage.delete_file(file_record.file_key)
                
                # 从数据库删除
                db.delete(file_record)
                db.commit()
                
                success_count += 1
                logger.info(f"[FileCleanup] 删除文件: {file_record.filename} (ID: {file_record.id})")
            
            except Exception as e:
                fail_count += 1
                logger.error(f"[FileCleanup] 删除文件失败: {file_record.filename}, 错误: {e}")
                db.rollback()
        
        logger.info(f"[FileCleanup] 清理完成: 成功 {success_count} 个, 失败 {fail_count} 个")
    
    except Exception as e:
        logger.error(f"[FileCleanup] 清理任务异常: {e}")
    
    finally:
        db.close()


def setup_cleanup_scheduler():
    """设置定时清理任务（可选）
    
    使用 APScheduler 设置定时任务，每天凌晨 2 点执行清理。
    需要在 main.py 的 lifespan 中调用此函数。
    
    示例：
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            cleanup_orphan_files,
            'cron',
            hour=2,
            minute=0,
            kwargs={'retention_days': 7}
        )
        scheduler.start()
    """
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from backend.app.services.file_storage.config import StorageConfig
        
        # 加载配置
        config = StorageConfig()
        retention_days = config.file_retention_days
        
        # 创建调度器
        scheduler = AsyncIOScheduler()
        
        # 添加任务：每天凌晨 2 点执行
        scheduler.add_job(
            cleanup_orphan_files,
            'cron',
            hour=2,
            minute=0,
            kwargs={'retention_days': retention_days}
        )
        
        scheduler.start()
        logger.info(f"[FileCleanup] 定时清理任务已启动（每天 02:00，保留期 {retention_days} 天）")
        
        return scheduler
    
    except ImportError:
        logger.warning("[FileCleanup] APScheduler 未安装，跳过定时清理任务设置")
        logger.warning("[FileCleanup] 如需启用，请安装: pip install apscheduler")
        return None

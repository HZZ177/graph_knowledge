
import sys
import threading
from datetime import datetime
from loguru import logger
from typing import List, Union, Dict, Any
from backend.app.core.file_path import log_path
from contextvars import ContextVar

# 创建全局上下文变量用于存储traceId
trace_id_var: ContextVar[str] = ContextVar('trace_id', default='')


# 自定义每个级别日志的信息头颜色
logger.level("DEBUG", color="<blue>")
logger.level("INFO", color="<green>")
logger.level("SUCCESS", color="<bold><green>")
logger.level("WARNING", color="<yellow>")
logger.level("ERROR", color="<red>")
logger.level("CRITICAL", color="<bold><red>")


def trace_id_filter(record):
    """
    自定义日志过滤器，为每条日志记录注入traceId
    
    Args:
        record: loguru的日志记录对象
    
    Returns:
        bool: 始终返回True，表示不过滤任何日志
    """
    # 从上下文变量中获取traceId，如果不存在则为空字符串
    trace_id = trace_id_var.get()
    # 将traceId注入到record的extra字段中，供格式化使用
    record["extra"]["trace_id"] = trace_id
    return True


# 配置自定义 logger handler，输出日志到：1、标准输出 2、日志输出文件
logger.configure(
    handlers=[
        {
            "sink": sys.stdout,  # 日志输出到标准输出
            "level": "DEBUG",  # 日志级别
            "format": "<green>{time:YYYY-MM-DD HH:mm:ss.SSSS}</green> | <cyan>traceId:{extra[trace_id]}</cyan> | <green>{module}:{line}</green> | <level>{level}</level> | {message}",
            "colorize": True,  # 启用颜色
            "backtrace": False,   # 控制是否追溯详细的回溯信息（即代码调用链和变量状态等详细信息）
            "diagnose": False,    # 控制不会包含详细的诊断信息
            "enqueue": False,  # 关闭多线程安全队列
            "filter": trace_id_filter,  # 添加自定义过滤器注入traceId
        },
        {
            "sink": f"{log_path}/graph_knowledge_engine_{{time:YYYY-MM-DD_HH}}.log",  # 指定日志输出到文件
            "level": "DEBUG",  # 日志级别
            "format": "{time:YYYY-MM-DD HH:mm:ss.SSSS} | traceId:{extra[trace_id]} | {module}:{line} | {level} | {message}",  # 日志格式
            "rotation": "1 hour",  # 每小时自动分割日志
            "retention": "7 days",  # 保留最近 7 天的日志文件
            "compression": "zip",  # 压缩日志文件
            "backtrace": True,   # 控制是否追溯详细的回溯信息（即代码调用链和变量状态等详细信息）
            "diagnose": True,  # 控制是否包含详细的诊断信息
            "enqueue": False,  # 关闭多线程安全队列
            "filter": trace_id_filter,  # 添加自定义过滤器注入traceId
        }
    ]
)


# 定义全局异常捕获函数，处理未捕获的异常
def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    # 忽略系统退出异常（如 Ctrl+C 中断）
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    # 记录未捕获的异常栈信息
    logger.opt(exception=(exc_type, exc_value, exc_traceback)).error("未捕获的异常")


# 设置全局异常捕获钩子
sys.excepthook = handle_uncaught_exception

# 捕获线程中的未捕获异常（Python 3.8+ 支持）
if hasattr(threading, "excepthook"):
    threading.excepthook = lambda args: logger.opt(exception=(args.exc_type, args.exc_value, args.exc_traceback)).error("线程中未捕获的异常")

# 供其他模块引用的 logger 和 trace_id_var
logger = logger
__all__ = ['logger', 'trace_id_var']

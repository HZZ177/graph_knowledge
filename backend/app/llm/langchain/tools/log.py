"""日志查询类工具

提供企业日志系统查询能力：
- search_logs: 搜索日志
- LogQueryConfig: 日志查询配置
"""

import json
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Annotated

import httpx
from langchain_core.tools import tool, InjectedToolArg
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from backend.app.core.logger import logger


# ============================================================
# 日志查询配置
# ============================================================

class BusinessLine(str, Enum):
    """业务线枚举 - 控制日志查询范围"""
    YONGCE_TEST = "永策测试"
    PROD = "永策C+路侧分区"
    PRIVATE = "私有化"


class LogServerName(str, Enum):
    """日志服务名称枚举 - 白名单控制"""
    VEHICLE_OWNER_SERVER = "vehicle-owner-server"
    VEHICLE_OWNER_ADMIN = "vehicle-owner-admin"
    PAY_CENTER = "vehicle-pay-center"


class PrivateServer(str, Enum):
    """私有化集团枚举"""
    RENJULE = "人居乐"
    KUERLE = "库尔勒"
    FUZHOU_GONGYEYUAN = "福州工业园"


class LogQueryConfig:
    """日志查询配置"""
    API_URL = "https://ts.keytop.cn/cd-common-server/log-query/list"
    API_APP_ID = "testai"
    API_SECRET_KEY = "d73833a466c040819dd086db57c0ed82"
    DEFAULT_LIMIT = 2000
    DEFAULT_PAGE_SIZE = 25
    MAX_TIME_RANGE_HOURS = 24
    LOG_CONTENT_MAX_LENGTH = 2500
    REQUEST_TIMEOUT = 30

    @classmethod
    def get_allowed_business_lines(cls) -> List[str]:
        return [e.value for e in BusinessLine]

    @classmethod
    def get_allowed_server_names(cls) -> List[str]:
        return [e.value for e in LogServerName]

    @classmethod
    def get_private_servers(cls) -> List[str]:
        return [e.value for e in PrivateServer]

    @classmethod
    def validate_business_line(cls, value: str) -> bool:
        return value in cls.get_allowed_business_lines()

    @classmethod
    def validate_time_range(cls, start_time: datetime, end_time: datetime) -> tuple:
        if end_time <= start_time:
            return False, "结束时间必须大于开始时间"
        time_diff = end_time - start_time
        if time_diff > timedelta(hours=cls.MAX_TIME_RANGE_HOURS):
            hours = time_diff.total_seconds() / 3600
            return False, f"时间范围超过限制：当前 {hours:.1f} 小时，最大允许 {cls.MAX_TIME_RANGE_HOURS} 小时"
        return True, ""

    @classmethod
    def get_all_server_descriptions(cls) -> str:
        """获取所有服务的描述，用于 System Prompt"""
        descriptions = {
            "vehicle-owner-server": "车主服务主服务，处理车主相关核心业务逻辑",
            "vehicle-owner-admin": "车主服务管理后台，处理各种后台运营管理功能，接收部分第三方上报等消息",
            "vehicle-pay-center": "车主服务核心支付服务，处理核心支付等交易",
        }
        lines = [f"- **{name}**：{desc}" for name, desc in descriptions.items()]
        return "\n".join(lines)


# ============================================================
# search_logs 工具
# ============================================================

class SearchLogsInput(BaseModel):
    """search_logs 工具输入参数"""
    keyword: str = Field(..., description="主要搜索关键词，如 trace_id 等")
    keyword2: str = Field(default="", description="次要关键词（可选），与主关键词是 AND 关系")
    server_name: LogServerName = Field(..., description="服务名称，从可用服务列表中选择")
    start_time: str = Field(..., description="开始时间，格式：YYYY-MM-DD HH:mm:ss")
    end_time: str = Field(..., description="结束时间，格式：YYYY-MM-DD HH:mm:ss")
    page_no: int = Field(default=1, description="页码，从 1 开始", ge=1)


@tool(args_schema=SearchLogsInput)
def search_logs(
    keyword: str,
    server_name: LogServerName,
    start_time: str,
    end_time: str,
    keyword2: str = "",
    page_no: int = 1,
    config: Annotated[RunnableConfig, InjectedToolArg] = None,
) -> str:
    """在企业日志系统中搜索日志。

    根据关键词、服务名称和时间范围查询日志。支持分页查询。
    可用于：错误排查、链路追踪（使用 trace_id 作为关键词）、业务问题定位。
    
    注意：时间范围不能超过 24 小时，服务名称必须从可用列表中选择。
    """
    # 1. 从 config.metadata 获取用户在 UI 选择的配置
    #    这些参数不由 AI 决定，而是通过 LangChain 的 config 机制从前端传递
    #    数据流：前端选择 → WebSocket → agent_context → config["metadata"] → 工具参数
    if not config:
        return json.dumps({"success": False, "error": "系统错误：缺少运行时配置"}, ensure_ascii=False)
    
    try:
        metadata = config.get("metadata", {}) or {}
        log_query = metadata.get("agent_context", {}).get("log_query", {})
        business_line = log_query.get("businessLine")
        private_server = log_query.get("privateServer")
        
        if not business_line:
            return json.dumps({"success": False, "error": "请在界面左上角选择业务线配置"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": f"获取业务线配置失败: {e}"}, ensure_ascii=False)
    
    logger.info(f"[search_logs] 开始查询: keyword={keyword}, server={server_name.value}, "
                f"time={start_time}~{end_time}, business_line={business_line}")
    
    # 2. 验证时间范围
    try:
        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        is_valid, error_msg = LogQueryConfig.validate_time_range(start_dt, end_dt)
        if not is_valid:
            return json.dumps({"success": False, "error": error_msg}, ensure_ascii=False)
    except ValueError as e:
        return json.dumps({"success": False, "error": f"时间格式错误: {e}"}, ensure_ascii=False)
    
    # 3. 验证业务线
    if not LogQueryConfig.validate_business_line(business_line):
        allowed = LogQueryConfig.get_allowed_business_lines()
        return json.dumps({"success": False, "error": f"业务线 '{business_line}' 不在允许列表中: {allowed}"}, ensure_ascii=False)
    
    # 4. 构建请求
    request_payload = {
        "keyword": keyword,
        "keyword2": keyword2 or "",
        "businessLine": business_line,
        "serverName": server_name.value,
        "privateServer": private_server,
        "startTime": start_time,
        "endTime": end_time,
        "limit": LogQueryConfig.DEFAULT_LIMIT,
        "pageNo": page_no,
        "pageSize": LogQueryConfig.DEFAULT_PAGE_SIZE,
    }
    headers = {
        "appId": LogQueryConfig.API_APP_ID,
        "secretKey": LogQueryConfig.API_SECRET_KEY
    }
    
    # 5. 调用 API
    try:
        with httpx.Client(timeout=LogQueryConfig.REQUEST_TIMEOUT) as client:
            response = client.post(LogQueryConfig.API_URL, json=request_payload, headers=headers)
            response.raise_for_status()
            response_data = response.json()
        
        if response_data.get("code") != 200:
            return json.dumps({"success": False, "error": response_data.get("message", "未知错误")}, ensure_ascii=False)
        
        # API 不支持分页，客户端自行分页
        data = response_data.get("data", {})
        all_records = data.get("records", [])
        total = len(all_records)
        logger.debug(f"[search_logs] API 返回 {total} 条记录")
        
        # 客户端分页
        page_size = LogQueryConfig.DEFAULT_PAGE_SIZE
        start_idx = (page_no - 1) * page_size
        end_idx = start_idx + page_size
        page_records = all_records[start_idx:end_idx]
        
        # 格式化日志：[时间] [Pod] 内容
        log_lines = []
        for record in page_records:
            pod = record.get("pod", "")
            content = record.get("content", "")[:LogQueryConfig.LOG_CONTENT_MAX_LENGTH]
            log_lines.append(f"{pod}] {content}")
        logs_text = "\n".join(log_lines) if log_lines else "(无日志)"
        
        # 简洁头部
        total_pages = (total + page_size - 1) // page_size
        result_text = f"[{server_name.value}] 共{total}条 第{page_no}/{total_pages}页\n{logs_text}"
        if page_no < total_pages:
            result_text += f"\n(更多: page_no={page_no + 1})"
        
        logger.info(f"[search_logs] 查询成功: total={total}")
        return result_text
        
    except httpx.TimeoutException:
        return json.dumps({"success": False, "error": f"请求超时（{LogQueryConfig.REQUEST_TIMEOUT}秒）"}, ensure_ascii=False)
    except httpx.HTTPStatusError as e:
        return json.dumps({"success": False, "error": f"HTTP 错误: {e.response.status_code}"}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[search_logs] 查询异常: {e}", exc_info=True)
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


if __name__ == "__main__":
    # 测试用例
    keyword = "error"
    server_name = "vehicle-owner-admin"
    start_time = "2025-12-03 00:00:00"
    end_time = "2025-12-03 23:59:59"
    business_line = "永策测试"
    private_server = ""
    page_no = 1

    result = search_logs.invoke(
        {
            "keyword": keyword,
            "server_name": server_name,
            "start_time": start_time,
            "end_time": end_time,
            "business_line": business_line,
            "private_server": private_server,
            "page_no": page_no,
        }
    )
    print(result)

"""LangChain 工具集

按功能分类组织的工具模块：
- discovery: 实体发现（模糊搜索）
- context: 上下文获取（根据 ID 查详情）
- impact: 影响面分析（反向查询使用情况）
- graph: 图拓扑（Neo4j 图遍历）
- code: 代码检索（MCP、文件操作、grep）
- log: 日志查询（企业日志 API）
- db: 数据库查询（SQL 查询）
"""

# 实体发现类工具
from .discovery import (
    search_businesses,
    search_implementations,
    search_data_resources,
    search_steps,
)

# 上下文获取类工具
from .context import (
    get_business_context,
    get_implementation_context,
    get_resource_context,
)

# 影响面分析类工具
from .impact import (
    get_implementation_business_usages,
    get_resource_business_usages,
)

# 图拓扑类工具
from .graph import (
    get_neighbors,
    get_path_between_entities,
)

# 代码检索类工具
from .code import (
    search_code_context,
    list_directory,
    read_file,
    read_file_range,
    grep_code,
)

# 日志查询类工具
from .log import (
    search_logs,
    LogQueryConfig,
    BusinessLine,
    LogServerName,
    PrivateServer,
)

# 数据库查询类工具
from .db import (
    get_table_schema,
    query_database,
    get_db_tools,
    DatabaseConfig,
)


# ============================================================
# 工具列表导出
# ============================================================

def get_all_chat_tools():
    """获取所有 Chat 工具列表（业务知识问答 Agent 使用）
    
    共 16 个工具：
    - 实体发现: 4 个
    - 上下文获取: 3 个
    - 影响面分析: 2 个
    - 图拓扑: 2 个
    - 代码检索: 5 个
    """
    return [
        # 实体发现
        search_businesses,
        search_implementations,
        search_data_resources,
        search_steps,
        # 上下文获取
        get_business_context,
        get_implementation_context,
        get_resource_context,
        # 影响面分析
        get_implementation_business_usages,
        get_resource_business_usages,
        # 图拓扑
        get_neighbors,
        get_path_between_entities,
        # 代码检索
        search_code_context,
        grep_code,
        list_directory,
        read_file,
        read_file_range,
    ]


def get_log_troubleshoot_tools():
    """获取日志排查 Agent 的工具集
    
    共 19 个工具：1 个日志工具 + 16 个业务知识工具 + 2 个数据库工具
    """
    return [search_logs] + get_all_chat_tools() + get_db_tools()


# 导出所有公开 API
__all__ = [
    # 工具函数
    "search_businesses",
    "search_implementations",
    "search_data_resources",
    "search_steps",
    "get_business_context",
    "get_implementation_context",
    "get_resource_context",
    "get_implementation_business_usages",
    "get_resource_business_usages",
    "get_neighbors",
    "get_path_between_entities",
    "search_code_context",
    "list_directory",
    "read_file",
    "read_file_range",
    "grep_code",
    "search_logs",
    "get_table_schema",
    "query_database",
    # 配置类
    "LogQueryConfig",
    "BusinessLine",
    "LogServerName",
    "PrivateServer",
    "DatabaseConfig",
    # 工厂函数
    "get_all_chat_tools",
    "get_log_troubleshoot_tools",
    "get_db_tools",
]

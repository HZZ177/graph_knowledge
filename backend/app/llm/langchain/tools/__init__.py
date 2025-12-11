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

# 永策Pro企业知识库检索工具
from .opdoc import (
    search_yongce_docs,
    get_opdoc_tools,
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
    """获取日志排查 Agent 的工具集（精简版）
    
    共 12 个工具：
    - 日志查询: 1 个 (search_logs)
    - 代码检索: 5 个 (search_code_context, grep_code, list_directory, read_file, read_file_range)
    - 业务理解: 4 个 (search_businesses, get_business_context, search_implementations, get_implementation_context)
    - 数据库查询: 2 个 (get_table_schema, query_database)
    
    对比完整版，移除的工具（日志排查场景低频/冗余）：
    - search_steps, search_data_resources, get_resource_context (业务细节工具)
    - get_implementation_business_usages, get_resource_business_usages (影响面分析)
    - get_neighbors, get_path_between_entities (图拓扑遍历)
    """
    return [
        # 日志查询
        search_logs,
        
        # 代码检索（完整保留）
        search_code_context,
        grep_code,
        list_directory,
        read_file,
        read_file_range,
        
        # 业务理解（保留核心）
        search_businesses,
        get_business_context,
        search_implementations,
        get_implementation_context,
        
        # 数据库查询
        get_table_schema,
        query_database,
    ]


def get_opdoc_qa_tools():
    """获取永策Pro智能助手 Agent 的工具集
    
    共 1 个工具：
    - 企业知识库检索: 1 个 (search_yongce_docs)
    """
    return get_opdoc_tools()


# 测试工具（transition_phase 已删除，阶段切换由编排器控制）
from .testing import (
    create_task_board,
    update_task_status,
    save_phase_summary,
    get_phase_summary,
    get_coding_issue_detail,
    get_all_testing_tools,
    get_testing_tools_phase1,
    get_testing_tools_phase2,
    get_testing_tools_phase3,
)


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
    "search_yongce_docs",  # 新增：永策Pro企业知识库检索
    # 测试工具（transition_phase 已删除）
    "create_task_board",
    "update_task_status",
    "save_phase_summary",
    "get_phase_summary",
    "get_coding_issue_detail",
    # 配置类
    "LogQueryConfig",
    "BusinessLine",
    "LogServerName",
    "PrivateServer",
    "DatabaseConfig",
    # 工厂函数
    "get_all_chat_tools",
    "get_log_troubleshoot_tools",
    "get_opdoc_qa_tools",  # 新增：操作文档工具集
    "get_opdoc_tools",  # 新增：操作文档工具集（别名）
    "get_db_tools",
    "get_all_testing_tools",
    "get_testing_tools_phase1",
    "get_testing_tools_phase2",
    "get_testing_tools_phase3",
]

"""数据库查询类工具

提供数据库查询能力：
- get_table_schema: 获取表的 DDL 结构定义
- query_database: 执行只读 SQL 查询（根据业务线自动选择数据库）
"""

import json
import re
from typing import Optional, List, Dict, Any, Annotated
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor
from langchain_core.tools import tool, InjectedToolArg
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from backend.app.db.sqlite import SessionLocal
from backend.app.models.resource_graph import DataResource
from backend.app.core.logger import logger
from backend.app.llm.langchain.tools.log import BusinessLine, PrivateServer


# ============================================================
# 数据库连接配置（待填充）
# ============================================================

class DatabaseConfig:
    """
    数据库连接配置
    OceanBase 使用 MySQL 协议连接
    
    业务线 → 数据库映射：
    - 一个集团使用一个数据库
    - 通过前端选择的业务线/私有化集团来确定连接哪个数据库
    """
    # OceanBase 连接配置
    OB_HOST = "61.171.117.80"
    OB_PORT = 12883
    OB_USER = "stc_parking@test#yongcepro_test"
    OB_PASSWORD = "Keytop@Yongce@123"
    
    # 数据库连接配置映射：database_key -> connection_config
    CONNECTIONS: Dict[str, Dict[str, Any]] = {
        # 永策测试环境
        "yongcepro_test": {
            "host": OB_HOST,
            "port": OB_PORT,
            "user": OB_USER,
            "password": OB_PASSWORD,
            "database": "yongcepro",
            "charset": "utf8mb4",
        },
        # 可添加更多数据库配置（其他集团/环境）
        # "renjule": {...},
        # "kuerle": {...},
    }
    
    # 业务线 → 数据库 key 映射
    # 与日志工具的 BusinessLine 枚举对应
    BUSINESS_LINE_DB_MAP: Dict[str, str] = {
        "永策测试": "yongcepro_test",
        # "永策C+路侧分区": "yongcepro_test",
        # 私有化集团映射（后续扩展）
        # "人居乐": "renjule",
        # "库尔勒": "kuerle",
    }
    
    # 查询限制
    MAX_ROWS = 100           # 单次查询最大返回行数
    QUERY_TIMEOUT = 30       # 查询超时时间（秒）
    MAX_JOIN_TABLES = 3      # 最大 JOIN 表数量
    
    # 敏感字段脱敏规则（正则模式 -> 脱敏 SQL 表达式）
    MASKING_RULES: Dict[str, str] = {
        r"phone|mobile|tel": "CONCAT(LEFT({col},3),'****',RIGHT({col},4))",
        r"id_card|identity|idcard": "CONCAT('**************',RIGHT({col},4))",
        r"email": "CONCAT(LEFT({col},3),'***',SUBSTRING({col},LOCATE('@',{col})))",
        r"password|secret|token|pwd": "'[REDACTED]'",
        r"bank_card|card_no|bankcard": "CONCAT('****',RIGHT({col},4))",
    }
    
    # 禁止访问的表（黑名单）
    BLOCKED_TABLES: List[str] = [
        "sys_user",
        "sys_password",
        "sys_secret",
        "payment_key",
    ]
    
    @classmethod
    def get_connection(cls, database: str) -> Optional[Dict[str, Any]]:
        """获取数据库连接配置"""
        return cls.CONNECTIONS.get(database)
    
    @classmethod
    def get_database_by_business_line(cls, business_line: str, private_server: str = None) -> Optional[str]:
        """
        根据业务线获取对应的数据库 key
        
        Args:
            business_line: 业务线名称（如 "永策测试"）
            private_server: 私有化集团名称（如 "人居乐"），仅当 business_line 为 "私有化" 时使用
            
        Returns:
            数据库 key（如 "yongcepro"），未找到返回 None
        """
        # 私有化场景：使用集团名称作为 key
        if business_line == "私有化" and private_server:
            return cls.BUSINESS_LINE_DB_MAP.get(private_server)
        
        return cls.BUSINESS_LINE_DB_MAP.get(business_line)
    
    @classmethod
    def get_available_databases(cls) -> List[str]:
        """获取所有可用的数据库名称"""
        return list(cls.CONNECTIONS.keys())


# ============================================================
# SQL 校验器
# ============================================================

class SQLValidator:
    """SQL 安全校验器"""
    
    # 只允许的 SQL 关键字（用于简单校验）
    ALLOWED_KEYWORDS = {'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'IN', 'NOT', 
                        'LIKE', 'BETWEEN', 'IS', 'NULL', 'ORDER', 'BY', 'ASC', 
                        'DESC', 'LIMIT', 'OFFSET', 'GROUP', 'HAVING', 'AS',
                        'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'ON',
                        'COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'DISTINCT'}
    
    # 禁止的 SQL 关键字
    BLOCKED_KEYWORDS = {'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
                        'TRUNCATE', 'REPLACE', 'GRANT', 'REVOKE', 'EXECUTE',
                        'CALL', 'INTO', 'SET', 'LOCK', 'UNLOCK'}
    
    @classmethod
    def validate(cls, sql: str, allowed_tables: List[str]) -> tuple[bool, str]:
        """
        校验 SQL 语句安全性
        
        Returns:
            (is_valid, error_message)
        """
        logger.debug(f"[SQLValidator] 开始校验 SQL, 长度={len(sql)}, 白名单表数={len(allowed_tables)}")
        sql_upper = sql.upper().strip()
        
        # 1. 必须以 SELECT 开头
        if not sql_upper.startswith('SELECT'):
            logger.warning(f"[SQLValidator] 校验失败: SQL 不是以 SELECT 开头, sql={sql[:100]}")
            return False, "仅允许 SELECT 查询语句"
        
        # 2. 检查禁止的关键字
        for keyword in cls.BLOCKED_KEYWORDS:
            # 使用单词边界匹配，避免误判
            pattern = r'\b' + keyword + r'\b'
            if re.search(pattern, sql_upper):
                logger.warning(f"[SQLValidator] 校验失败: 包含禁止关键字 {keyword}, sql={sql[:100]}")
                return False, f"禁止使用 {keyword} 语句"
        
        # 3. 检查是否包含注释（防止注入）
        if '--' in sql or '/*' in sql:
            logger.warning(f"[SQLValidator] 校验失败: SQL 包含注释, sql={sql[:100]}")
            return False, "SQL 中不允许包含注释"
        
        # 4. 检查分号（防止多语句注入）
        if ';' in sql.rstrip(';'):  # 允许末尾的分号
            logger.warning(f"[SQLValidator] 校验失败: SQL 包含多个分号, sql={sql[:100]}")
            return False, "SQL 中不允许包含多条语句"
        
        # 5. 提取涉及的表名并校验
        # 简单的表名提取（FROM/JOIN 后面的标识符）
        table_pattern = r'(?:FROM|JOIN)\s+`?(\w+)`?'
        tables_in_sql = re.findall(table_pattern, sql_upper)
        
        logger.debug(f"[SQLValidator] SQL 中涉及的表: {tables_in_sql}")
        
        for table in tables_in_sql:
            table_lower = table.lower()
            # 检查黑名单
            if table_lower in [t.lower() for t in DatabaseConfig.BLOCKED_TABLES]:
                logger.warning(f"[SQLValidator] 校验失败: 尝试访问黑名单表 {table}")
                return False, f"禁止访问表: {table}"
            # 检查白名单（如果提供）
            if allowed_tables and table_lower not in [t.lower() for t in allowed_tables]:
                logger.warning(f"[SQLValidator] 校验失败: 表 {table} 不在白名单中")
                return False, f"表 {table} 不在可查询范围内"
        
        # 6. 检查 JOIN 数量
        join_count = len(re.findall(r'\bJOIN\b', sql_upper))
        if join_count > DatabaseConfig.MAX_JOIN_TABLES:
            logger.warning(f"[SQLValidator] 校验失败: JOIN 数量 {join_count} 超过限制 {DatabaseConfig.MAX_JOIN_TABLES}")
            return False, f"JOIN 表数量超过限制（最多 {DatabaseConfig.MAX_JOIN_TABLES} 个）"
        
        logger.info(f"[SQLValidator] 校验通过, 涉及表={tables_in_sql}, JOIN数={join_count}")
        return True, ""
    
    @classmethod
    def ensure_limit(cls, sql: str, max_rows: int = None) -> str:
        """确保 SQL 包含 LIMIT 子句"""
        max_rows = max_rows or DatabaseConfig.MAX_ROWS
        sql_upper = sql.upper().strip().rstrip(';')
        
        # 检查是否已有 LIMIT
        limit_match = re.search(r'\bLIMIT\s+(\d+)', sql_upper)
        if limit_match:
            current_limit = int(limit_match.group(1))
            if current_limit > max_rows:
                logger.info(f"[SQLValidator] 调整 LIMIT: {current_limit} -> {max_rows}")
                # 替换为最大限制
                sql = re.sub(
                    r'\bLIMIT\s+\d+',
                    f'LIMIT {max_rows}',
                    sql,
                    flags=re.IGNORECASE
                )
            else:
                logger.debug(f"[SQLValidator] LIMIT 已存在且合规: {current_limit}")
        else:
            logger.info(f"[SQLValidator] 添加 LIMIT {max_rows}")
            # 添加 LIMIT
            sql = f"{sql.rstrip(';')} LIMIT {max_rows}"
        
        return sql


# ============================================================
# 数据库执行器
# ============================================================

class DatabaseExecutor:
    """数据库查询执行器"""
    
    @classmethod
    @contextmanager
    def get_connection(cls, database: str):
        """
        获取数据库连接（上下文管理器）
        
        使用方式:
            with DatabaseExecutor.get_connection('stc_parking') as conn:
                cursor = conn.cursor()
                ...
        """
        import time
        
        logger.info(f"[DatabaseExecutor] 准备连接数据库: database={database}")
        config = DatabaseConfig.get_connection(database)
        if not config:
            logger.error(f"[DatabaseExecutor] 数据库配置未找到: {database}")
            raise ValueError(f"数据库 {database} 未配置")
        
        conn = None
        start_time = time.time()
        try:
            logger.debug(f"[DatabaseExecutor] 连接参数: host={config['host']}, port={config['port']}, db={config['database']}")
            conn = pymysql.connect(
                host=config['host'],
                port=config['port'],
                user=config['user'],
                password=config['password'],
                database=config['database'],
                charset=config.get('charset', 'utf8mb4'),
                read_timeout=DatabaseConfig.QUERY_TIMEOUT,
                write_timeout=DatabaseConfig.QUERY_TIMEOUT,
                connect_timeout=10,
                cursorclass=DictCursor,
            )
            connect_time = time.time() - start_time
            logger.info(f"[DatabaseExecutor] 成功连接数据库: database={database}, 耗时={connect_time:.3f}s")
            yield conn
        except pymysql.Error as e:
            logger.error(f"[DatabaseExecutor] 连接数据库失败: database={database}, error={e}, error_code={e.args[0] if e.args else 'N/A'}")
            raise
        finally:
            if conn:
                conn.close()
                total_time = time.time() - start_time
                logger.debug(f"[DatabaseExecutor] 关闭数据库连接: database={database}, 总耗时={total_time:.3f}s")
    
    @classmethod
    def execute(cls, sql: str, database: str) -> List[Dict[str, Any]]:
        """
        执行 SQL 查询
        
        Args:
            sql: SELECT SQL 语句
            database: 数据库名称（对应 CONNECTIONS 中的 key）
            
        Returns:
            查询结果列表，每行为一个字典
        """
        import time
        
        logger.info(f"[DatabaseExecutor] 开始执行 SQL: database={database}")
        logger.debug(f"[DatabaseExecutor] SQL 内容: {sql}")
        
        with cls.get_connection(database) as conn:
            cursor = conn.cursor()
            exec_start = time.time()
            try:
                cursor.execute(sql)
                exec_time = time.time() - exec_start
                logger.info(f"[DatabaseExecutor] SQL 执行完成, 耗时={exec_time:.3f}s")
                
                fetch_start = time.time()
                results = cursor.fetchall()
                fetch_time = time.time() - fetch_start
                logger.info(f"[DatabaseExecutor] 数据获取完成: rows={len(results)}, 耗时={fetch_time:.3f}s")
                
                # 将结果转换为可序列化的格式
                serialize_start = time.time()
                serializable_results = []
                for idx, row in enumerate(results):
                    serializable_row = {}
                    for key, value in row.items():
                        # 处理特殊类型（日期、Decimal 等）
                        if hasattr(value, 'isoformat'):  # datetime/date
                            serializable_row[key] = value.isoformat()
                        elif hasattr(value, '__float__'):  # Decimal
                            serializable_row[key] = float(value)
                        elif isinstance(value, bytes):
                            serializable_row[key] = value.decode('utf-8', errors='replace')
                        else:
                            serializable_row[key] = value
                    serializable_results.append(serializable_row)
                
                serialize_time = time.time() - serialize_start
                total_time = time.time() - exec_start
                
                logger.info(
                    f"[DatabaseExecutor] 查询成功: database={database}, "
                    f"rows={len(serializable_results)}, "
                    f"总耗时={total_time:.3f}s ("
                    f"执行={exec_time:.3f}s, "
                    f"获取={fetch_time:.3f}s, "
                    f"序列化={serialize_time:.3f}s)"
                )
                
                # 记录结果样例（仅debug级别）
                if serializable_results:
                    logger.debug(f"[DatabaseExecutor] 结果样例（第1行）: {serializable_results[0]}")
                
                return serializable_results
                
            except pymysql.Error as e:
                logger.error(
                    f"[DatabaseExecutor] SQL 执行失败: "
                    f"error={e}, "
                    f"error_code={e.args[0] if e.args else 'N/A'}, "
                    f"sql={sql[:200]}"
                )
                raise
            finally:
                cursor.close()


# ============================================================
# get_table_schema
# ============================================================

class GetTableSchemaInput(BaseModel):
    """get_table_schema 工具输入参数"""
    table_name: str = Field(
        ...,
        description="表名称，如 t_user_card, t_order_info。必须是明确的表名。"
    )


@tool(args_schema=GetTableSchemaInput)
def get_table_schema(table_name: str) -> str:
    """获取指定表的 DDL 结构定义。
    
    返回表的 CREATE TABLE 语句，包含字段名、类型、注释等信息。
    在构造 SQL 查询前必须先调用此工具了解表结构。
    
    注意：只有在明确知道要查询的表名时才调用此工具。
    """
    logger.info(f"[get_table_schema] 开始查询表结构: table_name={table_name}")
    
    try:
        db = SessionLocal()
        try:
            # 精确匹配表名
            logger.debug(f"[get_table_schema] 查询数据资源表: table_name={table_name}")
            resource = db.query(DataResource).filter(DataResource.name == table_name).first()
            
            if not resource:
                logger.warning(f"[get_table_schema] 未找到表: table_name={table_name}, 尝试模糊匹配")
                # 尝试模糊匹配给出建议
                fuzzy_results = db.query(DataResource).filter(
                    DataResource.name.ilike(f'%{table_name}%')
                ).limit(5).all()
                
                suggestions = [r.name for r in fuzzy_results]
                logger.info(f"[get_table_schema] 模糊匹配结果: {suggestions}")
                
                return json.dumps({
                    "error": f"未找到表 {table_name}，该表可能尚未在系统中注册",
                    "suggestions": suggestions if suggestions else None,
                    "hint": "请确认表名是否正确，或联系管理员添加表结构信息"
                }, ensure_ascii=False)
            
            logger.info(f"[get_table_schema] 找到表: name={resource.name}, system={resource.system}, type={resource.type}")
            
            # 构建返回结果
            result = {
                "table_name": resource.name,
                "description": resource.description,
            }
            
            if resource.ddl:
                logger.debug(f"[get_table_schema] DDL 长度: {len(resource.ddl)} 字符")
                result["ddl"] = resource.ddl
                # 尝试从 DDL 中解析字段列表（简化展示）
                columns = _parse_columns_from_ddl(resource.ddl)
                if columns:
                    logger.info(f"[get_table_schema] 解析到 {len(columns)} 个字段")
                    result["columns"] = columns
                else:
                    logger.warning(f"[get_table_schema] DDL 解析失败，未提取到字段")
            else:
                logger.warning(f"[get_table_schema] 表 {table_name} 没有 DDL 信息")
                result["ddl"] = None
                result["warning"] = "该表尚未配置 DDL 结构定义，无法进行数据查询。请先在数据资源中补充表结构信息。"
            
            logger.info(f"[get_table_schema] 返回结果: table={resource.name}, has_ddl={bool(resource.ddl)}, col_count={len(result.get('columns', []))}")
            return json.dumps(result, ensure_ascii=False)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"[get_table_schema] 查询失败: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def _parse_columns_from_ddl(ddl: str) -> List[Dict[str, str]]:
    """
    从 DDL 中解析字段列表（简化实现）
    
    示例 DDL:
    CREATE TABLE t_user (
        id BIGINT PRIMARY KEY COMMENT '用户ID',
        name VARCHAR(100) NOT NULL COMMENT '用户名',
        phone VARCHAR(20) COMMENT '手机号'
    );
    """
    columns = []
    try:
        # 匹配字段定义行
        # 格式: field_name TYPE [constraints] [COMMENT 'xxx']
        pattern = r'^\s*`?(\w+)`?\s+(\w+(?:\([^)]+\))?)[^,\n]*?(?:COMMENT\s+[\'"]([^\'"]*)[\'"])?'
        
        lines = ddl.split('\n')
        for line in lines:
            line = line.strip()
            # 跳过 CREATE TABLE 行和括号行
            if line.upper().startswith('CREATE') or line in ('(', ')', ');'):
                continue
            # 跳过索引和约束定义
            if any(kw in line.upper() for kw in ['PRIMARY KEY', 'INDEX', 'KEY ', 'CONSTRAINT', 'UNIQUE']):
                if not line.strip().startswith('`'):  # 不是字段定义
                    continue
            
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                col_name = match.group(1)
                col_type = match.group(2)
                col_comment = match.group(3) or ""
                
                # 标记敏感字段
                is_sensitive = any(
                    re.search(pat, col_name, re.IGNORECASE)
                    for pat in DatabaseConfig.MASKING_RULES.keys()
                )
                
                columns.append({
                    "name": col_name,
                    "type": col_type,
                    "comment": col_comment,
                    "sensitive": is_sensitive
                })
    except Exception as e:
        logger.warning(f"[_parse_columns_from_ddl] 解析失败: {e}")
    
    return columns


# ============================================================
# query_database
# ============================================================

class QueryDatabaseInput(BaseModel):
    """query_database 工具输入参数"""
    sql: str = Field(
        ...,
        description="SELECT SQL 查询语句。仅支持 SELECT，禁止 INSERT/UPDATE/DELETE 等"
    )
    reason: str = Field(
        ...,
        description="查询目的说明，用于审计日志"
    )


@tool(args_schema=QueryDatabaseInput)
def query_database(
    sql: str,
    reason: str,
    config: Annotated[RunnableConfig, InjectedToolArg] = None,
) -> str:
    """在业务数据库执行只读 SQL 查询。
    
    使用前请先调用 get_table_schema 了解表结构，确保 SQL 语句正确。
    数据库连接由系统根据当前业务线自动选择。
    
    限制：
    - 仅支持 SELECT 语句
    - 单次返回最多 100 行
    - 敏感字段（手机号、身份证等）自动脱敏
    - 禁止访问系统敏感表
    """
    logger.info(f"[query_database] ========== 开始执行数据库查询 ==========")
    logger.info(f"[query_database] 查询目的: {reason}")
    logger.debug(f"[query_database] SQL 预览: {sql[:200]}..." if len(sql) > 200 else f"[query_database] SQL: {sql}")
    
    # 1. 从 config.metadata 获取用户在 UI 选择的业务线配置
    if not config:
        logger.error(f"[query_database] 缺少运行时配置")
        return json.dumps({"error": "系统错误：缺少运行时配置"}, ensure_ascii=False)
    
    try:
        logger.debug(f"[query_database] 解析业务线配置")
        metadata = config.get("metadata", {}) or {}
        log_query = metadata.get("agent_context", {}).get("log_query", {})
        business_line = log_query.get("businessLine")
        private_server = log_query.get("privateServer")
        
        logger.info(f"[query_database] 业务线配置: business_line={business_line}, private_server={private_server}")
        
        if not business_line:
            logger.warning(f"[query_database] 未选择业务线")
            return json.dumps({
                "error": "请在界面左上角选择业务线配置",
                "hint": "数据库查询需要根据业务线确定连接哪个数据库"
            }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[query_database] 获取业务线配置失败: {e}", exc_info=True)
        return json.dumps({"error": f"获取业务线配置失败: {e}"}, ensure_ascii=False)
    
    # 2. 根据业务线获取数据库 key
    logger.debug(f"[query_database] 根据业务线获取数据库: {business_line}")
    database = DatabaseConfig.get_database_by_business_line(business_line, private_server)
    if not database:
        logger.error(f"[query_database] 业务线 '{business_line}' 未配置数据库")
        return json.dumps({
            "error": f"业务线 '{business_line}' 暂未配置数据库连接",
            "hint": "请联系管理员配置该业务线的数据库连接"
        }, ensure_ascii=False)
    
    logger.info(f"[query_database] 确定数据库: business_line={business_line}, database={database}")
    
    try:
        # 3. 获取所有已注册的表作为白名单（不再按 system 过滤，因为是同一个库）
        logger.debug(f"[query_database] 加载表白名单")
        db = SessionLocal()
        try:
            allowed_tables = [
                r.name for r in db.query(DataResource.name)
                .filter(DataResource.type == 'table')
                .all()
            ]
            logger.info(f"[query_database] 白名单表数量: {len(allowed_tables)}")
        finally:
            db.close()
        
        # 4. SQL 安全校验
        logger.info(f"[query_database] 开始 SQL 安全校验")
        is_valid, error_msg = SQLValidator.validate(sql, allowed_tables)
        if not is_valid:
            logger.warning(f"[query_database] SQL 校验失败: {error_msg}")
            return json.dumps({
                "error": "SQL 校验失败",
                "detail": error_msg,
                "sql": sql
            }, ensure_ascii=False)
        
        # 5. 确保 LIMIT 限制
        logger.debug(f"[query_database] 检查 LIMIT 子句")
        sql = SQLValidator.ensure_limit(sql)
        
        # 6. 检查数据库连接配置
        if not DatabaseConfig.get_connection(database):
            logger.error(f"[query_database] 数据库 {database} 未配置连接")
            return json.dumps({
                "error": f"数据库 {database} 未配置连接",
                "hint": "请在 DatabaseConfig.CONNECTIONS 中添加数据库连接配置"
            }, ensure_ascii=False)
        
        # 7. 记录审计日志
        logger.info(f"[query_database] 审计: reason='{reason}', business_line={business_line}, database={database}")
        logger.info(f"[query_database] 执行 SQL: {sql}")
        
        # 8. 执行查询
        try:
            results = DatabaseExecutor.execute(sql, database)
            
            logger.info(
                f"[query_database] 查询成功: "
                f"business_line={business_line}, "
                f"database={database}, "
                f"rows={len(results)}"
            )
            logger.info(f"[query_database] ========== 查询完成 ==========")
            
            return json.dumps({
                "business_line": business_line,
                "database": database,
                "sql": sql,
                "row_count": len(results),
                "data": results
            }, ensure_ascii=False)
            
        except pymysql.Error as e:
            logger.error(f"[query_database] 数据库执行失败: {e}", exc_info=True)
            return json.dumps({
                "error": "数据库查询执行失败",
                "detail": str(e),
                "sql": sql
            }, ensure_ascii=False)
            
    except Exception as e:
        logger.error(f"[query_database] 执行失败: {e}", exc_info=True)
        logger.error(f"[query_database] ========== 查询失败 ==========")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============================================================
# 导出
# ============================================================

# 数据库查询工具列表
DB_TOOLS = [
    get_table_schema,
    query_database,
]


def get_db_tools():
    """获取所有数据库查询工具"""
    return DB_TOOLS

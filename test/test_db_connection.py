"""测试数据库工具

数据流说明：
1. get_table_schema → 查询本地 SQLite (app.db) 中的 DataResource.ddl
2. query_database → 
   - 从 agent_context 获取业务线 → 映射到数据库
   - 连接 OceanBase 执行实际 SQL 查询
"""

import os
import sys

# 切换到项目根目录（app.db 在 backend/app 目录下）
PROJECT_ROOT = r'c:\Users\86364\PycharmProjects\graph_knowledge'
BACKEND_DIR = os.path.join(PROJECT_ROOT, 'backend')
os.chdir(BACKEND_DIR)

sys.path.insert(0, PROJECT_ROOT)

from backend.app.db.sqlite import SessionLocal, engine
from backend.app.models.resource_graph import DataResource
from backend.app.llm.langchain.tools.db import (
    DatabaseConfig,
    DatabaseExecutor,
    get_table_schema,
    query_database,
)

# 打印数据库路径信息
print(f"当前工作目录: {os.getcwd()}")
print(f"SQLite URL: {engine.url}")


def test_sqlite_metadata():
    """测试 1: 查询本地 SQLite 元数据"""
    print("=" * 60)
    print("测试 1: SQLite 元数据 (DataResource 表)")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # 查询所有数据资源
        total = db.query(DataResource).count()
        resources = db.query(DataResource).limit(10).all()
        print(f"\n本地 DataResource 表中的记录 (共 {total} 条):")
        
        if not resources:
            print("  ⚠️ 暂无数据资源，请先在前端添加")
            return []
        
        for r in resources:
            ddl_status = "✅有DDL" if r.ddl else "❌无DDL"
            print(f"  - {r.name} (类型: {r.type}) [{ddl_status}]")
        
        # 返回有 DDL 的表名列表
        tables_with_ddl = [r.name for r in db.query(DataResource).filter(DataResource.ddl.isnot(None)).all()]
        print(f"\n有 DDL 定义的表: {tables_with_ddl[:5]}{'...' if len(tables_with_ddl) > 5 else ''}")
        return tables_with_ddl
        
    finally:
        db.close()


def test_oceanbase_connection():
    """测试 2: 测试 OceanBase 连接"""
    print("\n" + "=" * 60)
    print("测试 2: OceanBase 数据库连接")
    print("=" * 60)
    
    database = "yongcepro_test"
    config = DatabaseConfig.get_connection(database)
    
    if not config:
        print(f"\n❌ 未找到 {database} 的连接配置")
        return False
    
    print(f"\n配置信息:")
    print(f"  Host: {config['host']}:{config['port']}")
    print(f"  User: {config['user']}")
    print(f"  Database: {config['database']}")
    
    try:
        with DatabaseExecutor.get_connection(database) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 AS test")
            result = cursor.fetchone()
            print(f"\n✅ OceanBase 连接成功! 测试结果: {result}")
            
            # 查询 OB 中的表
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            print(f"\nOceanBase 中的表 (前10个):")
            for i, table in enumerate(tables[:10]):
                print(f"  {i+1}. {list(table.values())[0]}")
            if len(tables) > 10:
                print(f"  ... 共 {len(tables)} 张表")
                
            return True
                
    except Exception as e:
        print(f"\n❌ OceanBase 连接失败: {e}")
        return False


def test_business_line_mapping():
    """测试 3: 业务线 → 数据库映射"""
    print("\n" + "=" * 60)
    print("测试 3: 业务线映射")
    print("=" * 60)
    
    test_cases = [
        ("永策测试", None),
        ("永策C+路侧分区", None),
        ("私有化", "人居乐"),
        ("未知业务线", None),
    ]
    
    for business_line, private_server in test_cases:
        db = DatabaseConfig.get_database_by_business_line(business_line, private_server)
        status = "✅" if db else "❌"
        print(f"  {status} {business_line}" + (f" ({private_server})" if private_server else "") + f" → {db or '未配置'}")


def test_get_table_schema(table_name: str = None):
    """测试 4: get_table_schema 工具"""
    print("\n" + "=" * 60)
    print("测试 4: get_table_schema 工具")
    print("=" * 60)
    
    if not table_name:
        # 获取一个有 DDL 的表
        db = SessionLocal()
        try:
            sample = db.query(DataResource).filter(DataResource.ddl.isnot(None)).first()
            if sample:
                table_name = sample.name
            else:
                print("  ⚠️ 暂无有 DDL 的表，请先在前端添加")
                return
        finally:
            db.close()
    
    print(f"\n查询表: {table_name}")
    result = get_table_schema.invoke({"table_name": table_name})
    print(result[:1000] + "..." if len(result) > 1000 else result)


def test_query_database_direct():
    """测试 5: 直接执行 SQL（绕过工具，测试执行器）"""
    print("\n" + "=" * 60)
    print("测试 5: 直接执行 SQL (DatabaseExecutor)")
    print("=" * 60)
    
    database = "yongcepro_test"
    sql = "SELECT 1 AS test_value, NOW() AS now_time"
    
    print(f"\n执行: {sql}")
    try:
        results = DatabaseExecutor.execute(sql, database)
        print(f"✅ 结果: {results}")
    except Exception as e:
        print(f"❌ 执行失败: {e}")


def test_query_database_tool():
    """测试 6: query_database 工具（需要模拟 config）"""
    print("\n" + "=" * 60)
    print("测试 6: query_database 工具 (模拟 agent_context)")
    print("=" * 60)
    
    # 模拟前端传入的 config
    mock_config = {
        "metadata": {
            "agent_context": {
                "log_query": {
                    "businessLine": "永策测试",
                    "privateServer": None
                }
            }
        }
    }
    
    print(f"\n模拟业务线: 永策测试")
    result = query_database.invoke(
        {
            "sql": "SELECT 1 AS test_value, NOW() AS now_time",
            "reason": "测试连接"
        },
        config=mock_config
    )
    print(result)


if __name__ == "__main__":
    # 1. 检查 SQLite 元数据
    tables_with_ddl = test_sqlite_metadata()
    
    # 2. 测试 OB 连接
    ob_ok = test_oceanbase_connection()
    
    # 3. 测试业务线映射
    test_business_line_mapping()
    
    # 4. 测试 get_table_schema
    if tables_with_ddl:
        test_get_table_schema(tables_with_ddl[0])
    else:
        test_get_table_schema("t_test")  # 测试不存在的表
    
    # 5. 直接执行 SQL
    if ob_ok:
        test_query_database_direct()
    
    # 6. 测试 query_database 工具
    if ob_ok:
        test_query_database_tool()

"""
Neo4j数据库强制清空脚本（无需确认）

功能：直接清空所有数据，无需确认

使用方法：
    python clear_neo4j_force.py

警告：此操作不可逆！
"""

from neo4j import GraphDatabase
from backend.app.db.neo4j_client import (
    DEFAULT_NEO4J_URI,
    DEFAULT_NEO4J_USER,
    DEFAULT_NEO4J_PASSWORD,
    DEFAULT_NEO4J_DATABASE,
)


def force_clear_neo4j():
    """强制清空Neo4j数据库（无需确认）"""
    
    print("🗑️  强制清空Neo4j数据库...")
    
    driver = None
    try:
        driver = GraphDatabase.driver(
            DEFAULT_NEO4J_URI,
            auth=(DEFAULT_NEO4J_USER, DEFAULT_NEO4J_PASSWORD),
        )
        
        with driver.session(database=DEFAULT_NEO4J_DATABASE) as session:
            # 删除所有节点和关系
            print("   删除所有节点和关系...")
            session.run("MATCH (n) DETACH DELETE n")
            
            # 删除所有约束
            print("   删除所有约束...")
            result = session.run("SHOW CONSTRAINTS")
            for constraint in result:
                name = constraint.get("name")
                if name:
                    try:
                        session.run(f"DROP CONSTRAINT {name}")
                    except:
                        pass
            
            # 删除所有索引
            print("   删除所有索引...")
            result = session.run("SHOW INDEXES")
            for index in result:
                name = index.get("name")
                index_type = index.get("type", "")
                if name and "CONSTRAINT" not in index_type.upper():
                    try:
                        session.run(f"DROP INDEX {name}")
                    except:
                        pass
            
            print("✅ 清空完成！")
        
    except Exception as e:
        print(f"❌ 错误：{e}")
        
    finally:
        if driver:
            driver.close()


if __name__ == "__main__":
    force_clear_neo4j()

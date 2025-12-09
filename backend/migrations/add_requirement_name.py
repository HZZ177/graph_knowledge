"""
迁移脚本：为 conversations 表添加 requirement_name 列
运行方式：python -m backend.migrations.add_requirement_name
"""
import sqlite3
import os

def migrate():
    # 数据库路径
    db_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'app.db')
    db_path = os.path.abspath(db_path)
    
    print(f"数据库路径: {db_path}")
    
    if not os.path.exists(db_path):
        print("数据库文件不存在，跳过迁移")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查列是否已存在
        cursor.execute("PRAGMA table_info(conversations)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'requirement_name' in columns:
            print("列 requirement_name 已存在，跳过")
        else:
            # 添加列
            cursor.execute("ALTER TABLE conversations ADD COLUMN requirement_name TEXT")
            conn.commit()
            print("成功添加列 requirement_name")
        
    except Exception as e:
        print(f"迁移失败: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()

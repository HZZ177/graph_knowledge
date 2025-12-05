"""
数据库表DDL导出脚本
自动导出指定前缀的表到JSON文件，用于导入到知识图谱系统
"""
import pymysql
import json
import sys

# 数据库配置
DB_CONFIG = {
    'host': '61.171.117.80',
    'port': 12883,
    'user': 'stc_parking@test#yongcepro_test',
    'password': 'Keytop@Yongce@123',
    'database': 'yongcepro',
    'charset': 'utf8mb4'
}

# 导出配置
TABLE_PREFIX = 't_cm%'  # 表名前缀，支持通配符
DEFAULT_SYSTEM = 'C端'  # 默认系统名称
OUTPUT_FILE = '../database_tables.json'  # 输出文件名


def export_tables():
    """导出数据库表到JSON文件"""
    try:
        print(f"正在连接数据库 {DB_CONFIG['host']}:{DB_CONFIG['port']}...")
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 查询所有匹配的表
        print(f"正在查询前缀为 '{TABLE_PREFIX}' 的表...")
        cursor.execute("""
            SELECT TABLE_NAME, TABLE_COMMENT, TABLE_SCHEMA
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME LIKE %s
              AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
        """, (DB_CONFIG['database'], TABLE_PREFIX))
        
        tables = cursor.fetchall()
        
        if not tables:
            print(f"未找到匹配的表（前缀: {TABLE_PREFIX}）")
            return
        
        print(f"找到 {len(tables)} 张表，开始导出...")
        result = []
        
        for idx, (table_name, table_comment, table_schema) in enumerate(tables, 1):
            try:
                # 获取DDL
                cursor.execute(f"SHOW CREATE TABLE `{table_name}`")
                ddl_row = cursor.fetchone()
                ddl = ddl_row[1] if ddl_row else ''
                
                # 构建数据
                table_data = {
                    'name': table_name,
                    'type': 'table',
                    'system': DEFAULT_SYSTEM,
                    'location': f'{table_schema}.{table_name}',
                    'description': table_comment or '',
                    'ddl': ddl
                }
                result.append(table_data)
                
                print(f"  [{idx}/{len(tables)}] {table_name} - {table_comment or '无描述'}")
                
            except Exception as e:
                print(f"  ⚠️  [{idx}/{len(tables)}] {table_name} 导出失败: {e}")
                continue
        
        # 保存为JSON
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        cursor.close()
        conn.close()
        
        print(f"\n✅ 成功导出 {len(result)} 张表到 {OUTPUT_FILE}")
        print(f"📁 文件路径: {OUTPUT_FILE}")
        print(f"\n下一步：在系统的「数据资源」页面点击「导入」按钮，上传此JSON文件")
        
    except pymysql.err.OperationalError as e:
        print(f"❌ 数据库连接失败: {e}")
        print("请检查：")
        print("  1. 数据库地址和端口是否正确")
        print("  2. 用户名和密码是否正确")
        print("  3. 数据库名称是否正确")
        print("  4. 网络是否可达")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    print("=" * 60)
    print("数据库表DDL导出工具")
    print("=" * 60)
    print(f"数据库: {DB_CONFIG['database']}")
    print(f"表前缀: {TABLE_PREFIX}")
    print(f"输出文件: {OUTPUT_FILE}")
    print("=" * 60)
    print()
    
    export_tables()

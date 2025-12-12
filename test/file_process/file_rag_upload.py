"""
批量文档导入 LightRAG 脚本

功能：
1. 遍历 docs 目录下的所有 Markdown 文件
2. 依次调用 lightrag_demo 的上传方法进行索引
3. 单个文件失败不影响后续处理
4. 统计成功/失败数量并输出报告

使用方法：
    python test/file_process/file_rag_upload.py

注意：
    - 这是一个非常耗时的操作，可能需要数小时
    - 建议在稳定网络环境下运行
    - 进度会实时显示，可以随时 Ctrl+C 中断
"""

import sys
import time
import asyncio
import logging
from pathlib import Path
from datetime import datetime

# ============== 项目路径设置 ==============
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 导入 lightrag_demo 中的 LightRAGDemo 类
from test.lightrag_demo import LightRAGDemo

# ============== 日志配置（与 lightrag_demo 保持一致）==============

# 当前处理文档的上下文（用于日志前缀）
class DocContext:
    current_index = 0
    current_name = ""
    total_count = 0

class DocPrefixFilter(logging.Filter):
    """为每条日志添加当前文档序号和名称前缀"""
    def filter(self, record):
        if DocContext.current_name:
            record.msg = f"[{DocContext.current_index}/{DocContext.total_count}|{DocContext.current_name}] {record.msg}"
        return True

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)

# 为根 logger 添加文档前缀过滤器
for handler in logging.root.handlers:
    handler.addFilter(DocPrefixFilter())

# LightRAG 核心日志
logging.getLogger("lightrag").setLevel(logging.DEBUG)
# HTTP 请求日志 (可以看到 embedding 调用)
logging.getLogger("httpx").setLevel(logging.DEBUG)
logging.getLogger("openai").setLevel(logging.DEBUG)
# 降低其他噪音
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("neo4j").setLevel(logging.INFO)

# ============== 配置 ==============

# 文档目录
DOCS_DIR = PROJECT_ROOT / "docs"

# 处理限制（调试用）
LIMIT = None  # 设置为数字限制处理数量，None 表示处理全部
SKIP_FIRST = 0  # 跳过前 N 个文件（用于断点续传）


# ============== 主流程 ==============

def get_doc_files() -> list[Path]:
    """获取所有待处理的文档文件"""
    if not DOCS_DIR.exists():
        print(f"❌ 文档目录不存在: {DOCS_DIR}")
        return []
    
    # 获取所有 .md 文件
    files = sorted(DOCS_DIR.glob("*.md"))
    
    # 应用跳过和限制
    if SKIP_FIRST > 0:
        files = files[SKIP_FIRST:]
    if LIMIT:
        files = files[:LIMIT]
    
    return files


def format_duration(seconds: float) -> str:
    """格式化时间"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


async def main():
    print("=" * 70)
    print("   📚 批量文档导入 LightRAG")
    print("=" * 70)
    
    # 获取文件列表
    files = get_doc_files()
    if not files:
        print("没有需要处理的文档")
        return
    
    print(f"\n📂 文档目录: {DOCS_DIR}")
    print(f"📄 待处理文档: {len(files)} 个")
    if SKIP_FIRST > 0:
        print(f"⏭️  跳过前 {SKIP_FIRST} 个文件")
    if LIMIT:
        print(f"🔢 限制处理 {LIMIT} 个文件")
    
    # 初始化 LightRAGDemo（复用 lightrag_demo 的类）
    demo = LightRAGDemo()
    
    try:
        await demo.initialize()
    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        return
    
    # 统计
    results = {
        "success": [],
        "failed": [],
        "total_time": 0,
    }
    
    total_start = time.time()
    
    print("\n" + "=" * 70)
    print("开始处理...")
    print("=" * 70)
    
    # 设置文档总数
    DocContext.total_count = len(files)
    
    try:
        for i, file_path in enumerate(files, 1):
            file_name = file_path.name
            
            # 更新当前文档上下文（用于日志前缀）
            DocContext.current_index = i
            DocContext.current_name = file_name
            
            # 显示进度
            print(f"\n[{i}/{len(files)}] 📄 {file_name}")
            
            # 处理文档（调用 demo 的 insert_document 方法）
            start_time = time.time()
            try:
                success = await demo.insert_document(str(file_path))
                elapsed = time.time() - start_time
                error = ""
            except Exception as e:
                success = False
                elapsed = time.time() - start_time
                error = str(e)
            
            if success:
                results["success"].append({
                    "file": file_name,
                    "time": elapsed,
                })
            else:
                results["failed"].append({
                    "file": file_name,
                    "error": error or "insert_document 返回 False",
                    "time": elapsed,
                })
                print(f"   ❌ 失败: {(error or 'insert_document 返回 False')[:100]}")
            
            results["total_time"] += elapsed
            
            # 显示累计统计
            success_count = len(results["success"])
            fail_count = len(results["failed"])
            avg_time = results["total_time"] / i
            remaining = (len(files) - i) * avg_time
            
            print(f"   📊 进度: {success_count}✓ {fail_count}✗ | "
                  f"平均: {format_duration(avg_time)} | "
                  f"预计剩余: {format_duration(remaining)}")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断处理")
    
    finally:
        await demo.close()
    
    # 输出报告
    total_elapsed = time.time() - total_start
    
    print("\n" + "=" * 70)
    print("   📊 处理报告")
    print("=" * 70)
    
    print(f"\n⏱️  总耗时: {format_duration(total_elapsed)}")
    print(f"✅ 成功: {len(results['success'])} 个")
    print(f"❌ 失败: {len(results['failed'])} 个")
    
    if results["success"]:
        avg_success_time = sum(r["time"] for r in results["success"]) / len(results["success"])
        print(f"📈 平均处理时间: {format_duration(avg_success_time)}")
    
    # 输出失败列表
    if results["failed"]:
        print("\n❌ 失败文件列表:")
        print("-" * 50)
        for item in results["failed"]:
            print(f"   • {item['file']}")
            print(f"     错误: {item['error'][:80]}")
        
        # 保存失败列表到文件
        fail_log_path = PROJECT_ROOT / "test" / "file_process" / "failed_files.txt"
        with open(fail_log_path, "w", encoding="utf-8") as f:
            f.write(f"# 失败文件列表 - {datetime.now().isoformat()}\n\n")
            for item in results["failed"]:
                f.write(f"文件: {item['file']}\n")
                f.write(f"错误: {item['error']}\n\n")
        print(f"\n📝 失败列表已保存到: {fail_log_path}")
    
    # 输出成功列表
    if results["success"]:
        success_log_path = PROJECT_ROOT / "test" / "file_process" / "success_files.txt"
        with open(success_log_path, "w", encoding="utf-8") as f:
            f.write(f"# 成功文件列表 - {datetime.now().isoformat()}\n\n")
            for item in results["success"]:
                f.write(f"{item['file']} ({format_duration(item['time'])})\n")
        print(f"📝 成功列表已保存到: {success_log_path}")
    
    print("\n" + "=" * 70)
    print("处理完成!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

"""
LightRAG 最小架构测试脚本

功能：
1. 手动选择 PDF/TXT/MD 文档
2. 导入到 LightRAG (向量库 + Neo4j 图谱)
3. 显示导入进度
4. 控制台对话测试

使用方法：
    pip install lightrag-hku[neo4j] pymupdf
    python test/lightrag_demo.py
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import Optional

# 添加项目根目录到 path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ============== 日志配置 ==============
# 设置 LightRAG 详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
# LightRAG 核心日志
logging.getLogger("lightrag").setLevel(logging.DEBUG)
# HTTP 请求日志 (可以看到 embedding 调用)
logging.getLogger("httpx").setLevel(logging.DEBUG)
logging.getLogger("openai").setLevel(logging.DEBUG)
# 降低其他噪音
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("neo4j").setLevel(logging.INFO)

# ============== 配置 (硬编码，测试阶段) ==============

# Neo4j 配置 (复用现有)
NEO4J_URI = "neo4j+s://c6010ae0.databases.neo4j.io"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "GMaCBUonUoHZCYcqa8mBho_FAjVBnykTlEdgpMKLdZU"

# LightRAG 配置
LIGHTRAG_WORKING_DIR = str(PROJECT_ROOT / "test" / "lightrag_data")
LIGHTRAG_WORKSPACE = "opdoc"  # Neo4j 数据隔离前缀

# LLM 配置 (对话模型)
LLM_API_KEY = "sk-z7HUcbUoz6yVKBnEPrMiXnrljTmzmRNpHBL224MqgFoOxoux"  # 替换为你的 API Key
LLM_BASE_URL = "https://88996.cloud/v1"  # 或你的网关地址
LLM_MODEL = "gemini-2.5-flash"

# Embedding 配置 (向量模型) - 单独配置
EMBEDDING_API_KEY = "sk-vxyvdnryevgolxatlsqilklzpiyfadxpkkqpvsagrgvuzavi"  # Embedding 服务的 API Key
EMBEDDING_BASE_URL = "https://api.siliconflow.cn/v1"  # Embedding 服务地址
EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-8B"
EMBEDDING_DIM = 4096  # 向量维度，需与模型匹配

# ============== 工具函数 ==============

def extract_text_from_pdf(pdf_path: str) -> str:
    """从 PDF 提取文本"""
    try:
        import fitz  # pymupdf
        doc = fitz.open(pdf_path)
        text = ""
        for page_num, page in enumerate(doc):
            text += f"\n--- Page {page_num + 1} ---\n"
            text += page.get_text()
        doc.close()
        return text
    except ImportError:
        print("⚠️  pymupdf 未安装，请运行: pip install pymupdf")
        return ""

def extract_text_from_file(file_path: str) -> str:
    """从文件提取文本"""
    path = Path(file_path)
    suffix = path.suffix.lower()
    
    if suffix == ".pdf":
        return extract_text_from_pdf(file_path)
    elif suffix in [".txt", ".md", ".markdown"]:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        print(f"⚠️  不支持的文件格式: {suffix}")
        return ""

def select_file() -> Optional[str]:
    """选择文件 (支持拖拽或输入路径)"""
    print("\n" + "=" * 50)
    print("📂 请输入文档路径 (支持 PDF/TXT/MD)")
    print("   或将文件拖拽到此窗口")
    print("=" * 50)
    
    file_path = input("\n文件路径: ").strip().strip('"').strip("'")
    
    if not file_path:
        return None
    
    if not Path(file_path).exists():
        print(f"❌ 文件不存在: {file_path}")
        return None
    
    return file_path

# ============== LightRAG 封装 ==============

class LightRAGDemo:
    def __init__(self):
        self.rag = None
        self._setup_env()
    
    def _setup_env(self):
        """设置环境变量"""
        os.environ["NEO4J_URI"] = NEO4J_URI
        os.environ["NEO4J_USERNAME"] = NEO4J_USERNAME
        os.environ["NEO4J_PASSWORD"] = NEO4J_PASSWORD
        os.environ["OPENAI_API_KEY"] = LLM_API_KEY
        
        # 确保工作目录存在
        os.makedirs(LIGHTRAG_WORKING_DIR, exist_ok=True)
    
    async def initialize(self):
        """初始化 LightRAG"""
        print("\n🚀 正在初始化 LightRAG...")
        
        try:
            from lightrag import LightRAG
            from lightrag.llm.openai import openai_complete_if_cache, openai_embed
            from lightrag.utils import EmbeddingFunc
            from lightrag.kg.shared_storage import initialize_pipeline_status
            import numpy as np
            
            # 自定义 LLM 函数
            async def llm_func(prompt, system_prompt=None, history_messages=[], **kwargs):
                return await openai_complete_if_cache(
                    model=LLM_MODEL,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    history_messages=history_messages,
                    api_key=LLM_API_KEY,
                    base_url=LLM_BASE_URL,
                    **kwargs
                )
            
            # 自定义 Embedding 函数 (带 phase 进度跟踪)
            self.embedding_stats = {
                "total_texts": 0,
                "phase": "",           # 当前 phase
                "phase_total": 0,      # 当前 phase 总数
                "phase_done": 0,       # 当前 phase 已完成
                "start_time": None,
            }
            
            async def embedding_func(texts: list[str]) -> np.ndarray:
                import time
                stats = self.embedding_stats
                if stats["start_time"] is None:
                    stats["start_time"] = time.time()
                
                stats["total_texts"] += len(texts)
                stats["phase_done"] += len(texts)
                
                # 显示进度
                if stats["phase"] and stats["phase_total"] > 0:
                    progress = min(100, stats["phase_done"] / stats["phase_total"] * 100)
                    bar = "█" * int(progress / 5) + "░" * (20 - int(progress / 5))
                    print(f"\r   📊 {stats['phase']} [{bar}] {stats['phase_done']}/{stats['phase_total']} ({progress:.0f}%)", end="", flush=True)
                else:
                    print(f"\r   📊 Embedding: {stats['total_texts']} 条", end="", flush=True)
                
                result = await openai_embed(
                    texts,
                    model=EMBEDDING_MODEL,
                    api_key=EMBEDDING_API_KEY,
                    base_url=EMBEDDING_BASE_URL,
                )
                return result
            
            # 创建 LightRAG 实例
            self.rag = LightRAG(
                working_dir=LIGHTRAG_WORKING_DIR,
                llm_model_func=llm_func,
                embedding_func=EmbeddingFunc(
                    embedding_dim=EMBEDDING_DIM,
                    max_token_size=8192,
                    func=embedding_func,
                ),
                # 存储配置
                graph_storage="Neo4JStorage",           # 复用 Neo4j
                vector_storage="NanoVectorDBStorage",   # 默认轻量向量
                kv_storage="JsonKVStorage",
                doc_status_storage="JsonDocStatusStorage",

                # 隔离配置
                workspace=LIGHTRAG_WORKSPACE,
                # 性能优化
                chunk_token_size=1200,                  # 分块大小 (默认1200)
                chunk_overlap_token_size=100,           # 重叠大小 (默认100)
                embedding_batch_num=8,                 # 每批 embedding 数量
                embedding_func_max_async=1,             # embedding 并发数 - 硅基流动rpm限制比较狠，配置为2都会导致rate limit
                llm_model_max_async=6,                  # LLM 并发数
                # 语言配置
                addon_params={
                    "language": "Chinese",              # 输出中文
                },
            )
            
            # 初始化存储
            await self.rag.initialize_storages()
            await initialize_pipeline_status()
            
            print("✅ LightRAG 初始化成功!")
            print(f"   📁 工作目录: {LIGHTRAG_WORKING_DIR}")
            print(f"   🗄️  Neo4j: {NEO4J_URI}")
            print(f"   🏷️  Workspace: {LIGHTRAG_WORKSPACE}")
            print()
            print("   ⚙️  性能配置:")
            print(f"      - chunk_token_size: {self.rag.chunk_token_size}")
            print(f"      - embedding_batch_num: {self.rag.embedding_batch_num}")
            print(f"      - embedding_func_max_async: {self.rag.embedding_func_max_async}")
            print(f"      - llm_model_max_async: {self.rag.llm_model_max_async}")
            print()
            print("   🌐 语言配置:")
            print(f"      - language: {self.rag.addon_params.get('language', 'English')}")
            
        except ImportError as e:
            print(f"❌ 缺少依赖: {e}")
            print("   请运行: pip install lightrag-hku[neo4j]")
            sys.exit(1)
        except Exception as e:
            print(f"❌ 初始化失败: {e}")
            raise
    
    async def insert_document(self, file_path: str):
        """导入文档"""
        if not self.rag:
            print("❌ LightRAG 未初始化")
            return False
        
        file_name = Path(file_path).name
        print(f"\n📄 正在处理文档: {file_name}")
        
        # 1. 提取文本
        print("   [1/3] 提取文本...")
        text = extract_text_from_file(file_path)
        if not text:
            print("❌ 文本提取失败")
            return False
        
        print(f"   ✓ 提取完成，共 {len(text)} 字符")
        
        # 重置 embedding 统计
        self.embedding_stats = {
            "total_texts": 0,
            "phase": "",
            "phase_total": 0,
            "phase_done": 0,
            "start_time": None,
        }
        
        # 2. 添加文档标识并导入
        doc_content = f"[文档名称: {file_name}]\n\n{text}"
        print("   [2/3] 正在索引 (实体提取 + 向量化)...")
        
        import time
        import re
        from lightrag.kg.shared_storage import get_namespace_data, get_pipeline_status_lock
        
        start_time = time.time()
        stats = self.embedding_stats
        
        # 启动后台进度监听任务
        async def monitor_progress():
            try:
                pipeline_status = await get_namespace_data("pipeline_status")
                pipeline_status_lock = get_pipeline_status_lock()
                last_message = ""
                while True:
                    await asyncio.sleep(0.3)
                    async with pipeline_status_lock:
                        current_message = pipeline_status.get("latest_message", "")
                        if current_message and current_message != last_message:
                            elapsed = time.time() - start_time
                            
                            # 解析 phase 信息并更新统计
                            # 格式: "Phase 1: Processing 45 entities from doc-xxx"
                            # 格式: "Phase 2: Processing 32 relations from doc-xxx"
                            match = re.search(r'Phase (\d+): Processing (\d+) (entities|relations)', current_message)
                            if match:
                                phase_num = match.group(1)
                                total = int(match.group(2))
                                phase_type = match.group(3)
                                stats["phase"] = f"Phase {phase_num} ({phase_type})"
                                stats["phase_total"] = total
                                stats["phase_done"] = 0  # 重置进度
                                print(f"\n   📡 [{elapsed:.0f}s] {current_message}", flush=True)
                            elif "Completed merging" in current_message:
                                # 完成 merging 阶段
                                stats["phase"] = ""
                                stats["phase_total"] = 0
                                print(f"\n   ✅ [{elapsed:.0f}s] {current_message}", flush=True)
                            else:
                                print(f"\n   📡 [{elapsed:.0f}s] {current_message}", flush=True)
                            
                            last_message = current_message
            except asyncio.CancelledError:
                pass
        
        monitor_task = asyncio.create_task(monitor_progress())
        
        try:
            # 传入 file_paths 参数，使 LightRAG 生成正确的 reference_id
            await self.rag.ainsert(doc_content, file_paths=[file_path])
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
            elapsed = time.time() - start_time
            print()  # 换行
            print(f"   ✓ 索引完成! 实际 embedding: {self.embedding_stats['total_texts']} 条, 耗时 {elapsed:.1f}s")
        except Exception as e:
            monitor_task.cancel()
            print(f"\n   ❌ 索引失败: {e}")
            return False
        
        # 3. 完成
        print("   [3/3] ✅ 文档导入成功!")
        return True
    
    async def query(self, question: str, only_context: bool = False) -> str:
        """
        查询问答
        
        Args:
            question: 用户问题
            only_context: 如果为 True，只返回检索上下文，不触发 AI 回答
        """
        if not self.rag:
            return "❌ LightRAG 未初始化"
        
        try:
            from lightrag import QueryParam
            result = await self.rag.aquery(
                question,
                param=QueryParam(
                    mode="hybrid",
                    only_need_context=only_context,  # 只返回上下文
                )
            )
            return result
        except Exception as e:
            return f"❌ 查询失败: {e}"
    
    async def close(self):
        """关闭连接"""
        if self.rag:
            try:
                await self.rag.finalize_storages()
                print("\n🔌 已关闭 LightRAG 连接")
            except:
                pass

# ============== 主程序 ==============

async def main():
    print("\n" + "=" * 60)
    print("   🔮 LightRAG 最小架构测试 - 操作文档问答")
    print("=" * 60)
    
    demo = LightRAGDemo()
    
    try:
        # 初始化
        await demo.initialize()
        
        # 主循环
        while True:
            print("\n" + "-" * 40)
            print("请选择操作:")
            print("  1. 导入文档")
            print("  2. 开始对话 (AI 回答)")
            print("  3. 检索模式 (只返回上下文)")
            print("  4. 退出")
            print("-" * 40)
            
            choice = input("请输入选项 (1/2/3/4): ").strip()
            
            if choice == "1":
                # 导入文档
                file_path = select_file()
                if file_path:
                    await demo.insert_document(file_path)
                    
            elif choice == "2":
                # 对话模式 - AI 回答
                print("\n💬 进入对话模式 (输入 'exit' 退出)")
                print("-" * 40)
                
                while True:
                    question = input("\n🙋 你: ").strip()
                    
                    if question.lower() in ["exit", "quit", "q", "退出"]:
                        print("👋 退出对话模式")
                        break
                    
                    if not question:
                        continue
                    
                    print("\n🤖 AI: ", end="", flush=True)
                    answer = await demo.query(question, only_context=False)
                    print(answer)
            
            elif choice == "3":
                # 检索模式 - 只返回上下文
                print("\n🔍 进入检索模式 (只返回上下文，不触发 AI 回答)")
                print("   返回内容包括: 实体描述 + 关系描述 + 文档块")
                print("-" * 40)
                
                while True:
                    question = input("\n🔎 检索: ").strip()
                    
                    if question.lower() in ["exit", "quit", "q", "退出"]:
                        print("👋 退出检索模式")
                        break
                    
                    if not question:
                        continue
                    
                    print("\n📄 检索结果:")
                    print("=" * 50)
                    context = await demo.query(question, only_context=True)
                    print(context)
                    print("=" * 50)
                    
            elif choice == "4":
                print("\n👋 再见!")
                break
            else:
                print("❌ 无效选项，请重新输入")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    finally:
        await demo.close()

if __name__ == "__main__":
    asyncio.run(main())

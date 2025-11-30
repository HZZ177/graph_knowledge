"""最小复现：流式响应下多工具调用名称被拼接的问题

测试目的：
1. 对比 streaming=True 和 streaming=False 的行为
2. 打印 chunk 级别的 tool_call_chunks 信息，观察 index 是否正确
3. 确认问题出在哪一层（provider / langchain_core / langgraph）

运行方式：
    cd d:\Pycharm Projects\graph_knowledge
    python -m test.test_streaming_tool_calls
"""

import asyncio
import os
import sys

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool


# ============================================================
# 定义两个简单的测试工具
# ============================================================

@tool
def search_code_context(query: str) -> str:
    """搜索代码上下文"""
    return f"搜索结果: {query}"


@tool
def search_businesses(query: str) -> str:
    """搜索业务流程"""
    return f"业务结果: {query}"


# ============================================================
# 配置（根据你的实际配置修改）
# ============================================================

# 方式1：从数据库读取配置（需要启动后端服务）
def get_llm_from_db(streaming: bool, use_patched: bool = False):
    """从数据库读取 LLM 配置
    
    Args:
        streaming: 是否启用流式
        use_patched: 是否使用修复了 index 的 PatchedChatOpenAI
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.app.services.ai_model_service import AIModelService
    from backend.app.llm.config import get_provider_base_url
    
    # 选择使用原生还是修复版
    if use_patched:
        from backend.app.llm.patched_chat_openai import PatchedChatOpenAI as LLMClass
        print(f"使用: PatchedChatOpenAI (修复 index)")
    else:
        LLMClass = ChatOpenAI
        print(f"使用: ChatOpenAI (原生)")
    
    # 连接数据库（使用绝对路径）
    import os
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "app", "app.db")
    print(f"数据库路径: {db_path}")
    engine = create_engine(f"sqlite:///{db_path}")
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        config = AIModelService.get_active_llm_config(db)
        
        # 自定义网关模式
        if config.provider_type == "custom_gateway" and config.gateway_endpoint:
            base_url = config.gateway_endpoint.rstrip("/")
            if base_url.endswith("/chat/completions"):
                base_url = base_url[:-17]
            elif base_url.endswith("/chat/completions/"):
                base_url = base_url[:-18]
            
            return LLMClass(
                model=config.model_name,
                api_key=config.api_key,
                base_url=base_url,
                temperature=config.temperature,
                streaming=streaming,
            )
        
        # 标准模式
        base_url = config.base_url
        if not base_url and config.provider:
            base_url = get_provider_base_url(config.provider)
        
        return LLMClass(
            model=config.model_name,
            api_key=config.api_key,
            base_url=base_url,
            temperature=config.temperature,
            streaming=streaming,
        )
    finally:
        db.close()


# 方式2：手动配置（如果不想连数据库，直接修改这里）
def get_llm_manual(streaming: bool):
    """手动配置 LLM（修改为你的实际配置）"""
    return ChatOpenAI(
        model="qwen-plus",  # 修改为你的模型名
        api_key="your-api-key",  # 修改为你的 API Key
        base_url="https://your-api-endpoint",  # 修改为你的 API 端点
        temperature=0.7,
        streaming=streaming,
    )


# 选择配置方式
USE_DB_CONFIG = True  # 设为 True 使用数据库配置，False 使用手动配置


def get_llm(streaming: bool, use_patched: bool = False):
    if USE_DB_CONFIG:
        return get_llm_from_db(streaming, use_patched=use_patched)
    else:
        return get_llm_manual(streaming)


# ============================================================
# 测试1：直接调用模型（不经过 Agent）
# ============================================================

async def test_direct_model_call():
    """直接调用模型，对比 streaming 和非 streaming 的 tool_calls"""
    
    tools = [search_code_context, search_businesses]
    
    # 构造一个会触发多工具并行调用的提示词
    prompt = """请同时执行以下两个操作：
1. 使用 search_code_context 工具搜索 "支付回调"
2. 使用 search_businesses 工具搜索 "开卡流程"

请并行调用这两个工具。"""
    
    messages = [HumanMessage(content=prompt)]
    
    print("=" * 60)
    print("测试1: 直接调用模型")
    print("=" * 60)
    
    # ========== 非流式调用 ==========
    print("\n>>> [非流式] streaming=False")
    llm_sync = get_llm(streaming=False)
    llm_sync_with_tools = llm_sync.bind_tools(tools)
    
    response_sync = await llm_sync_with_tools.ainvoke(messages)
    
    print(f"tool_calls 数量: {len(response_sync.tool_calls)}")
    for i, tc in enumerate(response_sync.tool_calls):
        print(f"  [{i}] name={tc['name']!r}, id={tc['id']!r}")
        print(f"       args={tc['args']}")
    
    # ========== 流式调用 ==========
    print("\n>>> [流式] streaming=True")
    llm_stream = get_llm(streaming=True)
    llm_stream_with_tools = llm_stream.bind_tools(tools)
    
    # 收集所有 chunks
    chunks = []
    async for chunk in llm_stream_with_tools.astream(messages):
        chunks.append(chunk)
    
    print(f"\n收到 {len(chunks)} 个 chunks")
    
    # 打印包含 tool_call_chunks 的 chunks
    print("\n--- tool_call_chunks 详情 ---")
    for i, chunk in enumerate(chunks):
        if hasattr(chunk, 'tool_call_chunks') and chunk.tool_call_chunks:
            for tc_chunk in chunk.tool_call_chunks:
                print(f"chunk[{i}]: index={tc_chunk.get('index')}, "
                      f"name={tc_chunk.get('name')!r}, "
                      f"id={tc_chunk.get('id')!r}, "
                      f"args={tc_chunk.get('args')!r}")
    
    # 合并所有 chunks 得到最终消息
    print("\n--- 合并后的结果 ---")
    final_message = chunks[0]
    for chunk in chunks[1:]:
        final_message = final_message + chunk
    
    print(f"tool_calls 数量: {len(final_message.tool_calls)}")
    for i, tc in enumerate(final_message.tool_calls):
        print(f"  [{i}] name={tc['name']!r}, id={tc['id']!r}")
        print(f"       args={tc['args']}")
    
    # ========== 对比结果 ==========
    print("\n>>> 对比结果")
    sync_names = [tc['name'] for tc in response_sync.tool_calls]
    stream_names = [tc['name'] for tc in final_message.tool_calls]
    
    if sync_names == stream_names:
        print("✓ 流式和非流式结果一致")
    else:
        print("✗ 流式和非流式结果不一致!")
        print(f"  非流式: {sync_names}")
        print(f"  流式:   {stream_names}")
    
    return response_sync, final_message


# ============================================================
# 测试2：通过 Agent 调用（更接近实际场景）
# ============================================================

async def test_agent_call():
    """通过 create_agent 调用，观察 stream_mode='updates' 下的行为"""
    
    from langchain.agents import create_agent
    
    tools = [search_code_context, search_businesses]
    
    prompt = """请同时执行以下两个操作：
1. 使用 search_code_context 工具搜索 "支付回调"
2. 使用 search_businesses 工具搜索 "开卡流程"

请并行调用这两个工具。"""
    
    print("\n" + "=" * 60)
    print("测试2: 通过 Agent 调用 (stream_mode='updates')")
    print("=" * 60)
    
    # ========== 非流式 LLM + Agent ==========
    print("\n>>> [Agent + 非流式LLM] streaming=False")
    llm_sync = get_llm(streaming=False)
    agent_sync = create_agent(model=llm_sync, tools=tools)
    
    inputs = {"messages": [HumanMessage(content=prompt)]}
    
    async for event in agent_sync.astream(inputs, stream_mode="updates"):
        if "model" in event:
            messages = event["model"].get("messages", [])
            for msg in messages:
                tool_calls = getattr(msg, "tool_calls", []) or []
                if tool_calls:
                    print(f"tool_calls 数量: {len(tool_calls)}")
                    for i, tc in enumerate(tool_calls):
                        print(f"  [{i}] name={tc['name']!r}, id={tc['id']!r}")
    
    # ========== 流式 LLM + Agent ==========
    print("\n>>> [Agent + 流式LLM] streaming=True")
    llm_stream = get_llm(streaming=True)
    agent_stream = create_agent(model=llm_stream, tools=tools)
    
    async for event in agent_stream.astream(inputs, stream_mode="updates"):
        if "model" in event:
            messages = event["model"].get("messages", [])
            for msg in messages:
                tool_calls = getattr(msg, "tool_calls", []) or []
                if tool_calls:
                    print(f"tool_calls 数量: {len(tool_calls)}")
                    for i, tc in enumerate(tool_calls):
                        print(f"  [{i}] name={tc['name']!r}, id={tc['id']!r}")


# ============================================================
# 测试3：检查 langchain_core 版本和 AIMessageChunk.__add__ 行为
# ============================================================

def test_chunk_merge_logic():
    """检查 AIMessageChunk 的合并逻辑"""
    from langchain_core.messages import AIMessageChunk
    from langchain_core.messages.tool import ToolCallChunk
    
    print("\n" + "=" * 60)
    print("测试3: AIMessageChunk 合并逻辑检查")
    print("=" * 60)
    
    # 打印版本
    import langchain_core
    print(f"\nlangchain_core 版本: {langchain_core.__version__}")
    
    # 模拟两个不同工具的 chunks（正确情况：index 不同）
    print("\n--- 模拟正确的 chunks (index 不同) ---")
    chunk1 = AIMessageChunk(
        content="",
        tool_call_chunks=[
            ToolCallChunk(name="search_code_context", args='{"query":', id="call_1", index=0)
        ]
    )
    chunk2 = AIMessageChunk(
        content="",
        tool_call_chunks=[
            ToolCallChunk(name="", args='"test"}', id="", index=0)
        ]
    )
    chunk3 = AIMessageChunk(
        content="",
        tool_call_chunks=[
            ToolCallChunk(name="search_businesses", args='{"query":', id="call_2", index=1)
        ]
    )
    chunk4 = AIMessageChunk(
        content="",
        tool_call_chunks=[
            ToolCallChunk(name="", args='"test2"}', id="", index=1)
        ]
    )
    
    merged_correct = chunk1 + chunk2 + chunk3 + chunk4
    print(f"合并后 tool_calls: {merged_correct.tool_calls}")
    
    # 模拟错误的 chunks（所有 index 都是 0 或 None）
    print("\n--- 模拟错误的 chunks (index 都是 0) ---")
    chunk1_bad = AIMessageChunk(
        content="",
        tool_call_chunks=[
            ToolCallChunk(name="search_code_context", args='{"query":"test"}', id="call_1", index=0)
        ]
    )
    chunk2_bad = AIMessageChunk(
        content="",
        tool_call_chunks=[
            ToolCallChunk(name="search_businesses", args='{"query":"test2"}', id="call_2", index=0)
        ]
    )
    
    merged_bad = chunk1_bad + chunk2_bad
    print(f"合并后 tool_calls: {merged_bad.tool_calls}")
    
    # 模拟 index 为 None 的情况
    print("\n--- 模拟 index 为 None 的 chunks ---")
    chunk1_none = AIMessageChunk(
        content="",
        tool_call_chunks=[
            ToolCallChunk(name="search_code_context", args='{"query":"test"}', id="call_1", index=None)
        ]
    )
    chunk2_none = AIMessageChunk(
        content="",
        tool_call_chunks=[
            ToolCallChunk(name="search_businesses", args='{"query":"test2"}', id="call_2", index=None)
        ]
    )
    
    merged_none = chunk1_none + chunk2_none
    print(f"合并后 tool_calls: {merged_none.tool_calls}")


# ============================================================
# 主入口
# ============================================================

async def test_patched_stream():
    """测试修复版 PatchedChatOpenAI 的流式响应"""
    
    tools = [search_code_context, search_businesses]
    
    prompt = """请同时执行以下两个操作：
1. 使用 search_code_context 工具搜索 "支付回调"
2. 使用 search_businesses 工具搜索 "开卡流程"

请并行调用这两个工具。"""
    
    messages = [HumanMessage(content=prompt)]
    
    print("\n" + "=" * 60)
    print("测试4: PatchedChatOpenAI 修复版流式测试")
    print("=" * 60)
    
    print("\n>>> [流式 + PatchedChatOpenAI] streaming=True")
    llm_patched = get_llm(streaming=True, use_patched=True)
    llm_patched_with_tools = llm_patched.bind_tools(tools)
    
    # 收集所有 chunks
    chunks = []
    async for chunk in llm_patched_with_tools.astream(messages):
        chunks.append(chunk)
    
    print(f"\n收到 {len(chunks)} 个 chunks")
    
    # 打印包含 tool_call_chunks 的 chunks
    print("\n--- tool_call_chunks 详情 ---")
    for i, chunk in enumerate(chunks):
        if hasattr(chunk, 'tool_call_chunks') and chunk.tool_call_chunks:
            for tc_chunk in chunk.tool_call_chunks:
                print(f"chunk[{i}]: index={tc_chunk.get('index')}, "
                      f"name={tc_chunk.get('name')!r}, "
                      f"id={tc_chunk.get('id')!r}")
    
    # 合并所有 chunks
    print("\n--- 合并后的结果 ---")
    final_message = chunks[0]
    for chunk in chunks[1:]:
        final_message = final_message + chunk
    
    print(f"tool_calls 数量: {len(final_message.tool_calls)}")
    for i, tc in enumerate(final_message.tool_calls):
        print(f"  [{i}] name={tc['name']!r}, id={tc['id']!r}")
    
    # 验证结果
    if len(final_message.tool_calls) == 2:
        print("\n✓ 修复成功！流式响应正确解析为 2 个独立的工具调用")
    else:
        print("\n✗ 修复未生效，仍然存在问题")


async def main():
    print("=" * 60)
    print("流式响应下多工具调用名称拼接问题 - 最小复现测试")
    print("=" * 60)
    
    # 测试3：检查合并逻辑（不需要网络调用）
    test_chunk_merge_logic()
    
    # 测试1：直接调用模型（原生 ChatOpenAI）
    try:
        await test_direct_model_call()
    except Exception as e:
        print(f"\n测试1 失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试4：测试修复版 PatchedChatOpenAI
    try:
        await test_patched_stream()
    except Exception as e:
        print(f"\n测试4 失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

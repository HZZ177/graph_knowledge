"""直接测试 API endpoint 的原始流式响应

目的：检查原始 SSE 响应中 tool_calls 的 index 字段是否正确

运行方式：
    cd d:\Pycharm Projects\graph_knowledge
    python -m test.test_raw_api_stream
"""

import asyncio
import json
import os
import sys

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx


# ============================================================
# 配置
# ============================================================

def get_api_config_from_db():
    """从数据库读取 API 配置"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.app.services.ai_model_service import AIModelService
    from backend.app.llm.config import get_provider_base_url
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "app", "app.db")
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
            
            return {
                "model": config.model_name,
                "api_key": config.api_key,
                "base_url": base_url,
            }
        
        # 标准模式
        base_url = config.base_url
        if not base_url and config.provider:
            base_url = get_provider_base_url(config.provider)
        
        return {
            "model": config.model_name,
            "api_key": config.api_key,
            "base_url": base_url,
        }
    finally:
        db.close()


def get_api_config_manual():
    """手动配置（如果不想连数据库）"""
    return {
        "model": "qwen-plus",  # 修改为你的模型名
        "api_key": "your-api-key",  # 修改为你的 API Key
        "base_url": "https://your-api-endpoint",  # 修改为你的 API 端点（不含 /chat/completions）
    }


# 选择配置方式
USE_DB_CONFIG = True


def get_api_config():
    if USE_DB_CONFIG:
        return get_api_config_from_db()
    else:
        return get_api_config_manual()


# ============================================================
# 测试函数
# ============================================================

async def test_raw_stream():
    """直接发送流式请求，打印原始 SSE 数据"""
    
    config = get_api_config()
    
    print("=" * 70)
    print("直接测试 API endpoint 原始流式响应")
    print("=" * 70)
    print(f"\n配置信息:")
    print(f"  model: {config['model']}")
    print(f"  base_url: {config['base_url']}")
    print(f"  api_key: {config['api_key'][:10]}...{config['api_key'][-4:]}")
    
    # 构造请求
    url = f"{config['base_url']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    
    # 定义两个工具，让模型并行调用
    tools = [
        {
            "type": "function",
            "function": {
                "name": "search_code_context",
                "description": "搜索代码上下文",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词"}
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "search_businesses",
                "description": "搜索业务流程",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词"}
                    },
                    "required": ["query"]
                }
            }
        }
    ]
    
    payload = {
        "model": config["model"],
        "stream": True,
        "messages": [
            {
                "role": "user",
                "content": "请同时执行两个操作：1) 使用 search_code_context 搜索'支付回调' 2) 使用 search_businesses 搜索'开卡流程'。请并行调用这两个工具。"
            }
        ],
        "tools": tools,
        "tool_choice": "auto",
    }
    
    print(f"\n请求 URL: {url}")
    print(f"\n发送请求中...\n")
    
    # 发送流式请求
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as response:
            print(f"响应状态码: {response.status_code}")
            print(f"响应头 Content-Type: {response.headers.get('content-type')}")
            print("\n" + "=" * 70)
            print("原始 SSE 数据流（重点关注 tool_calls 中的 index 字段）")
            print("=" * 70 + "\n")
            
            chunk_count = 0
            tool_call_chunks = []
            
            async for line in response.aiter_lines():
                if not line:
                    continue
                
                # SSE 格式：data: {...}
                if line.startswith("data: "):
                    data_str = line[6:]  # 去掉 "data: " 前缀
                    
                    if data_str.strip() == "[DONE]":
                        print(f"\n[DONE] 流结束")
                        continue
                    
                    try:
                        data = json.loads(data_str)
                        chunk_count += 1
                        
                        # 提取 delta
                        choices = data.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            tool_calls = delta.get("tool_calls", [])
                            
                            if tool_calls:
                                # 有 tool_calls，重点打印
                                print(f"[chunk {chunk_count}] ⭐ tool_calls 数据:")
                                for tc in tool_calls:
                                    index = tc.get("index")
                                    tc_id = tc.get("id")
                                    func = tc.get("function", {})
                                    name = func.get("name")
                                    args = func.get("arguments")
                                    
                                    print(f"    index={index}, id={tc_id!r}, name={name!r}, args={args!r}")
                                    
                                    tool_call_chunks.append({
                                        "chunk": chunk_count,
                                        "index": index,
                                        "id": tc_id,
                                        "name": name,
                                        "args": args,
                                    })
                            else:
                                # 普通内容
                                content = delta.get("content", "")
                                role = delta.get("role", "")
                                if content:
                                    print(f"[chunk {chunk_count}] content: {content!r}")
                                elif role:
                                    print(f"[chunk {chunk_count}] role: {role}")
                                else:
                                    # 空 delta
                                    pass
                    
                    except json.JSONDecodeError as e:
                        print(f"[chunk] JSON 解析失败: {data_str[:100]}...")
                
                elif line.strip():
                    # 其他非空行
                    print(f"[其他] {line}")
    
    # 分析结果
    print("\n" + "=" * 70)
    print("分析结果")
    print("=" * 70)
    
    if not tool_call_chunks:
        print("\n⚠️ 没有收到任何 tool_calls，模型可能没有决定调用工具。")
        print("   请检查模型是否支持 function calling。")
        return
    
    print(f"\n收到 {len(tool_call_chunks)} 个 tool_call chunks:")
    for tc in tool_call_chunks:
        print(f"  chunk={tc['chunk']}, index={tc['index']}, id={tc['id']!r}, name={tc['name']!r}")
    
    # 检查 index 分布
    indices = [tc["index"] for tc in tool_call_chunks]
    unique_indices = set(indices)
    
    print(f"\nindex 值分布: {indices}")
    print(f"唯一 index 值: {unique_indices}")
    
    if len(unique_indices) == 1 and 0 in unique_indices and len(tool_call_chunks) > 1:
        print("\n❌ 问题确认: 所有 tool_call chunks 的 index 都是 0！")
        print("   这会导致 langchain_core 把多个工具调用错误地合并成一个。")
        print("\n   根因: 你的 API endpoint 在流式响应中没有正确设置 index 字段。")
    elif None in unique_indices:
        print("\n⚠️ 注意: 部分 tool_call chunks 的 index 为 None")
        print("   langchain_core 可能可以正确处理（None != None），但这不是标准行为。")
    else:
        print("\n✓ index 值看起来正确（不同工具有不同的 index）")


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    asyncio.run(test_raw_stream())

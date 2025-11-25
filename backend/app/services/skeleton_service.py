"""骨架生成服务 - 多Agent协作 + 流式回调"""

import json
import uuid
import time
import re
from typing import Any, Callable, Dict, List, Optional, Awaitable
from datetime import datetime

from sqlalchemy.orm import Session
from crewai import LLM

from backend.app.llm.base import get_crewai_llm
from backend.app.schemas.skeleton import (
    SkeletonGenerateRequest,
    SkeletonAgentOutput,
    StepSkeleton,
    EdgeSkeleton,
    ImplSkeleton,
    DataResourceSkeleton,
    StepImplLinkSkeleton,
    ImplDataLinkSkeleton,
    ProcessSkeleton,
    AgentStreamChunk,
    DataAnalysisResult,
    FlowDesignResult,
)
from backend.app.schemas.canvas import (
    SaveProcessCanvasRequest,
    CanvasProcess,
    CanvasStep,
    CanvasEdge,
    CanvasImplementation,
    CanvasStepImplLink,
    CanvasDataResource,
    CanvasImplDataLink,
)
from backend.app.core.logger import logger


# ==================== Agent定义 ====================

AGENT_CONFIGS = [
    {
        "name": "数据分析师",
        "index": 0,
        "description": "分析原始技术数据，提取系统、接口、数据资源线索",
    },
    {
        "name": "流程设计师",
        "index": 1,
        "description": "根据业务描述和技术线索，设计业务流程步骤",
    },
    {
        "name": "技术架构师",
        "index": 2,
        "description": "补充实现细节、数据资源访问关系，生成完整骨架",
    },
]


# ==================== Prompt模板 ====================

DATA_ANALYSIS_PROMPT = """你是一位资深的技术分析专家，擅长从日志和网络抓包中提取有价值的业务技术信息。

**重要：过滤噪声数据**
用户提供的原始数据中可能包含大量无关信息，你必须严格过滤以下噪声：

【必须忽略的请求类型】
- 静态资源：.js, .mjs, .jsx, .ts, .css, .less, .sass, .scss, .map
- 图片文件：.jpg, .jpeg, .png, .gif, .svg, .ico, .webp, .bmp
- 字体文件：.woff, .woff2, .ttf, .eot, .otf
- 媒体文件：.mp4, .mp3, .wav, .webm, .ogg
- 文档文件：.pdf, .doc, .xls

【必须忽略的系统请求】
- 前端框架：webpack, vite, next, nuxt, chunk, bundle, manifest
- 监控埋点：track, log, beacon, collect, analytics, metrics, trace, sentry, bugsnag
- 广告相关：ad, ads, advertisement, banner, pixel
- 第三方SDK：google, facebook, baidu, tencent (除非是业务相关)
- 健康检查：health, ping, alive, ready, status

【只提取以下有价值的信息】
- 实际的业务API接口（如 /api/user/xxx, /api/order/xxx）
- 真实的后端服务调用
- 数据库操作相关的日志
- 消息队列相关的日志
- 缓存操作相关的日志

请分析以下原始技术数据，提取与业务"{business_name}"直接相关的关键信息：

【业务描述】
{business_description}

【结构化日志】
{structured_logs}

【抓包接口】
{api_captures}

【已知系统】
{known_systems}

【已知数据资源】
{known_data_resources}

请提取并整理以下信息，以JSON格式输出：
{{
    "systems": ["系统1", "系统2"],
    "apis": [
        {{"system": "系统名", "path": "/api/xxx", "method": "POST", "description": "描述"}}
    ],
    "data_resources": [
        {{"name": "资源名", "type": "table/cache/mq", "system": "所属系统"}}
    ],
    "call_sequence": ["步骤1的描述", "步骤2的描述"]
}}

注意：
1. 只提取与核心业务流程直接相关的接口和资源，过滤所有噪声
2. 如果原始数据混杂了多个不相关的业务，只提取与"{business_name}"相关的部分
3. 如果某项信息无法从数据中提取，请基于业务描述进行合理推断"""


FLOW_DESIGN_PROMPT = """你是一位资深的业务流程设计师，擅长将业务需求转化为清晰的流程图。

请根据以下信息设计业务流程步骤：

【业务名称】
{business_name}

【业务描述】
{business_description}

【渠道】
{channel}

【技术分析结果】
{analysis_result}

请设计流程步骤，以JSON格式输出：
{{
    "steps": [
        {{
            "name": "步骤名称（简短，描述实际业务动作）",
            "description": "步骤详细描述",
            "step_type": "process/decision",
            "order": 1,
            "system_hint": "可能涉及的系统",
            "api_hint": "可能调用的接口",
            "data_hints": ["可能访问的数据"],
            "branches": [
                {{"target_step_name": "目标步骤名", "condition": "条件", "label": "标签"}}
            ]
        }}
    ]
}}

要求：
1. 【重要】不要生成"开始"、"结束"这类虚拟节点，只生成实际的业务步骤
2. 所有步骤的step_type只能是"process"或"decision"
3. decision类型用于有分支判断的步骤，此时填写branches
4. process类型用于普通顺序执行的步骤
5. order从1开始递增
6. 步骤名称应描述实际业务动作，如"展示车卡列表"、"用户选择套餐"、"调用支付接口"等"""


TECH_ENRICH_PROMPT = """你是一位资深的技术架构师，擅长为业务流程补充技术实现细节。

请根据以下信息，为每个步骤补充技术实现（Implementation）和数据资源（DataResource）访问关系：

【业务名称】
{business_name}

【业务描述】
{business_description}

【渠道】
{channel}

【流程步骤】
{flow_steps}

【技术分析结果】
{analysis_result}

请输出完整的骨架结构，以JSON格式（严格遵循以下结构）：
{{
    "process": {{
        "name": "业务名称",
        "channel": "app/web/mini_program",
        "description": "业务描述"
    }},
    "steps": [
        {{
            "name": "步骤名称（实际业务动作，不要开始/结束）",
            "description": "步骤描述",
            "step_type": "process/decision"
        }}
    ],
    "edges": [
        {{
            "from_step_name": "源步骤名",
            "to_step_name": "目标步骤名",
            "edge_type": "normal/branch",
            "condition": "分支条件（仅branch时填写）",
            "label": "边标签"
        }}
    ],
    "implementations": [
        {{
            "name": "POST /api/xxx 或 ServiceName.MethodName",
            "type": "http_endpoint/rpc_method/mq_consumer/scheduled_job",
            "system": "服务名称，如 user-service、payment-service",
            "description": "实现功能描述",
            "code_ref": "服务名/controllers/xxx.py:method_name",
            "step_name": "关联的步骤名称"
        }}
    ],
    "step_impl_links": [
        {{
            "step_name": "步骤名称",
            "impl_name": "实现名称"
        }}
    ],
    "data_resources": [
        {{
            "name": "表名或资源名，如 user_card、pay_order",
            "type": "db_table/cache/mq/api",
            "system": "所属服务名称",
            "description": "数据资源描述"
        }}
    ],
    "impl_data_links": [
        {{
            "impl_name": "实现名称",
            "resource_name": "数据资源名称",
            "access_type": "read/write/read_write",
            "access_pattern": "访问模式描述，如'按user_id查询用户信息'"
        }}
    ]
}}

参考示例（Implementation命名规范）：
- HTTP接口: "POST /api/v1/user/verify_identity" 或 "GET /api/v1/card/list"
- RPC方法: "MemberCardService.CheckOpenEligibility"
- 消息队列: "PaymentResultConsumer"
- 定时任务: "CardExpirationJob"

参考示例（DataResource命名规范）：
- 数据库表: user_card, pay_order, card_plate_bind
- 缓存: user_session_cache
- 消息队列: payment_result_queue

要求：
1. 每个步骤（除start/end外）至少关联一个implementation
2. 合理推断数据资源的访问类型（read/write/read_write）
3. 确保所有引用的数据资源都在data_resources中定义
4. step_impl_links和impl_data_links使用名称引用，不要使用ID
5. edges中用步骤名称指定连接关系，按流程顺序排列"""


# ==================== 核心服务函数 ====================

async def generate_skeleton_with_stream(
    db: Session,
    request: SkeletonGenerateRequest,
    stream_callback: Callable[[AgentStreamChunk], Awaitable[None]],
) -> SaveProcessCanvasRequest:
    """带流式回调的骨架生成
    
    Args:
        db: 数据库会话
        request: 生成请求
        stream_callback: 流式回调函数，接收AgentStreamChunk
        
    Returns:
        转换后的画布数据
    """
    
    logger.info(f"=== 开始骨架生成 ===")
    logger.info(f"业务名称: {request.business_name}")
    logger.info(f"业务描述: {request.business_description[:100]}...")
    logger.info(f"结构化日志: {'有' if request.structured_logs else '无'}")
    logger.info(f"抓包接口: {'有' if request.api_captures else '无'}")
    
    llm = get_crewai_llm(db)
    logger.info(f"LLM实例已获取: {type(llm).__name__}")
    
    # ========== Agent 1: 数据分析 ==========
    agent_config = AGENT_CONFIGS[0]
    start_time = time.time()
    
    await stream_callback(AgentStreamChunk(
        type="agent_start",
        agent_name=agent_config["name"],
        agent_index=agent_config["index"],
        agent_description=agent_config["description"],
    ))
    
    analysis_prompt = DATA_ANALYSIS_PROMPT.format(
        business_name=request.business_name,
        business_description=request.business_description,
        structured_logs=request.structured_logs or "无",
        api_captures=request.api_captures or "无",
        known_systems=", ".join(request.known_systems) if request.known_systems else "无",
        known_data_resources=", ".join(request.known_data_resources) if request.known_data_resources else "无",
    )
    
    analysis_output = await _call_llm_with_stream(
        llm, analysis_prompt, agent_config, stream_callback
    )
    
    analysis_result = _parse_analysis_result(analysis_output)
    
    await stream_callback(AgentStreamChunk(
        type="agent_end",
        agent_name=agent_config["name"],
        agent_index=agent_config["index"],
        agent_output=analysis_output,
        duration_ms=int((time.time() - start_time) * 1000),
    ))
    
    # ========== Agent 2: 流程设计 ==========
    agent_config = AGENT_CONFIGS[1]
    start_time = time.time()
    
    await stream_callback(AgentStreamChunk(
        type="agent_start",
        agent_name=agent_config["name"],
        agent_index=agent_config["index"],
        agent_description=agent_config["description"],
    ))
    
    flow_prompt = FLOW_DESIGN_PROMPT.format(
        business_name=request.business_name,
        business_description=request.business_description,
        channel=request.channel or "通用",
        analysis_result=analysis_output,
    )
    
    flow_output = await _call_llm_with_stream(
        llm, flow_prompt, agent_config, stream_callback
    )
    
    flow_result = _parse_flow_result(flow_output)
    
    await stream_callback(AgentStreamChunk(
        type="agent_end",
        agent_name=agent_config["name"],
        agent_index=agent_config["index"],
        agent_output=flow_output,
        duration_ms=int((time.time() - start_time) * 1000),
    ))
    
    # ========== Agent 3: 技术充实 ==========
    agent_config = AGENT_CONFIGS[2]
    start_time = time.time()
    
    await stream_callback(AgentStreamChunk(
        type="agent_start",
        agent_name=agent_config["name"],
        agent_index=agent_config["index"],
        agent_description=agent_config["description"],
    ))
    
    enrich_prompt = TECH_ENRICH_PROMPT.format(
        business_name=request.business_name,
        business_description=request.business_description,
        channel=request.channel or "通用",
        flow_steps=flow_output,
        analysis_result=analysis_output,
    )
    
    enrich_output = await _call_llm_with_stream(
        llm, enrich_prompt, agent_config, stream_callback
    )
    
    skeleton = _parse_skeleton_output(enrich_output, request)
    
    await stream_callback(AgentStreamChunk(
        type="agent_end",
        agent_name=agent_config["name"],
        agent_index=agent_config["index"],
        agent_output=enrich_output,
        duration_ms=int((time.time() - start_time) * 1000),
    ))
    
    # ========== 转换为画布结构 ==========
    canvas_data = convert_skeleton_to_canvas(skeleton)
    
    await stream_callback(AgentStreamChunk(
        type="result",
        agent_name="系统",
        agent_index=-1,
        canvas_data=canvas_data.dict(),
    ))
    
    return canvas_data


async def _call_llm_with_stream(
    llm: LLM,
    prompt: str,
    agent_config: dict,
    stream_callback: Callable[[AgentStreamChunk], Awaitable[None]],
) -> str:
    """调用LLM并模拟流式返回内容
    
    注意：CrewAI的LLM.call()不支持stream参数，这里使用普通调用后模拟流式输出
    """
    
    agent_name = agent_config["name"]
    agent_index = agent_config["index"]
    
    logger.info(f"[{agent_name}] 开始调用LLM...")
    logger.debug(f"[{agent_name}] Prompt长度: {len(prompt)} 字符")
    
    try:
        # 直接调用LLM（不支持流式）
        full_response = str(llm.call(prompt))
        logger.info(f"[{agent_name}] LLM调用完成，响应长度: {len(full_response)} 字符")
        logger.debug(f"[{agent_name}] LLM响应内容: {full_response[:500]}...")
        
        # 模拟流式输出：按句子分割
        sentences = re.split(r'([。！？\n])', full_response)
        for i in range(0, len(sentences), 2):
            chunk = sentences[i]
            if i + 1 < len(sentences):
                chunk += sentences[i + 1]
            if chunk.strip():
                await stream_callback(AgentStreamChunk(
                    type="stream",
                    agent_name=agent_name,
                    agent_index=agent_index,
                    content=chunk,
                ))
        
        return full_response
        
    except Exception as e:
        logger.error(f"[{agent_name}] LLM调用失败: {e}", exc_info=True)
        # 发送错误信息
        error_msg = f"LLM调用失败: {str(e)}"
        await stream_callback(AgentStreamChunk(
            type="stream",
            agent_name=agent_name,
            agent_index=agent_index,
            content=error_msg,
        ))
        raise


def _parse_analysis_result(output: str) -> DataAnalysisResult:
    """解析数据分析Agent的输出"""
    try:
        json_match = re.search(r'\{[\s\S]*\}', output)
        if json_match:
            data = json.loads(json_match.group())
            return DataAnalysisResult(
                systems=data.get("systems", []),
                apis=data.get("apis", []),
                data_resources=data.get("data_resources", []),
                call_sequence=data.get("call_sequence", []),
                raw_analysis=output,
            )
    except Exception as e:
        logger.warning(f"解析分析结果失败: {e}")
    
    return DataAnalysisResult(raw_analysis=output)


def _parse_flow_result(output: str) -> FlowDesignResult:
    """解析流程设计Agent的输出"""
    try:
        json_match = re.search(r'\{[\s\S]*\}', output)
        if json_match:
            data = json.loads(json_match.group())
            steps = []
            for step_data in data.get("steps", []):
                branches = None
                if step_data.get("branches"):
                    branches = [
                        BranchRef(**b) for b in step_data["branches"]
                    ]
                steps.append(StepSkeleton(
                    name=step_data.get("name", "未命名步骤"),
                    description=step_data.get("description", ""),
                    step_type=step_data.get("step_type", "process"),
                    order=step_data.get("order", 0),
                    system_hint=step_data.get("system_hint"),
                    api_hint=step_data.get("api_hint"),
                    data_hints=step_data.get("data_hints"),
                    branches=branches,
                ))
            return FlowDesignResult(steps=steps, raw_design=output)
    except Exception as e:
        logger.warning(f"解析流程设计结果失败: {e}")
    
    return FlowDesignResult(raw_design=output)


def _parse_skeleton_output(output: str, request: SkeletonGenerateRequest) -> SkeletonAgentOutput:
    """解析技术充实Agent的输出（新格式）"""
    try:
        json_match = re.search(r'\{[\s\S]*\}', output)
        if json_match:
            data = json.loads(json_match.group())
            logger.info(f"成功解析JSON，keys: {data.keys()}")
            
            # 解析process
            process_data = data.get("process", {})
            process = ProcessSkeleton(
                name=process_data.get("name", request.business_name),
                channel=process_data.get("channel", request.channel or ""),
                description=process_data.get("description", request.business_description),
            )
            
            # 解析steps
            steps = []
            for step_data in data.get("steps", []):
                steps.append(StepSkeleton(
                    name=step_data.get("name", "未命名步骤"),
                    description=step_data.get("description", ""),
                    step_type=step_data.get("step_type", "process"),
                ))
            
            # 解析edges
            edges = []
            for edge_data in data.get("edges", []):
                edges.append(EdgeSkeleton(
                    from_step_name=edge_data.get("from_step_name", ""),
                    to_step_name=edge_data.get("to_step_name", ""),
                    edge_type=edge_data.get("edge_type", "normal"),
                    condition=edge_data.get("condition"),
                    label=edge_data.get("label"),
                ))
            
            # 解析implementations
            implementations = []
            for impl_data in data.get("implementations", []):
                implementations.append(ImplSkeleton(
                    name=impl_data.get("name", "未命名实现"),
                    type=impl_data.get("type", "http_endpoint"),
                    system=impl_data.get("system", "unknown"),
                    description=impl_data.get("description"),
                    code_ref=impl_data.get("code_ref"),
                    step_name=impl_data.get("step_name"),  # 兼容旧格式
                ))
            
            # 解析step_impl_links
            step_impl_links = []
            for link_data in data.get("step_impl_links", []):
                step_impl_links.append(StepImplLinkSkeleton(
                    step_name=link_data.get("step_name", ""),
                    impl_name=link_data.get("impl_name", ""),
                ))
            
            # 如果没有step_impl_links，从implementations的step_name字段提取
            if not step_impl_links:
                for impl in implementations:
                    if impl.step_name:
                        step_impl_links.append(StepImplLinkSkeleton(
                            step_name=impl.step_name,
                            impl_name=impl.name,
                        ))
            
            # 解析data_resources
            data_resources = []
            for res_data in data.get("data_resources", []):
                data_resources.append(DataResourceSkeleton(
                    name=res_data.get("name", "未命名资源"),
                    type=res_data.get("type", "db_table"),
                    system=res_data.get("system", "unknown"),
                    description=res_data.get("description"),
                ))
            
            # 解析impl_data_links
            impl_data_links = []
            for link_data in data.get("impl_data_links", []):
                impl_data_links.append(ImplDataLinkSkeleton(
                    impl_name=link_data.get("impl_name", ""),
                    resource_name=link_data.get("resource_name", ""),
                    access_type=link_data.get("access_type", "read"),
                    access_pattern=link_data.get("access_pattern"),
                ))
            
            logger.info(f"解析完成: {len(steps)}步骤, {len(edges)}边, {len(implementations)}实现, {len(data_resources)}资源")
            
            return SkeletonAgentOutput(
                process=process,
                steps=steps,
                edges=edges,
                implementations=implementations,
                step_impl_links=step_impl_links,
                data_resources=data_resources,
                impl_data_links=impl_data_links,
            )
    except Exception as e:
        logger.error(f"解析骨架输出失败: {e}", exc_info=True)
    
    # 降级：返回最小骨架
    return SkeletonAgentOutput(
        process=ProcessSkeleton(
            name=request.business_name,
            channel=request.channel or "",
            description=request.business_description,
        ),
        steps=[
            StepSkeleton(name="开始", description="流程开始", step_type="start"),
            StepSkeleton(name="结束", description="流程结束", step_type="end"),
        ],
        edges=[
            EdgeSkeleton(from_step_name="开始", to_step_name="结束", edge_type="normal"),
        ],
        implementations=[],
        step_impl_links=[],
        data_resources=[],
        impl_data_links=[],
    )


# ==================== 骨架转画布 ====================

def convert_skeleton_to_canvas(skeleton: SkeletonAgentOutput) -> SaveProcessCanvasRequest:
    """将Agent输出转换为画布结构（新格式）"""
    
    process_id = uuid.uuid4().hex
    
    logger.info(f"开始转换骨架到画布: process={skeleton.process.name}")
    
    # 1. 生成步骤ID映射
    step_name_to_id: Dict[str, str] = {}
    steps: List[CanvasStep] = []
    for step in skeleton.steps:
        step_id = uuid.uuid4().hex
        step_name_to_id[step.name] = step_id
        steps.append(CanvasStep(
            step_id=step_id,
            name=step.name,
            description=step.description,
            step_type=step.step_type,
        ))
    logger.info(f"生成{len(steps)}个步骤节点")
    
    # 2. 生成边（从edges列表）
    edges: List[CanvasEdge] = []
    for edge in skeleton.edges:
        from_id = step_name_to_id.get(edge.from_step_name)
        to_id = step_name_to_id.get(edge.to_step_name)
        if from_id and to_id:
            edges.append(CanvasEdge(
                from_step_id=from_id,
                to_step_id=to_id,
                edge_type=edge.edge_type,
                condition=edge.condition,
                label=edge.label,
            ))
    logger.info(f"生成{len(edges)}条边")
    
    # 3. 生成实现
    impl_name_to_id: Dict[str, str] = {}
    implementations: List[CanvasImplementation] = []
    
    for impl in skeleton.implementations:
        impl_id = uuid.uuid4().hex
        impl_name_to_id[impl.name] = impl_id
        
        implementations.append(CanvasImplementation(
            impl_id=impl_id,
            name=impl.name,
            type=impl.type,
            system=impl.system,
            description=impl.description,
            code_ref=impl.code_ref,
        ))
    logger.info(f"生成{len(implementations)}个实现节点")
    
    # 4. 生成步骤-实现关联（从step_impl_links列表）
    step_impl_links: List[CanvasStepImplLink] = []
    for link in skeleton.step_impl_links:
        step_id = step_name_to_id.get(link.step_name)
        impl_id = impl_name_to_id.get(link.impl_name)
        if step_id and impl_id:
            step_impl_links.append(CanvasStepImplLink(
                step_id=step_id,
                impl_id=impl_id,
            ))
    logger.info(f"生成{len(step_impl_links)}条步骤-实现关联")
    
    # 5. 生成数据资源
    resource_name_to_id: Dict[str, str] = {}
    data_resources: List[CanvasDataResource] = []
    
    for res in skeleton.data_resources:
        resource_id = uuid.uuid4().hex
        resource_name_to_id[res.name] = resource_id
        
        data_resources.append(CanvasDataResource(
            resource_id=resource_id,
            name=res.name,
            type=res.type,
            system=res.system,
            description=res.description,
        ))
    logger.info(f"生成{len(data_resources)}个数据资源节点")
    
    # 6. 生成实现-数据资源关联（从impl_data_links列表）
    impl_data_links: List[CanvasImplDataLink] = []
    for link in skeleton.impl_data_links:
        impl_id = impl_name_to_id.get(link.impl_name)
        resource_id = resource_name_to_id.get(link.resource_name)
        if impl_id and resource_id:
            impl_data_links.append(CanvasImplDataLink(
                impl_id=impl_id,
                resource_id=resource_id,
                access_type=link.access_type,
                access_pattern=link.access_pattern,
            ))
    logger.info(f"生成{len(impl_data_links)}条实现-数据关联")
    
    return SaveProcessCanvasRequest(
        process_id=process_id,
        process=CanvasProcess(
            process_id=process_id,
            name=skeleton.process.name,
            description=skeleton.process.description,
            channel=skeleton.process.channel,
        ),
        steps=steps,
        edges=edges,
        implementations=implementations,
        step_impl_links=step_impl_links,
        data_resources=data_resources,
        impl_data_links=impl_data_links,
        impl_links=[],
    )

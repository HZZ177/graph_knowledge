"""骨架生成服务 - 多Agent协作 + WebSocket流式响应

基于 CrewAI 多Agent协作生成业务流程骨架。
"""

import json
import uuid
import re
from typing import Dict, List, Optional

from sqlalchemy.orm import Session
from crewai import Crew
from starlette.websockets import WebSocket

from backend.app.llm.factory import get_crewai_llm
from backend.app.llm.crewai.streaming import run_agent_stream
from backend.app.llm.crewai.agents import CrewAiAgents
from backend.app.llm.crewai.tasks import CrewAiTasks
from backend.app.llm.crewai.prompts import (
    DATA_ANALYSIS_PROMPT,
    FLOW_DESIGN_PROMPT,
    TECH_ENRICH_PROMPT,
)
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
    DataAnalysisResult,
    FlowDesignResult,
    BranchRef,
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


# ==================== 核心服务函数 ====================

async def generate_skeleton(
        db: Session,
        request: SkeletonGenerateRequest,
        websocket: WebSocket,
) -> SaveProcessCanvasRequest:
    """生成业务骨架（WebSocket 流式响应）
    
    Service 层只负责业务编排，流式发送由 streaming 层自动处理。
    
    Args:
        db: 数据库会话
        request: 生成请求
        websocket: WebSocket 连接，用于流式响应
        
    Returns:
        转换后的画布数据
    """
    logger.info(f"=== 开始骨架生成 ===")
    logger.info(f"业务名称: {request.business_name}")
    logger.info(f"业务描述: {request.business_description[:100]}...")

    llm = get_crewai_llm(db)

    # ========== Agent 1: 数据分析 ==========
    analysis_prompt = DATA_ANALYSIS_PROMPT.format(
        business_name=request.business_name,
        business_description=request.business_description,
        structured_logs=request.structured_logs or "无",
        api_captures=request.api_captures or "无",
        known_systems=", ".join(request.known_systems) if request.known_systems else "无",
        known_data_resources=", ".join(request.known_data_resources) if request.known_data_resources else "无",
    )

    analyst_agent = CrewAiAgents.create_data_analysis_agent(llm)
    analyst_task = CrewAiTasks.create_data_analysis_task(analyst_agent, analysis_prompt)
    crew = Crew(
        agents=[analyst_agent],
        tasks=[analyst_task],
        verbose=False,
        stream=True
    )

    # 直接调用，streaming 层自动处理 chunk 发送
    analysis_output = await run_agent_stream(crew, websocket, CrewAiAgents.get_meta(0))

    # ========== Agent 2: 流程设计 ==========
    flow_prompt = FLOW_DESIGN_PROMPT.format(
        business_name=request.business_name,
        business_description=request.business_description,
        channel=request.channel or "通用",
        analysis_result=analysis_output,
    )

    designer_agent = CrewAiAgents.create_flow_design_agent(llm)
    designer_task = CrewAiTasks.create_flow_design_task(designer_agent, flow_prompt)
    crew = Crew(
        agents=[designer_agent],
        tasks=[designer_task],
        verbose=False,
        stream=True
    )

    flow_output = await run_agent_stream(crew, websocket, CrewAiAgents.get_meta(1))

    # ========== Agent 3: 技术充实 ==========
    enrich_prompt = TECH_ENRICH_PROMPT.format(
        business_name=request.business_name,
        business_description=request.business_description,
        channel=request.channel or "通用",
        flow_steps=flow_output,
        analysis_result=analysis_output,
    )

    architect_agent = CrewAiAgents.create_tech_architect_agent(llm)
    architect_task = CrewAiTasks.create_tech_enrich_task(architect_agent, enrich_prompt)
    crew = Crew(
        agents=[architect_agent],
        tasks=[architect_task],
        verbose=False,
        stream=True
    )

    enrich_output = await run_agent_stream(crew, websocket, CrewAiAgents.get_meta(2))

    # ========== 转换为画布结构 ==========
    skeleton = _parse_skeleton_output(enrich_output, request)
    canvas_data = convert_skeleton_to_canvas(skeleton)

    # 发送最终结果
    await websocket.send_text(json.dumps({
        "type": "result",
        "agent_name": "系统",
        "agent_index": -1,
        "canvas_data": canvas_data.dict(),
    }))

    return canvas_data


def _extract_json_block(text: str) -> Optional[str]:
    """从LLM输出中提取第一段JSON对象，避免前后解释性文字的干扰。"""
    if not text:
        return None
    # 优先从 ```json ... ``` 代码块中提取
    fence_pattern = r"```json\s*([\s\S]*?)```"
    fenced_blocks = re.findall(fence_pattern, text, re.IGNORECASE)
    if fenced_blocks:
        for block in reversed(fenced_blocks):
            candidate = block.strip()
            try:
                json.loads(candidate)
                return candidate
            except Exception:
                continue

    # 回退策略：匹配整段文本中的第一段 {...}
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    return match.group()


def _parse_analysis_result(output: str) -> DataAnalysisResult:
    """解析数据分析Agent的输出"""
    try:
        json_str = _extract_json_block(output) or output
        data = json.loads(json_str)
        return DataAnalysisResult(
            systems=data.get("systems", []),
            apis=data.get("apis", []),
            data_resources=data.get("data_resources", []),
            call_sequence=data.get("call_sequence", []),
            raw_analysis=output,
        )
    except Exception as e:
        logger.debug(
            "解析分析结果失败: %s, output preview=%s",
            e,
            output[:200].replace("\n", " ") if output else "",
        )

    return DataAnalysisResult(raw_analysis=output)


def _parse_flow_result(output: str) -> FlowDesignResult:
    """解析流程设计Agent的输出"""
    try:
        json_str = _extract_json_block(output) or output
        data = json.loads(json_str)
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
        logger.debug(
            "解析流程设计结果失败: %s, output preview=%s",
            e,
            output[:200].replace("\n", " ") if output else "",
        )

    return FlowDesignResult(raw_design=output)


def _parse_skeleton_output(output: str, request: SkeletonGenerateRequest) -> SkeletonAgentOutput:
    """解析技术充实Agent的输出（新格式）"""
    try:
        json_str = _extract_json_block(output) or output
        data = json.loads(json_str)
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
            ))

        # 解析implementations
        implementations = []
        for impl_data in data.get("implementations", []):
            implementations.append(ImplSkeleton(
                name=impl_data.get("name", ""),
                type=impl_data.get("type", "http_endpoint"),
                system=impl_data.get("system", ""),
                description=impl_data.get("description"),
                code_ref=impl_data.get("code_ref"),
            ))

        # 解析step_impl_links
        step_impl_links = []
        for link_data in data.get("step_impl_links", []):
            step_impl_links.append(StepImplLinkSkeleton(
                step_name=link_data.get("step_name", ""),
                impl_name=link_data.get("impl_name", ""),
            ))

        # 解析data_resources
        data_resources = []
        for res_data in data.get("data_resources", []):
            data_resources.append(DataResourceSkeleton(
                name=res_data.get("name", ""),
                type=res_data.get("type", "db_table"),
                system=res_data.get("system", ""),
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
        logger.warning(f"解析技术充实结果失败: {e}")

    # 解析失败时，构造最小骨架
    logger.info("使用降级策略构造最小骨架")
    process = ProcessSkeleton(
        name=request.business_name,
        channel=request.channel or "",
        description=request.business_description,
    )

    return SkeletonAgentOutput(
        process=process,
        steps=[],
        edges=[],
        implementations=[],
        step_impl_links=[],
        data_resources=[],
        impl_data_links=[],
    )


# ==================== 骨架转画布 ====================

def convert_skeleton_to_canvas(skeleton: SkeletonAgentOutput) -> SaveProcessCanvasRequest:
    """将Agent输出转换为画布结构"""

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

    # 2. 生成边
    edges: List[CanvasEdge] = []
    for edge in skeleton.edges:
        from_id = step_name_to_id.get(edge.from_step_name)
        to_id = step_name_to_id.get(edge.to_step_name)
        if from_id and to_id:
            edges.append(CanvasEdge(
                from_step_id=from_id,
                to_step_id=to_id,
                edge_type=edge.edge_type,
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

    # 4. 生成步骤-实现关联
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

    # 6. 生成实现-数据资源关联
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

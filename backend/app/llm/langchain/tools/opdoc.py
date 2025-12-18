"""永策Pro企业知识库检索工具

提供基于 LightRAG 的永策Pro全量文档检索能力，用于永策Pro智能助手 Agent。
"""

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.app.db.sqlite import SessionLocal
from backend.app.services.lightrag_service import LightRAGService
from backend.app.core.logger import logger


class SearchYongceDocsInput(BaseModel):
    """search_yongce_docs 工具输入参数"""
    question: str = Field(
        ..., 
        description="要查询的问题，如 '权限管理功能说明'、'订单流程设计'、'API接口文档'、'部署操作步骤'"
    )
    mode: str = Field(
        default="mix",
        description="""
检索模式，根据问题类型选择最优模式：

- **naive**（最快，2-4秒）：纯向量相似度检索
  适用场景：简单概念查询，如"什么是XX"、"XX的定义"
  特点：速度最快，仅基于语义相似性，无关系分析

- **local**（较快，5-8秒）：实体中心的图谱检索
  适用场景：特定实体查询，如"XX功能如何配置"、"XX模块的使用方法"
  特点：从实体出发，遍历1度关系，侧重实体描述和直接关联

- **global**（较慢，10-15秒）：关系中心的图谱检索
  适用场景：关系分析问题，如"XX和YY如何关联"、"影响链分析"
  特点：从关系出发，跨领域连接，侧重关系模式和全局结构

- **hybrid**（最慢，15-25秒）：深度图谱推理
  适用场景：复杂分析问题，需要全面视角，如"完整的配置和使用流程"/"用户问题分析"，可能是多个模块互相影响，需要综合考虑的
  特点：并行执行local和global，深度探索多层关系，最全面但最慢

- **mix**（推荐，8-12秒）：图谱+向量平衡检索【默认】
  适用场景：通用查询，不确定问题类型时使用
  特点：并行执行local和naive，平衡结构与语义，容错性强

选择建议：
- 90%的问题使用默认的 mix 即可
- 只有明确需要深度分析时才使用 hybrid
- 简单定义查询可用 naive 加速
"""
    )


@tool(args_schema=SearchYongceDocsInput)
async def search_yongce_docs(question: str, mode: str = "mix") -> str:
    """搜索永策Pro企业知识库
    
    从永策Pro项目的全量文档中检索相关内容，包括产品文档、技术文档、API文档、操作手册、开发指南等。
    支持多种检索模式，可根据问题类型选择最优策略（默认使用mix模式，适合90%的场景）。
    
    知识库范围：
    - 产品功能：功能说明、使用方法、配置项
    - 技术文档：架构设计、技术选型、实现细节
    - API文档：接口说明、参数定义、调用示例
    - 操作指南：部署流程、运维操作、故障排查
    - 开发文档：开发规范、代码示例、最佳实践
    - 业务流程：业务说明、流程图、使用场景
    
    Args:
        question: 要查询的问题，使用自然语言描述即可
        mode: 检索模式（默认"mix"），根据问题选择：
              - naive: 简单概念查询（最快）
              - local: 特定功能/实体查询（常用）
              - global: 关系分析查询
              - hybrid: 复杂深度分析（最慢最全）
              - mix: 通用平衡模式（推荐，默认）
        
    Returns:
        检索到的相关文档内容，包含详细说明和来源引用
    """
    logger.info(f"[YongceTool] 收到检索请求: question={question[:50]}..., mode={mode}")
    
    # 验证mode参数
    valid_modes = ["naive", "local", "global", "hybrid", "mix"]
    if mode not in valid_modes:
        logger.warning(f"[YongceTool] 无效的mode={mode}，使用默认值mix")
        mode = "mix"
    
    # 获取数据库会话
    db = SessionLocal()
    
    try:
        # 调用 LightRAG 服务检索
        result = await LightRAGService.search_context(question, db, mode=mode)
        
        context = result.get("context", "")
        sources = result.get("sources", [])
        error = result.get("error")
        
        if error:
            return f"检索失败: {error}"
        
        if not context:
            return "未找到相关文档。\n\n建议：\n- 尝试使用不同的关键词\n- 简化问题描述\n- 确认文档库中已包含相关内容"
        
        # 格式化输出
        output_parts = ["## 检索结果\n", context]
        
        # 添加来源引用（Reference Document List）
        if sources:
            output_parts.append("\n\n## Reference Document List")
            output_parts.append("以下是检索到的文档来源，请在回答末尾以Markdown链接格式引用：")
            for idx, source in enumerate(sources, 1):
                name = source.get("name", "") if isinstance(source, dict) else source
                url = source.get("url", "") if isinstance(source, dict) else ""
                if url:
                    output_parts.append(f"[{idx}] 文档标题: {name}")
                    output_parts.append(f"    文档地址: {url}")
                else:
                    output_parts.append(f"[{idx}] 文档标题: {name}")
        
        output = "\n".join(output_parts)
        
        logger.info(f"[YongceTool] 检索成功: context_length={len(context)}, sources_count={len(sources)}")
        logger.debug(f"[YongceTool] 完整检索内容:\n{context}")  # DEBUG: 查看完整内容是否包含图片
        
        return output
    
    except Exception as e:
        logger.error(f"[YongceTool] 检索异常: {e}")
        return f"检索过程中发生错误: {str(e)}"
    
    finally:
        db.close()


def get_opdoc_tools():
    """获取永策Pro智能助手 Agent 的工具集
    
    Returns:
        包含 1 个工具的列表：search_yongce_docs
    """
    return [search_yongce_docs]

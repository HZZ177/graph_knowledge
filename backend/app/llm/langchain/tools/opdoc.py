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


@tool(args_schema=SearchYongceDocsInput)
async def search_yongce_docs(question: str) -> str:
    """搜索永策Pro企业知识库
    
    从永策Pro项目的全量文档中检索相关内容，包括产品文档、技术文档、API文档、操作手册、开发指南等。
    使用 LightRAG 的混合检索模式（向量 + 知识图谱），能够理解语义并发现文档间的关联。
    
    知识库范围：
    - 产品功能：功能说明、使用方法、配置项
    - 技术文档：架构设计、技术选型、实现细节
    - API文档：接口说明、参数定义、调用示例
    - 操作指南：部署流程、运维操作、故障排查
    - 开发文档：开发规范、代码示例、最佳实践
    - 业务流程：业务说明、流程图、使用场景
    
    Args:
        question: 要查询的问题，使用自然语言描述即可
        
    Returns:
        检索到的相关文档内容，包含详细说明和来源引用
    """
    logger.info(f"[YongceTool] 收到检索请求: {question[:50]}...")
    
    # 获取数据库会话
    db = SessionLocal()
    
    try:
        # 调用 LightRAG 服务检索
        result = await LightRAGService.search_context(question, db)
        
        context = result.get("context", "")
        sources = result.get("sources", [])
        error = result.get("error")
        
        if error:
            return f"检索失败: {error}"
        
        if not context:
            return "未找到相关文档。\n\n建议：\n- 尝试使用不同的关键词\n- 简化问题描述\n- 确认文档库中已包含相关内容"
        
        # 格式化输出
        output_parts = ["## 检索结果\n", context]
        
        # 添加来源引用
        if sources:
            output_parts.append("\n\n## 来源文档")
            for idx, source in enumerate(sources, 1):
                output_parts.append(f"{idx}. {source}")
        
        output = "\n".join(output_parts)
        
        logger.info(f"[YongceTool] 检索成功: context_length={len(context)}, sources_count={len(sources)}")
        
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

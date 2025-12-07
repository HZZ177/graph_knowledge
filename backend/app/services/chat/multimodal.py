"""多模态消息构造工具"""

from typing import List, Dict, Any, Optional
from langchain_core.messages import HumanMessage
from loguru import logger


def determine_file_type(content_type: str, filename: str) -> str:
    """判断文件类型
    
    Args:
        content_type: MIME 类型
        filename: 文件名
    
    Returns:
        'image' | 'document' | 'audio' | 'video' | 'unknown'
    """
    # 图片类型
    if content_type.startswith('image/'):
        return 'image'
    
    # 音频类型
    if content_type.startswith('audio/'):
        return 'audio'
    
    # 视频类型
    if content_type.startswith('video/'):
        return 'video'
    
    # 文档类型
    document_types = {
        'application/pdf',
        'text/plain',
        'text/markdown',
        'text/csv',
        'application/json',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }
    
    if content_type in document_types:
        return 'document'
    
    # 代码文件
    code_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.rb', '.php'}
    if any(filename.lower().endswith(ext) for ext in code_extensions):
        return 'document'
    
    # 日志文件
    if filename.lower().endswith('.log'):
        return 'document'
    
    return 'unknown'


def build_multimodal_message(
    question: str,
    attachments: Optional[List[Dict[str, Any]]] = None
) -> HumanMessage:
    """构造多模态 HumanMessage（基于 URL）
    
    Args:
        question: 用户问题文本
        attachments: 文件附件列表，格式：
            [
                {
                    "file_id": "uuid",
                    "url": "https://oss.../file.png",
                    "type": "image",
                    "filename": "screenshot.png",
                    "content_type": "image/png"
                }
            ]
    
    Returns:
        HumanMessage 对象，content 为多模态数组
    
    示例：
        message = build_multimodal_message(
            "分析这张架构图",
            [{"file_id": "...", "url": "https://...", "type": "image", ...}]
        )
        
        # message.content = [
        #     {"type": "text", "text": "分析这张架构图"},
        #     {"type": "image_url", "image_url": {"url": "https://..."}}
        # ]
    """
    # 构造 content 数组（符合 LangChain 多模态标准）
    content = []
    
    # 1. 添加文本部分
    if question and question.strip():
        content.append({
            "type": "text",
            "text": question
        })
    
    # 2. 添加文件附件
    if attachments:
        for att in attachments:
            file_type = att.get('type', 'unknown')
            url = att.get('url', '')
            filename = att.get('filename', 'unknown')
            
            # 图片类型：使用 image_url
            if file_type == 'image':
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": url,
                        "detail": "high"  # 高分辨率分析
                    }
                })
                logger.info(f"[Multimodal] 添加图片附件: {filename}")
            
            # 文档类型：暂时作为文本引用（未来可以扩展为文档解析）
            elif file_type == 'document':
                # 对于文档，LLM 可能无法直接读取 URL
                # 这里可以选择：
                # 1. 下载文档并提取文本（推荐）
                # 2. 仅提供文件名提示用户
                content.append({
                    "type": "text",
                    "text": f"\n[附件: {filename}，URL: {url}]"
                })
                logger.info(f"[Multimodal] 添加文档附件引用: {filename}")
            
            # 音频/视频：暂不支持，提示用户
            elif file_type in ['audio', 'video']:
                content.append({
                    "type": "text",
                    "text": f"\n[附件: {filename} ({file_type})，暂不支持直接处理]"
                })
                logger.warning(f"[Multimodal] 不支持的文件类型: {file_type}")
    
    # 如果没有任何内容，添加默认文本
    if not content:
        content.append({
            "type": "text",
            "text": "请分析这些文件"
        })
    
    return HumanMessage(content=content)


def extract_attachments_summary(attachments: Optional[List[Dict[str, Any]]]) -> str:
    """提取附件摘要（用于日志）
    
    Args:
        attachments: 文件附件列表
    
    Returns:
        摘要字符串，例如 "2张图片, 1个PDF"
    """
    if not attachments:
        return "无附件"
    
    counts = {}
    for att in attachments:
        file_type = att.get('type', 'unknown')
        counts[file_type] = counts.get(file_type, 0) + 1
    
    parts = []
    type_names = {
        'image': '图片',
        'document': '文档',
        'audio': '音频',
        'video': '视频',
        'unknown': '未知'
    }
    
    for file_type, count in counts.items():
        type_name = type_names.get(file_type, file_type)
        parts.append(f"{count}个{type_name}")
    
    return ", ".join(parts)

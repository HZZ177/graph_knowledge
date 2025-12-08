"""多模态消息构造工具

支持：
- 图片：直接传 URL 给多模态 LLM
- 文档：解析提取文本内容，作为上下文发给 LLM
"""

from typing import List, Dict, Any, Optional
from langchain_core.messages import HumanMessage
from loguru import logger

from backend.app.services.chat.document_parser import (
    parse_document_structured_from_url,
)


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
            
            # 文档类型：标记为待解析（同步版本不解析）
            elif file_type == 'document':
                # 同步版本只添加引用，异步版本会解析内容
                content.append({
                    "type": "text",
                    "text": f"\n[附件: {filename}，需要使用异步版本 build_multimodal_message_async 来解析文档内容]"
                })
                logger.info(f"[Multimodal] 添加文档附件引用: {filename}（请使用异步版本解析）")
            
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


async def build_multimodal_message_async(
    question: str,
    attachments: Optional[List[Dict[str, Any]]] = None,
    max_doc_chars: int = 50000
) -> HumanMessage:
    """构造多模态 HumanMessage（异步版本，支持文档解析）
    
    与同步版本的区别：
    - 文档类型会下载并解析内容，作为文本上下文发给 LLM
    - 图片类型仍然使用 image_url 方式
    
    Args:
        question: 用户问题文本
        attachments: 文件附件列表
        max_doc_chars: 文档内容最大字符数（防止 token 超限）
    
    Returns:
        HumanMessage 对象
    """
    content = []
    
    # 1. 添加文本部分
    if question and question.strip():
        content.append({
            "type": "text",
            "text": question
        })
    
    # 2. 处理文件附件
    if attachments:
        for att in attachments:
            file_type = att.get('type', 'unknown')
            url = att.get('url', '')
            filename = att.get('filename', 'unknown')
            content_type = att.get('content_type', '')
            
            # 图片类型：使用 image_url
            if file_type == 'image':
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": url,
                        "detail": "high"
                    }
                })
                logger.info(f"[Multimodal] 添加图片附件: {filename}")
            
            # 文档类型：下载并解析内容（按页顺序，保留图片位置）
            elif file_type == 'document':
                logger.info(f"[Multimodal] 开始解析文档: {filename}")
                
                try:
                    # 异步下载并结构化解析文档
                    content_blocks = await parse_document_structured_from_url(
                        url=url,
                        content_type=content_type,
                        filename=filename
                    )
                    
                    # 添加文档开始标记
                    content.append({
                        "type": "text",
                        "text": f"\n\n--- 文档: {filename} ---\n"
                    })
                    
                    # 按顺序处理内容块（文本和图片交替，保留位置关系）
                    total_text_chars = 0
                    image_count = 0
                    storage = None
                    
                    for block in content_blocks:
                        if block["type"] == "text":
                            # 文本块：检查长度限制
                            block_text = block["content"]
                            if total_text_chars + len(block_text) > max_doc_chars:
                                # 截断剩余内容
                                remaining = max_doc_chars - total_text_chars
                                if remaining > 100:
                                    block_text = block_text[:remaining] + f"\n\n[文档过长，已截断，共约 {total_text_chars + len(block['content'])} 字符]"
                                    content.append({
                                        "type": "text",
                                        "text": block_text
                                    })
                                break
                            
                            content.append({
                                "type": "text",
                                "text": block_text
                            })
                            total_text_chars += len(block_text)
                            
                        elif block["type"] == "image":
                            # 图片块：上传到 OSS 并添加 URL
                            try:
                                if storage is None:
                                    from backend.app.services.storage import get_storage_service
                                    storage = get_storage_service()
                                
                                page = block.get("page", 0)
                                idx = block.get("index", 0)
                                img_filename = f"{filename}_p{page}_img{idx}.png"
                                
                                _, img_url = await storage.upload_file(
                                    file_bytes=block["data"],
                                    filename=img_filename,
                                    content_type="image/png"
                                )
                                
                                # 添加图片位置说明和图片
                                content.append({
                                    "type": "text",
                                    "text": f"\n[第 {page} 页图片 {idx + 1}]"
                                })
                                content.append({
                                    "type": "image_url",
                                    "image_url": {
                                        "url": img_url,
                                        "detail": "high"
                                    }
                                })
                                image_count += 1
                                logger.debug(f"[Multimodal] 上传文档图片: {img_filename}")
                                
                            except Exception as e:
                                logger.warning(f"[Multimodal] 文档图片上传失败: {e}")
                    
                    # 添加文档结束标记
                    content.append({
                        "type": "text",
                        "text": f"\n--- 文档结束 ---\n"
                    })
                    
                    logger.info(f"[Multimodal] 文档解析完成: {filename}, {total_text_chars} 字符, {image_count} 张图片")
                    
                except Exception as e:
                    logger.error(f"[Multimodal] 文档解析失败: {filename}, {e}")
                    content.append({
                        "type": "text",
                        "text": f"\n[文档 {filename} 解析失败: {e}]"
                    })
            
            # 音频/视频：暂不支持
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
    
    # 将原始附件信息保存到 additional_kwargs，供历史记录恢复使用
    additional_kwargs = {}
    if attachments:
        additional_kwargs["original_attachments"] = attachments
    
    return HumanMessage(content=content, additional_kwargs=additional_kwargs)

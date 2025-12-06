# 多模态文件上传功能开发文档

> **版本**: v1.0  
> **作者**: Graph Knowledge Team  
> **创建日期**: 2024-12-06  
> **目标**: 为 Agent 对话系统增加图片、文档、音频等多模态文件上传能力

---

## 📋 目录

- [功能概述](#功能概述)
- [技术方案](#技术方案)
- [前端实现](#前端实现)
- [后端实现](#后端实现)
- [测试验证](#测试验证)
- [注意事项与限制](#注意事项与限制)
- [扩展规划](#扩展规划)

---

## 功能概述

### 需求背景

当前系统只支持纯文本对话，无法处理：
- 用户上传的截图（错误截图、架构图、流程图）
- 日志文件（完整日志文件而非片段）
- 代码文件（需要审查的代码）
- 文档文件（PDF、Word 等需要分析的文档）

### 功能目标

1. **前端**：支持用户在对话输入框上传文件（图片、文档、音频等）
2. **后端**：将文件内容与用户问题一起传递给 LangChain Agent
3. **Agent**：利用 Vision 模型分析图片，或将文档内容作为上下文
4. **体验**：无缝集成到现有对话流程，支持多文件上传

### 核心优势

✅ **原生 LangChain 支持**：使用 `HumanMessage` 的标准多模态结构  
✅ **无需服务器存储**：文件在前端 Base64 编码，通过 WebSocket 直接传输  
✅ **会话历史兼容**：多模态消息自动保存到 LangGraph Checkpoint  
✅ **多文件支持**：可同时上传多张图片或多个文档  

---

## 技术方案

### 架构设计

```
┌─────────────┐                    ┌─────────────┐                    ┌─────────────┐
│   前端 UI    │                    │   后端 API   │                    │  LLM Agent  │
│             │                    │             │                    │             │
│  1. 用户选择 │  ──WebSocket──▶   │  2. 接收请求 │  ──HumanMessage──▶ │  3. 模型处理 │
│     文件     │      (JSON)        │     解析附件  │     (多模态)       │    Vision   │
│  2. Base64  │                    │  3. 构造消息 │                    │    解析PDF   │
│     编码     │                    │             │                    │             │
│  3. 发送请求 │  ◀──WebSocket──   │  4. 流式返回 │  ◀─────────────   │  4. 生成回答 │
│             │      (SSE)         │             │                    │             │
└─────────────┘                    └─────────────┘                    └─────────────┘
```

### 核心原理

**LangChain 的 `HumanMessage` 支持结构化 content**：

```python
from langchain_core.messages import HumanMessage

# 纯文本消息（现有）
message = HumanMessage(content="这是一个问题")

# 多模态消息（新增）
message = HumanMessage(
    content=[
        {"type": "text", "text": "分析这个截图中的错误"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,/9j/4AAQ..."}}
    ]
)
```

### 数据流转

```
用户文件 (File)
  ↓ FileReader.readAsDataURL()
Base64 字符串
  ↓ WebSocket.send(JSON)
后端接收 (StreamChatRequest.attachments)
  ↓ build_multimodal_message()
HumanMessage(content=[text, image_url, ...])
  ↓ agent.astream_events()
LLM 处理（Vision 模型识别图片/解析文档）
  ↓ WebSocket 流式推送
前端渲染回答
```

---

## 前端实现

### 1. 创建文件上传 Hook

**文件路径**: `frontend/src/hooks/useFileUpload.ts`

```typescript
import { useState } from 'react';
import { message as antdMessage } from 'antd';

export interface FileAttachment {
  type: 'image' | 'document' | 'audio';
  name: string;
  mimeType: string;
  base64Data: string;  // Base64 编码（不含 data:xxx;base64, 前缀）
  size: number;
}

export const useFileUpload = () => {
  const [attachments, setAttachments] = useState<FileAttachment[]>([]);

  /**
   * 处理文件上传：读取文件并转换为 Base64
   */
  const handleFileUpload = async (file: File): Promise<FileAttachment> => {
    // 文件大小限制（10MB）
    const MAX_SIZE = 10 * 1024 * 1024;
    if (file.size > MAX_SIZE) {
      antdMessage.error('文件大小不能超过 10MB');
      throw new Error('文件过大');
    }

    return new Promise((resolve, reject) => {
      const reader = new FileReader();

      reader.onload = () => {
        const base64 = reader.result as string;
        // 移除 data:xxx;base64, 前缀
        const base64Data = base64.split(',')[1];

        const attachment: FileAttachment = {
          type: getFileType(file.type),
          name: file.name,
          mimeType: file.type,
          base64Data: base64Data,
          size: file.size,
        };

        resolve(attachment);
      };

      reader.onerror = () => {
        antdMessage.error('文件读取失败');
        reject(new Error('文件读取失败'));
      };

      reader.readAsDataURL(file);
    });
  };

  /**
   * 根据 MIME 类型判断文件类型
   */
  const getFileType = (mimeType: string): FileAttachment['type'] => {
    if (mimeType.startsWith('image/')) return 'image';
    if (mimeType.startsWith('audio/')) return 'audio';
    return 'document';
  };

  /**
   * 添加附件
   */
  const addAttachment = async (file: File) => {
    try {
      const attachment = await handleFileUpload(file);
      setAttachments(prev => [...prev, attachment]);
      antdMessage.success(`${file.name} 已添加`);
    } catch (error) {
      console.error('文件上传失败:', error);
    }
  };

  /**
   * 移除附件
   */
  const removeAttachment = (index: number) => {
    setAttachments(prev => prev.filter((_, i) => i !== index));
  };

  /**
   * 清空所有附件
   */
  const clearAttachments = () => {
    setAttachments([]);
  };

  return {
    attachments,
    addAttachment,
    removeAttachment,
    clearAttachments,
  };
};
```

### 2. 修改 ChatPage 组件

**文件路径**: `frontend/src/pages/ChatPage.tsx`

#### 2.1 引入依赖

```typescript
import { Upload, Button, Tag } from 'antd';
import { PaperClipOutlined, FileImageOutlined, FileTextOutlined } from '@ant-design/icons';
import { useFileUpload } from '../hooks/useFileUpload';
```

#### 2.2 添加状态和逻辑

```typescript
const ChatPage = () => {
  // ... 现有状态
  const { attachments, addAttachment, removeAttachment, clearAttachments } = useFileUpload();

  /**
   * 发送消息（修改）
   */
  const sendMessage = () => {
    if (!inputValue.trim() && attachments.length === 0) {
      message.error('请输入问题或上传文件');
      return;
    }

    const request = {
      question: inputValue || '请分析这些文件',  // 如果只有文件没有文字，给默认问题
      thread_id: currentThreadId,
      agent_type: selectedAgent,
      log_query: logQuery,  // 日志排查 Agent 需要
      attachments: attachments,  // 新增：附件列表
    };

    ws.send(JSON.stringify(request));

    // 清空输入和附件
    setInputValue('');
    clearAttachments();
  };

  /**
   * Upload 组件配置
   */
  const beforeUpload = (file: File) => {
    addAttachment(file);
    return false;  // 阻止自动上传
  };

  // ... 其他逻辑
};
```

#### 2.3 UI 渲染

```tsx
return (
  <div className="chat-page">
    {/* ... 现有内容 ... */}

    {/* 附件预览区（在输入框上方） */}
    {attachments.length > 0 && (
      <div className="attachments-preview" style={{ 
        padding: '8px 16px', 
        backgroundColor: '#f5f5f5', 
        borderRadius: '4px',
        marginBottom: '8px'
      }}>
        <div style={{ marginBottom: '4px', fontSize: '12px', color: '#666' }}>
          已添加 {attachments.length} 个附件：
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {attachments.map((att, idx) => (
            <Tag
              key={idx}
              closable
              onClose={() => removeAttachment(idx)}
              icon={att.type === 'image' ? <FileImageOutlined /> : <FileTextOutlined />}
            >
              {att.name} ({(att.size / 1024).toFixed(1)} KB)
            </Tag>
          ))}
        </div>
      </div>
    )}

    {/* 输入框区域 */}
    <div className="input-area" style={{ display: 'flex', gap: '8px', alignItems: 'flex-end' }}>
      {/* 附件上传按钮 */}
      <Upload
        beforeUpload={beforeUpload}
        showUploadList={false}
        accept="image/*,.pdf,.txt,.log,.md,.json,.js,.ts,.py,.java"  // 限制文件类型
        multiple  // 支持多文件选择
      >
        <Button icon={<PaperClipOutlined />} title="上传文件" />
      </Upload>

      {/* 文本输入框 */}
      <Input.TextArea
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onPressEnter={(e) => {
          if (!e.shiftKey) {
            e.preventDefault();
            sendMessage();
          }
        }}
        placeholder="输入问题，或上传文件后点击发送..."
        autoSize={{ minRows: 1, maxRows: 4 }}
        style={{ flex: 1 }}
      />

      {/* 发送按钮 */}
      <Button
        type="primary"
        onClick={sendMessage}
        disabled={!inputValue.trim() && attachments.length === 0}
      >
        发送
      </Button>
    </div>
  </div>
);
```

### 3. 支持拖拽和粘贴（可选增强）

```typescript
// 在 ChatPage 中添加拖拽支持
useEffect(() => {
  const handlePaste = (e: ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;

    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile();
        if (file) {
          addAttachment(file);
        }
      }
    }
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    const files = e.dataTransfer?.files;
    if (files) {
      Array.from(files).forEach(file => {
        addAttachment(file);
      });
    }
  };

  const handleDragOver = (e: DragEvent) => {
    e.preventDefault();
  };

  document.addEventListener('paste', handlePaste);
  document.addEventListener('drop', handleDrop);
  document.addEventListener('dragover', handleDragOver);

  return () => {
    document.removeEventListener('paste', handlePaste);
    document.removeEventListener('drop', handleDrop);
    document.removeEventListener('dragover', handleDragOver);
  };
}, [addAttachment]);
```

---

## 后端实现

### 1. 扩展请求 Schema

**文件路径**: `backend/app/schemas/llm.py`

```python
from typing import List, Optional
from pydantic import BaseModel, field_validator

class FileAttachment(BaseModel):
    """文件附件（前端已 Base64 编码）"""
    type: str  # 'image' | 'document' | 'audio'
    name: str
    mimeType: str  # 'image/jpeg', 'application/pdf', 'text/plain', etc.
    base64Data: str  # Base64 编码的文件内容（不含前缀）
    size: int  # 文件大小（字节）
    
    @field_validator('size')
    @classmethod
    def validate_size(cls, v):
        max_size = 10 * 1024 * 1024  # 10MB
        if v > max_size:
            raise ValueError('文件大小不能超过 10MB')
        return v


class StreamChatRequest(BaseModel):
    """流式问答 WebSocket 请求（支持多模态附件）"""
    question: str
    thread_id: Optional[str] = None
    agent_type: str = "knowledge_qa"
    log_query: Optional[LogQueryContext] = None
    attachments: Optional[List[FileAttachment]] = None  # 新增：文件附件列表
```

### 2. 创建多模态消息构造工具

**文件路径**: `backend/app/services/chat/multimodal.py`（新建）

```python
"""多模态消息处理工具"""

import base64
import io
from typing import List, Optional, Dict, Any
from langchain_core.messages import HumanMessage
from backend.app.core.logger import logger


def build_multimodal_message(
    question: str,
    attachments: Optional[List[Dict[str, Any]]] = None
) -> HumanMessage:
    """构造多模态 HumanMessage
    
    Args:
        question: 用户问题文本
        attachments: 文件附件列表，每个元素包含：
            - type: 'image' | 'document' | 'audio'
            - name: 文件名
            - mimeType: MIME 类型
            - base64Data: Base64 编码的文件内容
            - size: 文件大小
    
    Returns:
        LangChain HumanMessage（支持文本 + 图片 + 文档）
    """
    content = []
    
    # 1. 添加文本内容
    content.append({
        "type": "text",
        "text": question
    })
    
    # 2. 处理附件
    if attachments:
        for att in attachments:
            try:
                if att['type'] == 'image':
                    # 图片：直接作为 image_url（Vision 模型支持）
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{att['mimeType']};base64,{att['base64Data']}"
                        }
                    })
                    logger.info(f"已添加图片附件: {att['name']}")
                
                elif att['type'] == 'document':
                    # 文档：解析内容后作为文本
                    text = parse_document(att)
                    if text:
                        content.append({
                            "type": "text",
                            "text": f"\n\n[文档: {att['name']}]\n```\n{text}\n```"
                        })
                        logger.info(f"已解析文档附件: {att['name']}, 长度: {len(text)}")
                    else:
                        logger.warning(f"文档解析失败: {att['name']}")
                
                elif att['type'] == 'audio':
                    # 音频：某些模型支持（如 Gemini 1.5 Pro）
                    # 注意：当前 OpenAI GPT-4o 不支持音频输入，需要转文字
                    logger.warning(f"音频附件需要先转文字: {att['name']}")
            
            except Exception as e:
                logger.error(f"处理附件失败: {att.get('name', 'unknown')}, 错误: {e}")
    
    return HumanMessage(content=content)


def parse_document(attachment: Dict[str, Any]) -> Optional[str]:
    """解析文档内容
    
    Args:
        attachment: 附件信息字典
    
    Returns:
        解析后的文本内容（限制长度），如果解析失败返回 None
    """
    mime_type = attachment['mimeType']
    base64_data = attachment['base64Data']
    name = attachment['name']
    
    try:
        # 解码 Base64
        content_bytes = base64.b64decode(base64_data)
        
        # 根据 MIME 类型处理
        if mime_type == 'application/pdf':
            return parse_pdf(content_bytes)
        
        elif mime_type in ['text/plain', 'text/markdown', 'application/json']:
            # 纯文本类型
            text = content_bytes.decode('utf-8', errors='ignore')
            return truncate_text(text)
        
        elif mime_type in ['text/x-python', 'text/x-java', 'text/javascript']:
            # 代码文件
            text = content_bytes.decode('utf-8', errors='ignore')
            return truncate_text(text)
        
        elif name.endswith(('.log', '.txt', '.md', '.json', '.js', '.ts', '.py', '.java')):
            # 根据文件扩展名判断
            text = content_bytes.decode('utf-8', errors='ignore')
            return truncate_text(text)
        
        else:
            logger.warning(f"不支持的文档类型: {mime_type}")
            return None
    
    except Exception as e:
        logger.error(f"文档解析异常: {name}, 错误: {e}")
        return None


def parse_pdf(content_bytes: bytes) -> str:
    """解析 PDF 内容
    
    Args:
        content_bytes: PDF 文件字节流
    
    Returns:
        提取的文本内容
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.error("缺少 pypdf 依赖，请安装: pip install pypdf")
        return "[PDF 解析失败：缺少 pypdf 依赖]"
    
    try:
        pdf_file = io.BytesIO(content_bytes)
        reader = PdfReader(pdf_file)
        
        text_parts = []
        for page_num, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(f"--- 第 {page_num + 1} 页 ---\n{page_text}")
        
        text = "\n\n".join(text_parts)
        return truncate_text(text)
    
    except Exception as e:
        logger.error(f"PDF 解析失败: {e}")
        return f"[PDF 解析失败: {str(e)}]"


def truncate_text(text: str, max_length: int = 20000) -> str:
    """截断文本到指定长度
    
    Args:
        text: 原始文本
        max_length: 最大长度（字符数）
    
    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    
    truncated = text[:max_length]
    return truncated + f"\n\n[... 内容过长，已截断，原始长度: {len(text)} 字符]"
```

### 3. 修改 chat_service.py

**文件路径**: `backend/app/services/chat/chat_service.py`

#### 3.1 引入依赖

```python
from backend.app.services.chat.multimodal import build_multimodal_message
```

#### 3.2 修改 streaming_chat 函数

```python
async def streaming_chat(
    db: Session,
    question: str,
    websocket: WebSocket,
    thread_id: Optional[str] = None,
    agent_type: str = "knowledge_qa",
    agent_context: Optional[dict] = None,
    attachments: Optional[List[dict]] = None,  # 新增参数
):
    """流式对话（支持多模态）
    
    Args:
        db: 数据库会话
        question: 用户问题
        websocket: WebSocket 连接
        thread_id: 会话 ID
        agent_type: Agent 类型
        agent_context: Agent 上下文配置
        attachments: 文件附件列表（新增）
    """
    try:
        # 0. 记录附件信息
        if attachments:
            logger.info(f"收到 {len(attachments)} 个附件:")
            for att in attachments:
                logger.info(f"  - {att['name']} ({att['type']}, {att['size']} bytes)")
        
        # 1. 生成或使用 thread_id
        if not thread_id:
            thread_id = str(uuid.uuid4())
        
        # 2. 获取 Agent
        registry = AgentRegistry.get_instance()
        agent = registry.get_agent(agent_type, db, agent_context)
        
        # 3. 构造多模态消息（关键修改）
        human_message = build_multimodal_message(question, attachments)
        
        # 4. 构造输入
        input_data = {
            "messages": [human_message]
        }
        
        # 5. 流式调用（与之前逻辑相同）
        config = {
            "configurable": {"thread_id": thread_id},
            "callbacks": [...]
        }
        
        # ... 后续流式处理逻辑不变
        
    except Exception as e:
        logger.error(f"流式对话异常: {e}")
        raise
```

### 4. 修改 WebSocket 接口

**文件路径**: `backend/app/api/v1/llm_chat.py`

```python
@router.websocket("/chat/ws")
async def websocket_chat(websocket: WebSocket):
    """WebSocket 知识图谱问答接口（支持多模态）"""
    await websocket.accept()
    
    # ... 现有逻辑 ...
    
    try:
        data = await websocket.receive_text()
        request = StreamChatRequest.model_validate_json(data)
        
        # 记录附件信息
        if request.attachments:
            logger.info(f"收到 {len(request.attachments)} 个附件")
        
        # 构建 agent_context
        agent_context = None
        if request.agent_type == "log_troubleshoot":
            if not request.log_query:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "error": "日志排查 Agent 需要选择业务线配置",
                }, ensure_ascii=False))
                return
            agent_context = {"log_query": request.log_query.model_dump()}
        
        # 调用流式问答（传入 attachments）
        await streaming_chat(
            db=db,
            question=request.question,
            websocket=websocket,
            thread_id=request.thread_id,
            agent_type=request.agent_type,
            agent_context=agent_context,
            attachments=[att.model_dump() for att in (request.attachments or [])],  # 新增
        )
        
    except Exception as e:
        logger.error(f"WebSocket 异常: {e}")
        # ... 错误处理
```

### 5. 安装依赖

**文件路径**: `backend/requirements.txt`

```txt
# ... 现有依赖 ...

# PDF 解析（新增）
pypdf==4.0.1

# 可选：其他文档格式支持
# python-docx==1.1.0      # Word 文档
# python-pptx==0.6.23     # PowerPoint
# openpyxl==3.1.2         # Excel
```

安装命令：

```bash
cd backend
pip install pypdf
```

---

## 测试验证

### 1. 前端测试

#### 测试步骤

1. **启动前端**
   ```bash
   cd frontend
   npm run dev
   ```

2. **测试图片上传**
   - 点击"附件"按钮，选择图片文件（JPG/PNG）
   - 确认附件预览区显示文件名和大小
   - 输入问题："这张截图中显示了什么错误？"
   - 点击发送，观察消息是否正常发送

3. **测试文档上传**
   - 上传 `.txt` 或 `.log` 文件
   - 输入问题："分析这个日志文件"
   - 发送并观察响应

4. **测试多文件**
   - 同时上传 2-3 个文件
   - 确认所有文件都在预览区显示
   - 发送后确认清空

5. **测试删除附件**
   - 上传文件后点击 Tag 的关闭按钮
   - 确认附件被移除

#### 预期结果

- ✅ 文件上传流程顺畅，无错误提示
- ✅ 附件预览显示正确
- ✅ WebSocket 消息包含 `attachments` 字段
- ✅ 发送后附件清空

### 2. 后端测试

#### 测试步骤

1. **启动后端**
   ```bash
   cd backend
   python app/main.py
   ```

2. **查看日志**
   - 观察控制台输出是否包含附件信息：
     ```
     收到 1 个附件:
       - screenshot.png (image, 45231 bytes)
     已添加图片附件: screenshot.png
     ```

3. **测试 Vision 模型**
   - 确保配置了支持 Vision 的模型（GPT-4o, Claude 3.5 Sonnet）
   - 上传截图并提问
   - 观察 Agent 是否能识别图片内容

4. **测试 PDF 解析**
   - 上传 PDF 文件
   - 观察日志是否显示解析成功
   - 检查 Agent 回答是否基于 PDF 内容

#### 预期结果

- ✅ 后端能接收并解析 `attachments` 字段
- ✅ `build_multimodal_message` 正确构造 HumanMessage
- ✅ Vision 模型能识别图片内容
- ✅ PDF 文档能正确解析为文本

### 3. 端到端测试用例

| 测试场景 | 操作步骤 | 预期结果 |
|---------|---------|---------|
| **截图分析** | 上传错误截图 + 问"这是什么错误" | Agent 识别截图内容并分析错误原因 |
| **日志分析** | 上传 `.log` 文件 + 问"有什么异常" | Agent 分析日志内容，指出异常信息 |
| **代码审查** | 上传 `.py` 文件 + 问"有什么问题" | Agent 审查代码并给出建议 |
| **PDF 问答** | 上传 PDF + 问"总结这个文档" | Agent 基于 PDF 内容生成摘要 |
| **多图对比** | 上传 2 张截图 + 问"对比这两张图" | Agent 对比两张图片的差异 |

---

## 注意事项与限制

### ⚠️ 重要限制

1. **文件大小限制**
   - 单文件最大 **10MB**
   - 建议图片压缩后再上传
   - 大型 PDF 建议提取关键页面

2. **Base64 编码开销**
   - Base64 会增加 33% 数据大小
   - 10MB 文件编码后约 13.3MB
   - WebSocket 消息大小受浏览器限制（通常 16MB）

3. **模型支持**
   - **图片识别**：需要 Vision 模型（GPT-4o, Claude 3.5 Sonnet, Gemini Pro Vision）
   - **音频**：当前不支持，需要先转文字
   - **视频**：当前不支持

4. **文档解析限制**
   - PDF：只提取文本，不处理图片和表格
   - Word/Excel：需要额外依赖，暂未实现
   - 复杂排版可能解析不准确

5. **性能影响**
   - 多个大文件会增加 WebSocket 传输时间
   - PDF 解析需要额外时间
   - Vision 模型调用比纯文本慢

### 🔐 安全建议

1. **文件类型校验**
   - 前端限制 `accept` 属性
   - 后端验证 MIME 类型
   - 防止恶意文件上传

2. **文件内容检查**
   - 检测病毒（如集成 ClamAV）
   - 过滤敏感信息
   - 限制 PDF 页数

3. **敏感数据保护**
   - 文件不持久化存储（使用 Base64 直传）
   - 对话历史加密存储
   - 生产环境使用 HTTPS + WSS

---

## 扩展规划

### 阶段一：MVP（当前方案）

- ✅ 图片上传 + Vision 分析
- ✅ 文本文档上传（TXT, LOG, MD, JSON）
- ✅ PDF 解析
- ✅ 前端附件预览和管理

### 阶段二：功能增强

- 🔜 **Word/Excel 支持**：集成 `python-docx` 和 `openpyxl`
- 🔜 **音频转文字**：集成 Whisper API
- 🔜 **OCR 支持**：对扫描件 PDF 进行 OCR 识别
- 🔜 **压缩上传**：前端压缩图片后再编码
- 🔜 **拖拽上传**：支持文件拖拽到对话框

### 阶段三：企业级优化

- 🔜 **OSS 直传**：大文件上传到对象存储，传 URL 给后端
- 🔜 **异步处理**：大型文档异步解析，避免阻塞
- 🔜 **缓存机制**：相同文件避免重复解析
- 🔜 **病毒扫描**：集成安全检测
- 🔜 **审计日志**：记录所有文件上传操作

---

## 附录

### A. 支持的文件类型

| 类型 | 扩展名 | MIME 类型 | 处理方式 | 模型要求 |
|------|-------|-----------|---------|---------|
| **图片** | `.jpg`, `.png`, `.webp`, `.gif` | `image/*` | Base64 直传 | Vision 模型 |
| **PDF** | `.pdf` | `application/pdf` | pypdf 提取文本 | 任意 |
| **文本** | `.txt`, `.md`, `.log` | `text/plain` | UTF-8 解码 | 任意 |
| **JSON** | `.json` | `application/json` | UTF-8 解码 | 任意 |
| **代码** | `.py`, `.js`, `.ts`, `.java`, etc. | `text/x-*` | UTF-8 解码 | 任意 |

### B. 错误处理清单

| 错误场景 | 处理方式 |
|---------|---------|
| 文件过大 | 前端拦截 + 提示用户 |
| 格式不支持 | 前端 `accept` 限制 + 后端返回友好提示 |
| Base64 解码失败 | 后端 try-catch + 记录日志 + 跳过该附件 |
| PDF 解析失败 | 返回错误提示，不阻断对话 |
| Vision 模型不可用 | 提示用户"当前模型不支持图片" |
| WebSocket 消息过大 | 前端限制文件数量 + 总大小 |

### C. 调试技巧

1. **查看 WebSocket 消息**
   ```javascript
   // 浏览器控制台
   ws.addEventListener('message', (event) => {
     console.log('收到消息:', event.data);
   });
   ```

2. **查看 Base64 编码**
   ```javascript
   console.log('附件大小:', attachment.base64Data.length);
   console.log('前100字符:', attachment.base64Data.substring(0, 100));
   ```

3. **后端日志级别**
   ```python
   # 临时调整日志级别查看详细信息
   logger.setLevel("DEBUG")
   ```

---

## 联系与反馈

- **技术负责人**: [Your Name]
- **文档版本**: v1.0
- **最后更新**: 2024-12-06

如有问题或建议，请提交 Issue 或联系开发团队。

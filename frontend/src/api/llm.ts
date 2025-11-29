/**
 * LLM Chat API - 知识图谱问答
 * 
 * 基于 WebSocket 的流式问答接口（LangChain Agent）
 * 支持多轮对话，通过 thread_id 管理会话历史
 */

import { getWebSocketUrl, API_BASE_PATH } from './config'

// ==================== 类型定义 ====================

export interface ChatMessage {
  role: 'user' | 'assistant' | 'tool'
  content: string
  tool_name?: string  // 仅 tool 类型
  tool_calls?: Array<{ name: string; args: Record<string, unknown> }>  // 仅 assistant 调用工具时
}

export interface ChatRequest {
  question: string
  thread_id?: string  // 会话 ID，为空则创建新会话
}

/** 工具调用信息 */
export interface ToolCallInfo {
  name: string
  output_length: number
}

/** WebSocket 消息类型 */
export interface ChatStreamMessage {
  type: 'start' | 'stream' | 'tool_start' | 'tool_end' | 'result' | 'error'
  // start 消息
  request_id?: string
  thread_id?: string
  // stream 消息
  content?: string
  // tool_start 消息
  tool_name?: string
  tool_input?: Record<string, unknown>
  // result 消息
  tool_calls?: ToolCallInfo[]
  // error 消息
  error?: string
}

export interface ChatCallbacks {
  /** 问答开始 */
  onStart?: (requestId: string, threadId: string) => void
  /** 流式内容片段 */
  onStream?: (content: string) => void
  /** 工具开始调用 */
  onToolStart?: (toolName: string, toolInput: Record<string, unknown>) => void
  /** 工具调用结束 */
  onToolEnd?: (toolName: string) => void
  /** 最终结果 */
  onResult?: (content: string, threadId: string, toolCalls: ToolCallInfo[]) => void
  /** 错误 */
  onError?: (error: string) => void
  /** 连接关闭 */
  onClose?: () => void
}

// ==================== URL ====================

// WebSocket URL（动态获取，支持代理）
export const getChatWsUrl = () => getWebSocketUrl('/api/v1/llm/chat/ws')
export const getRegenerateWsUrl = () => getWebSocketUrl('/api/v1/llm/chat/regenerate/ws')

// HTTP 基础路径，使用相对路径以便通过 dev proxy 或同域部署
const HTTP_BASE_PATH = `${API_BASE_PATH}/llm`

// 重新生成请求
export interface RegenerateRequest {
  thread_id: string
  user_msg_index: number  // 第几个用户消息（从0开始）
}

// ==================== Chat WebSocket 客户端 ====================

export class ChatClient {
  private ws: WebSocket | null = null
  private callbacks: ChatCallbacks = {}
  
  /**
   * 开始问答
   */
  start(request: ChatRequest, callbacks: ChatCallbacks): void {
    this.callbacks = callbacks
    
    // 关闭已有连接
    this.stop()
    
    // 创建新连接
    this.ws = new WebSocket(getChatWsUrl())
    
    this.ws.onopen = () => {
      this.ws?.send(JSON.stringify(request))
    }
    
    this.ws.onmessage = (event) => {
      try {
        const message: ChatStreamMessage = JSON.parse(event.data)
        this.handleMessage(message)
      } catch (e) {
        console.error('解析 WebSocket 消息失败:', e)
        this.callbacks.onError?.('消息解析失败')
      }
    }
    
    this.ws.onerror = (event) => {
      console.error('WebSocket 错误:', event)
      this.callbacks.onError?.('WebSocket 连接错误')
    }
    
    this.ws.onclose = () => {
      this.ws = null
      this.callbacks.onClose?.()
    }
  }
  
  /**
   * 停止/取消请求
   */
  stop(): void {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }
  
  /**
   * 是否已连接
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
  }
  
  /**
   * 处理消息
   */
  private handleMessage(message: ChatStreamMessage): void {
    switch (message.type) {
      case 'start':
        this.callbacks.onStart?.(
          message.request_id || '',
          message.thread_id || ''
        )
        break
        
      case 'stream':
        this.callbacks.onStream?.(message.content || '')
        break
        
      case 'tool_start':
        this.callbacks.onToolStart?.(
          message.tool_name || '',
          message.tool_input || {}
        )
        break
        
      case 'tool_end':
        this.callbacks.onToolEnd?.(message.tool_name || '')
        break
        
      case 'result':
        this.callbacks.onResult?.(
          message.content || '',
          message.thread_id || '',
          message.tool_calls || []
        )
        break
        
      case 'error':
        this.callbacks.onError?.(message.error || '未知错误')
        break
    }
  }
}

// ==================== 便捷函数 ====================

/**
 * 创建 Chat 客户端
 */
export function createChatClient(): ChatClient {
  return new ChatClient()
}


// ==================== Regenerate WebSocket 客户端 ====================

export class RegenerateClient {
  private ws: WebSocket | null = null
  private callbacks: ChatCallbacks = {}
  
  /**
   * 开始重新生成
   */
  start(request: RegenerateRequest, callbacks: ChatCallbacks): void {
    this.callbacks = callbacks
    this.stop()
    
    this.ws = new WebSocket(getRegenerateWsUrl())
    
    this.ws.onopen = () => {
      this.ws?.send(JSON.stringify(request))
    }
    
    this.ws.onmessage = (event) => {
      try {
        const message: ChatStreamMessage = JSON.parse(event.data)
        this.handleMessage(message)
      } catch (e) {
        console.error('解析 WebSocket 消息失败:', e)
        this.callbacks.onError?.('消息解析失败')
      }
    }
    
    this.ws.onerror = (event) => {
      console.error('WebSocket 错误:', event)
      this.callbacks.onError?.('WebSocket 连接错误')
    }
    
    this.ws.onclose = () => {
      this.ws = null
      this.callbacks.onClose?.()
    }
  }
  
  stop(): void {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }
  
  private handleMessage(message: ChatStreamMessage): void {
    switch (message.type) {
      case 'start':
        this.callbacks.onStart?.(message.request_id || '', message.thread_id || '')
        break
      case 'stream':
        this.callbacks.onStream?.(message.content || '')
        break
      case 'tool_start':
        this.callbacks.onToolStart?.(message.tool_name || '', message.tool_input || {})
        break
      case 'tool_end':
        this.callbacks.onToolEnd?.(message.tool_name || '')
        break
      case 'result':
        this.callbacks.onResult?.(message.content || '', message.thread_id || '', message.tool_calls || [])
        break
      case 'error':
        this.callbacks.onError?.(message.error || '未知错误')
        break
    }
  }
}

export function createRegenerateClient(): RegenerateClient {
  return new RegenerateClient()
}


// ==================== HTTP 辅助函数 ====================

export interface ConversationMetadata {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export async function listConversations(): Promise<ConversationMetadata[]> {
  const resp = await fetch(`${HTTP_BASE_PATH}/conversations`)
  if (!resp.ok) throw new Error('获取会话列表失败')
  return await resp.json()
}

export async function deleteConversation(threadId: string): Promise<void> {
  const resp = await fetch(`${HTTP_BASE_PATH}/conversation/${encodeURIComponent(threadId)}`, {
    method: 'DELETE',
  })
  if (!resp.ok) throw new Error('删除会话失败')
}

export async function fetchConversationHistory(threadId: string): Promise<ChatMessage[]> {
  const resp = await fetch(`${HTTP_BASE_PATH}/conversation/${encodeURIComponent(threadId)}`)
  if (!resp.ok) {
    throw new Error(`获取会话历史失败: ${resp.status}`)
  }
  const data = await resp.json() as { thread_id: string; messages: ChatMessage[] }
  return data.messages || []
}

export async function generateConversationTitle(threadId: string): Promise<string> {
  const resp = await fetch(`${HTTP_BASE_PATH}/conversation/${encodeURIComponent(threadId)}/title`, {
    method: 'POST',
  })
  if (!resp.ok) {
    throw new Error(`生成标题失败: ${resp.status}`)
  }
  const data = await resp.json() as { thread_id: string; title: string }
  return data.title
}

export async function truncateConversation(threadId: string, keepPairs: number): Promise<void> {
  const resp = await fetch(`${HTTP_BASE_PATH}/conversation/${encodeURIComponent(threadId)}/truncate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keep_pairs: keepPairs }),
  })
  if (!resp.ok) {
    throw new Error(`截断对话失败: ${resp.status}`)
  }
}

/**
 * 流式API封装
 * 
 * 提供WebSocket流式接口的统一封装
 */

// ==================== 类型定义 ====================

export interface StreamMessage {
  type: 'start' | 'chunk' | 'done' | 'error'
  content?: string
  request_id?: string
  error?: string
  metadata?: Record<string, any>
}

export interface StreamChatRequest {
  question: string
  process_id?: string
}

export interface StreamCallbacks {
  onStart?: (requestId: string) => void
  onChunk?: (content: string, message: StreamMessage) => void
  onDone?: (fullContent: string, metadata?: Record<string, any>) => void
  onError?: (error: string) => void
}

// ==================== WebSocket URL ====================

const WS_BASE_URL = 'ws://localhost:8000/api/v1'

export const WS_ENDPOINTS = {
  chatStream: `${WS_BASE_URL}/llm/chat/ws/stream`,
  skeletonGenerate: `${WS_BASE_URL}/llm/skeleton/ws/generate`,
}

// ==================== 通用WebSocket流式客户端 ====================

export class StreamingClient {
  private ws: WebSocket | null = null
  private callbacks: StreamCallbacks = {}
  private fullContent: string = ''
  
  constructor(private url: string) {}
  
  /**
   * 开始流式请求
   */
  start<T extends object>(payload: T, callbacks: StreamCallbacks): void {
    this.callbacks = callbacks
    this.fullContent = ''
    
    // 关闭已有连接
    this.stop()
    
    // 创建新连接
    this.ws = new WebSocket(this.url)
    
    this.ws.onopen = () => {
      this.ws?.send(JSON.stringify(payload))
    }
    
    this.ws.onmessage = (event) => {
      try {
        const message: StreamMessage = JSON.parse(event.data)
        this.handleMessage(message)
      } catch (e) {
        console.error('解析WebSocket消息失败:', e)
        this.callbacks.onError?.('消息解析失败')
      }
    }
    
    this.ws.onerror = (event) => {
      console.error('WebSocket错误:', event)
      this.callbacks.onError?.('WebSocket连接错误')
    }
    
    this.ws.onclose = () => {
      this.ws = null
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
   * 处理消息
   */
  private handleMessage(message: StreamMessage): void {
    switch (message.type) {
      case 'start':
        this.callbacks.onStart?.(message.request_id || '')
        break
        
      case 'chunk':
        if (message.content) {
          this.fullContent += message.content
          this.callbacks.onChunk?.(message.content, message)
        }
        break
        
      case 'done':
        this.callbacks.onDone?.(this.fullContent, message.metadata)
        break
        
      case 'error':
        this.callbacks.onError?.(message.error || '未知错误')
        break
    }
  }
}

// ==================== 便捷函数 ====================

/**
 * 创建流式Chat客户端
 */
export function createChatStreamClient(): StreamingClient {
  return new StreamingClient(WS_ENDPOINTS.chatStream)
}

/**
 * 流式Chat请求（Promise风格，返回完整响应）
 */
export function streamChat(
  question: string,
  processId?: string,
  onChunk?: (content: string) => void,
): Promise<string> {
  return new Promise((resolve, reject) => {
    const client = new StreamingClient(WS_ENDPOINTS.chatStream)
    
    client.start<StreamChatRequest>(
      { question, process_id: processId },
      {
        onChunk: (content) => onChunk?.(content),
        onDone: (fullContent) => {
          resolve(fullContent)
        },
        onError: (error) => {
          reject(new Error(error))
        },
      }
    )
  })
}

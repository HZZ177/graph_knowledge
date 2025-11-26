/**
 * 通用WebSocket流式响应Hook
 * 
 * 提供：
 * 1. WebSocket连接管理
 * 2. 流式内容累积
 * 3. 状态管理（连接中、流式中、完成、错误）
 * 4. 自动重连（可选）
 */

import { useState, useCallback, useRef, useEffect } from 'react'

// ==================== 类型定义 ====================

export interface StreamMessage {
  type: 'start' | 'chunk' | 'done' | 'error'
  content?: string
  request_id?: string
  error?: string
  metadata?: Record<string, any>
}

export type StreamStatus = 'idle' | 'connecting' | 'streaming' | 'done' | 'error'

export interface UseWebSocketStreamOptions {
  /** WebSocket URL */
  url: string
  /** 收到chunk时的回调 */
  onChunk?: (content: string, message: StreamMessage) => void
  /** 流式完成时的回调 */
  onDone?: (fullContent: string, metadata?: Record<string, any>) => void
  /** 发生错误时的回调 */
  onError?: (error: string) => void
  /** 连接建立时的回调 */
  onConnect?: () => void
  /** 连接关闭时的回调 */
  onClose?: () => void
}

export interface UseWebSocketStreamReturn {
  /** 累积的完整内容 */
  content: string
  /** 当前状态 */
  status: StreamStatus
  /** 错误信息 */
  error: string | null
  /** 是否正在流式传输 */
  isStreaming: boolean
  /** 请求ID */
  requestId: string | null
  /** 开始流式请求 */
  start: <T extends object>(payload: T) => void
  /** 停止/取消请求 */
  stop: () => void
  /** 重置状态 */
  reset: () => void
}

// ==================== Hook实现 ====================

export function useWebSocketStream(options: UseWebSocketStreamOptions): UseWebSocketStreamReturn {
  const { url, onChunk, onDone, onError, onConnect, onClose } = options
  
  const [content, setContent] = useState('')
  const [status, setStatus] = useState<StreamStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [requestId, setRequestId] = useState<string | null>(null)
  
  const wsRef = useRef<WebSocket | null>(null)
  const contentRef = useRef('')  // 用于在回调中获取最新content
  
  // 同步contentRef
  useEffect(() => {
    contentRef.current = content
  }, [content])
  
  // 清理WebSocket
  const cleanup = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])
  
  // 组件卸载时清理
  useEffect(() => {
    return cleanup
  }, [cleanup])
  
  // 重置状态
  const reset = useCallback(() => {
    cleanup()
    setContent('')
    setStatus('idle')
    setError(null)
    setRequestId(null)
    contentRef.current = ''
  }, [cleanup])
  
  // 停止请求
  const stop = useCallback(() => {
    cleanup()
    if (status === 'streaming' || status === 'connecting') {
      setStatus('idle')
    }
  }, [cleanup, status])
  
  // 开始流式请求
  const start = useCallback(<T extends object>(payload: T) => {
    // 重置状态
    setContent('')
    setError(null)
    setStatus('connecting')
    contentRef.current = ''
    
    // 关闭已有连接
    cleanup()
    
    // 创建新连接
    const ws = new WebSocket(url)
    wsRef.current = ws
    
    ws.onopen = () => {
      onConnect?.()
      // 发送请求数据
      ws.send(JSON.stringify(payload))
    }
    
    ws.onmessage = (event) => {
      try {
        const message: StreamMessage = JSON.parse(event.data)
        
        switch (message.type) {
          case 'start':
            setStatus('streaming')
            setRequestId(message.request_id || null)
            break
            
          case 'chunk':
            if (message.content) {
              setContent(prev => prev + message.content)
              contentRef.current += message.content
              onChunk?.(message.content, message)
            }
            break
            
          case 'done':
            setStatus('done')
            onDone?.(contentRef.current, message.metadata)
            break
            
          case 'error':
            setStatus('error')
            setError(message.error || '未知错误')
            onError?.(message.error || '未知错误')
            break
        }
      } catch (e) {
        console.error('解析WebSocket消息失败:', e)
        setStatus('error')
        setError('消息解析失败')
        onError?.('消息解析失败')
      }
    }
    
    ws.onerror = (event) => {
      console.error('WebSocket错误:', event)
      setStatus('error')
      setError('WebSocket连接错误')
      onError?.('WebSocket连接错误')
    }
    
    ws.onclose = () => {
      wsRef.current = null
      onClose?.()
    }
  }, [url, cleanup, onChunk, onDone, onError, onConnect, onClose])
  
  return {
    content,
    status,
    error,
    isStreaming: status === 'streaming',
    requestId,
    start,
    stop,
    reset,
  }
}

// ==================== 便捷Hook ====================

/**
 * 流式Chat Hook - 专门用于chat/ws/stream接口
 */
export interface UseChatStreamOptions {
  onChunk?: (content: string) => void
  onDone?: (fullContent: string) => void
  onError?: (error: string) => void
}

export interface ChatStreamPayload {
  question: string
  process_id?: string
}

export function useChatStream(options: UseChatStreamOptions = {}) {
  const wsUrl = 'ws://localhost:8000/api/v1/llm/chat/ws/stream'
  
  const stream = useWebSocketStream({
    url: wsUrl,
    onChunk: (content) => options.onChunk?.(content),
    onDone: (fullContent) => options.onDone?.(fullContent),
    onError: (error) => options.onError?.(error),
  })
  
  const ask = useCallback((question: string, processId?: string) => {
    const payload: ChatStreamPayload = {
      question,
      process_id: processId,
    }
    stream.start(payload)
  }, [stream])
  
  return {
    ...stream,
    ask,
  }
}

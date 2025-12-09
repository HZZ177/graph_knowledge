/**
 * 智能测试助手 API
 * 
 * 提供测试会话管理和 WebSocket 连接
 */

import http from './http'

// ==================== 类型定义 ====================

/** 创建会话请求 */
export interface CreateSessionRequest {
  project_name: string
  requirement_id: string
  requirement_name: string
}

/** 创建会话响应 */
export interface CreateSessionResponse {
  session_id: string
}

/** 测试会话信息 */
export interface TestingSession {
  id: string
  title: string
  project_name: string
  requirement_id: string
  status: string
  current_phase: string
  thread_id_analysis?: string
  thread_id_plan?: string
  thread_id_generate?: string
  created_at: string
  updated_at: string
}

/** 测试结果 */
export interface TestingResults {
  session_id: string
  requirement_summary: Record<string, unknown> | null
  test_plan: Record<string, unknown> | null
  test_cases: Record<string, unknown> | null
}

/** WebSocket 配置 */
export interface TestingWSConfig {
  session_id: string
  requirement_id: string
  project_name: string
  requirement_name: string
}

// ==================== REST API ====================

/**
 * 创建测试会话
 */
export async function createTestingSession(
  request: CreateSessionRequest
): Promise<CreateSessionResponse> {
  const response = await http.post('/testing/sessions', request)
  return response.data
}

/**
 * 获取测试会话列表
 */
export async function listTestingSessions(
  limit: number = 20,
  offset: number = 0
): Promise<{ sessions: TestingSession[]; total: number }> {
  const response = await http.get('/testing/sessions', {
    params: { limit, offset }
  })
  return response.data
}

/**
 * 获取测试会话详情
 */
export async function getTestingSession(
  sessionId: string
): Promise<TestingSession> {
  const response = await http.get(`/testing/sessions/${sessionId}`)
  return response.data
}

/**
 * 获取测试结果
 */
export async function getTestingResults(
  sessionId: string
): Promise<TestingResults> {
  const response = await http.get(`/testing/sessions/${sessionId}/results`)
  return response.data
}

// ==================== WebSocket ====================

/**
 * 创建测试 WebSocket 客户端
 */
export function createTestingWSClient(
  config: TestingWSConfig,
  handlers: {
    onStart?: (sessionId: string) => void
    onStream?: (content: string) => void
    onToolStart?: (msg: Record<string, unknown>) => void
    onToolEnd?: (msg: Record<string, unknown>) => void
    onPhaseChanged?: (phase: string) => void
    onResult?: (sessionId: string, status: string) => void
    onError?: (error: string) => void
    onClose?: () => void
  }
): {
  connect: () => void
  close: () => void
} {
  let ws: WebSocket | null = null
  
  const connect = () => {
    // 构建 WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.hostname
    const port = '8000' // 后端端口
    const url = `${protocol}//${host}:${port}/api/v1/testing/generate`
    
    ws = new WebSocket(url)
    
    ws.onopen = () => {
      console.log('[TestingWS] 连接已建立')
      // 发送配置消息
      ws?.send(JSON.stringify(config))
    }
    
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        
        switch (msg.type) {
          case 'start':
            handlers.onStart?.(msg.session_id)
            break
          case 'stream':
            handlers.onStream?.(msg.content)
            break
          case 'tool_start':
            handlers.onToolStart?.(msg)
            break
          case 'tool_end':
            handlers.onToolEnd?.(msg)
            break
          case 'phase_changed':
            handlers.onPhaseChanged?.(msg.phase)
            break
          case 'result':
            handlers.onResult?.(msg.session_id, msg.status)
            break
          case 'error':
            handlers.onError?.(msg.error || msg.message)
            break
        }
      } catch (e) {
        console.error('[TestingWS] 消息解析失败:', e)
      }
    }
    
    ws.onerror = (error) => {
      console.error('[TestingWS] 连接错误:', error)
      handlers.onError?.('WebSocket 连接错误')
    }
    
    ws.onclose = () => {
      console.log('[TestingWS] 连接已关闭')
      handlers.onClose?.()
    }
  }
  
  const close = () => {
    if (ws) {
      ws.close()
      ws = null
    }
  }
  
  return { connect, close }
}

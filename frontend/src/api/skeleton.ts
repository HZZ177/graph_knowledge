/**
 * 骨架生成API - WebSocket流式接口
 */

import http from './http'

// ==================== 类型定义 ====================

export interface SkeletonGenerateRequest {
  business_name: string
  business_description: string
  channel?: string
  structured_logs?: string
  api_captures?: string
  known_systems?: string[]
  known_data_resources?: string[]
}

export interface AgentStreamChunk {
  type: 'agent_start' | 'stream' | 'agent_end' | 'result' | 'error'
  agent_name: string
  agent_index: number
  timestamp: string
  
  // stream 类型
  content?: string
  
  // agent_start 类型
  agent_description?: string
  
  // agent_end 类型
  agent_output?: string
  duration_ms?: number
  
  // result 类型
  canvas_data?: CanvasData
  
  // error 类型
  error?: string
}

export interface CanvasData {
  process_id: string
  process: {
    process_id: string
    name: string
    description?: string
    channel?: string
    entrypoints?: string[]
  }
  steps: Array<{
    step_id: string
    name: string
    description?: string
    step_type?: string
  }>
  edges: Array<{
    from_step_id: string
    to_step_id: string
    edge_type?: string
    condition?: string
    label?: string
  }>
  implementations: Array<{
    impl_id: string
    name: string
    type?: string
    system?: string
    description?: string
    code_ref?: string
  }>
  step_impl_links: Array<{
    step_id: string
    impl_id: string
  }>
  data_resources: Array<{
    resource_id: string
    name: string
    type?: string
    system?: string
    description?: string
  }>
  impl_data_links: Array<{
    impl_id: string
    resource_id: string
    access_type?: string
    access_pattern?: string
  }>
  impl_links: Array<{
    from_impl_id: string
    to_impl_id: string
    edge_type?: string
  }>
}

// ==================== WebSocket连接管理 ====================

export type ChunkHandler = (chunk: AgentStreamChunk) => void
export type ErrorHandler = (error: string) => void
export type CloseHandler = () => void

export interface SkeletonWebSocketOptions {
  onChunk: ChunkHandler
  onError?: ErrorHandler
  onClose?: CloseHandler
}

/**
 * 创建骨架生成WebSocket连接
 */
export function createSkeletonWebSocket(
  request: SkeletonGenerateRequest,
  options: SkeletonWebSocketOptions
): WebSocket {
  // 构建WebSocket URL - 使用后端地址
  const wsUrl = 'ws://localhost:8000/api/v1/skeleton/ws/generate'
  
  const ws = new WebSocket(wsUrl)
  
  ws.onopen = () => {
    // 连接成功后发送请求数据
    ws.send(JSON.stringify(request))
  }
  
  ws.onmessage = (event) => {
    try {
      const chunk: AgentStreamChunk = JSON.parse(event.data)
      options.onChunk(chunk)
    } catch (e) {
      console.error('解析WebSocket消息失败:', e)
      options.onError?.('消息解析失败')
    }
  }
  
  ws.onerror = (event) => {
    console.error('WebSocket错误:', event)
    options.onError?.('WebSocket连接错误')
  }
  
  ws.onclose = () => {
    options.onClose?.()
  }
  
  return ws
}

// ==================== HTTP接口 ====================

/**
 * 确认骨架，写入数据库
 */
export async function confirmSkeleton(canvasData: CanvasData): Promise<CanvasData> {
  const res = await http.post<CanvasData>('/skeleton/confirm', canvasData)
  return res.data
}

/**
 * 非流式骨架预览（备用）
 */
export async function previewSkeleton(request: SkeletonGenerateRequest): Promise<CanvasData> {
  const res = await http.post<CanvasData>('/skeleton/preview', request)
  return res.data
}

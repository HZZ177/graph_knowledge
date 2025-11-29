/**
 * API 配置 - 统一管理接口地址
 */

// HTTP 基础路径（相对路径，走 Vite 代理）
export const API_BASE_PATH = '/api/v1'

/**
 * 获取 WebSocket URL
 * 开发环境走 Vite 代理，生产环境使用当前域名
 */
export function getWebSocketUrl(path: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return `${protocol}//${host}${path}`
}

// WebSocket 端点
export const WS_ENDPOINTS = {
  chat: () => getWebSocketUrl('/api/v1/llm/chat/ws'),
  chatStream: () => getWebSocketUrl('/api/v1/llm/chat/ws/stream'),
  skeletonGenerate: () => getWebSocketUrl('/api/v1/llm/skeleton/ws/generate'),
}

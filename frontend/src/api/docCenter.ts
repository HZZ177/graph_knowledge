/**
 * 文档中心 API 客户端
 */

import { API_BASE_PATH, getWebSocketUrl } from './config'
import type {
  TreeNode,
  SourceDocument,
  LocalDocument,
  DocumentListResponse,
  SyncRequest,
  SyncResult,
  IndexRequest,
  IndexTask,
  QueueStatus,
  IndexProgressMessage,
  QueueStatusMessage,
  SyncProgressMessage,
} from '../types/docCenter'

const BASE_URL = `${API_BASE_PATH}/doc-center`

// ============== REST API ==============

/**
 * 从帮助中心同步目录结构和文档列表到本地
 */
export async function syncFromHelpCenter(): Promise<{ folders_synced: number; documents_synced: number }> {
  const res = await fetch(`${BASE_URL}/sync`, { method: 'POST' })
  const data = await res.json()
  if (data.code !== 0) throw new Error(data.message)
  return data.data
}

/**
 * 获取本地目录树
 */
export async function getDirectoryTree(): Promise<TreeNode[]> {
  const res = await fetch(`${BASE_URL}/tree`)
  const data = await res.json()
  if (data.code !== 0) throw new Error(data.message)
  return data.data
}

/**
 * 获取本地文档列表
 */
export async function getDocuments(params: {
  parent_id?: string
  sync_status?: string[]
  index_status?: string[]
  keyword?: string
  page?: number
  page_size?: number
}): Promise<DocumentListResponse> {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) {
      if (Array.isArray(value)) {
        // 数组参数用逗号分隔
        if (value.length > 0) searchParams.set(key, value.join(','))
      } else {
        searchParams.set(key, String(value))
      }
    }
  })
  
  const res = await fetch(`${BASE_URL}/documents?${searchParams}`)
  const data = await res.json()
  if (data.code !== 0) throw new Error(data.message)
  return data.data
}

/**
 * 获取文档详情
 */
export async function getDocumentDetail(docId: string): Promise<LocalDocument> {
  const res = await fetch(`${BASE_URL}/documents/${docId}`)
  const data = await res.json()
  if (data.code !== 0) throw new Error(data.message)
  return data.data
}

/**
 * 获取文档内容
 */
export async function getDocumentContent(docId: string): Promise<string> {
  const res = await fetch(`${BASE_URL}/documents/${docId}/content`)
  const data = await res.json()

  // 无内容视为正常情况
  if (res.status === 404) return ''

  // 兼容后端错误返回格式
  if (!res.ok) {
    throw new Error(data?.detail || data?.message || `HTTP ${res.status}`)
  }
  if (data.code !== 0) throw new Error(data.message)
  return data.data.content
}

/**
 * 同步单个文档内容（下载内容、处理图片）
 */
export async function syncDocumentContent(docId: string): Promise<SyncResult> {
  const res = await fetch(`${BASE_URL}/documents/${docId}/sync-content`, {
    method: 'POST',
  })
  const data = await res.json()
  if (data.code !== 0) throw new Error(data.message)
  return data.data
}

/**
 * 创建索引任务
 */
export async function createIndexTasks(
  documentIds: string[],
  priority: number = 0
): Promise<{ tasks: IndexTask[] }> {
  const res = await fetch(`${BASE_URL}/index`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_ids: documentIds, priority }),
  })
  const data = await res.json()
  if (data.code !== 0) throw new Error(data.message)
  return data.data
}

/**
 * 获取索引队列状态
 */
export async function getIndexQueueStatus(): Promise<QueueStatus> {
  const res = await fetch(`${BASE_URL}/index/status`)
  const data = await res.json()
  if (data.code !== 0) throw new Error(data.message)
  return data.data
}

/**
 * 手动触发队列处理
 */
export async function triggerProcessQueue(): Promise<void> {
  const res = await fetch(`${BASE_URL}/index/process`, { method: 'POST' })
  const data = await res.json()
  if (data.code !== 0) throw new Error(data.message)
}

/**
 * 取消排队中的索引任务
 */
export async function cancelIndexTask(docId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/index/${docId}`, { method: 'DELETE' })
  const data = await res.json()
  if (data.code !== 0) throw new Error(data.message || data.detail)
}

// ============== WebSocket ==============

export type WSMessage = IndexProgressMessage | QueueStatusMessage | SyncProgressMessage | { type: 'heartbeat' } | { type: 'pong' }

export interface DocCenterWSCallbacks {
  onProgress?: (msg: IndexProgressMessage) => void
  onSyncProgress?: (msg: SyncProgressMessage) => void
  onQueueStatus?: (msg: QueueStatusMessage) => void
  onError?: (error: Error) => void
  onClose?: () => void
}

/**
 * 创建 WebSocket 连接（带自动重连）
 */
export function createDocCenterWS(callbacks: DocCenterWSCallbacks): WebSocket {
  const wsUrl = getWebSocketUrl('/api/v1/doc-center/ws')
  let ws: WebSocket
  let pingInterval: ReturnType<typeof setInterval> | null = null
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null
  let isManualClose = false
  let reconnectAttempts = 0
  const maxReconnectAttempts = 10
  const reconnectDelay = 3000

  const connect = () => {
    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      console.log('[DocCenterWS] 连接成功')
      reconnectAttempts = 0
      // 启动心跳
      if (pingInterval) clearInterval(pingInterval)
      pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }))
        }
      }, 25000)
    }

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data)
        
        if (msg.type === 'index_progress' && callbacks.onProgress) {
          callbacks.onProgress(msg as IndexProgressMessage)
        } else if (msg.type === 'sync_progress' && callbacks.onSyncProgress) {
          callbacks.onSyncProgress(msg as SyncProgressMessage)
        } else if (msg.type === 'queue_status' && callbacks.onQueueStatus) {
          callbacks.onQueueStatus(msg as QueueStatusMessage)
        }
      } catch (e) {
        void e
      }
    }

    ws.onerror = (event) => {
      console.error('[DocCenterWS] 连接错误:', event)
      callbacks.onError?.(new Error('WebSocket 连接错误'))
    }

    ws.onclose = () => {
      if (pingInterval) {
        clearInterval(pingInterval)
        pingInterval = null
      }
      
      if (!isManualClose && reconnectAttempts < maxReconnectAttempts) {
        reconnectAttempts++
        console.log(`[DocCenterWS] 连接断开，${reconnectDelay/1000}秒后重连 (${reconnectAttempts}/${maxReconnectAttempts})`)
        reconnectTimeout = setTimeout(connect, reconnectDelay)
      } else {
        callbacks.onClose?.()
      }
    }
  }

  connect()

  // 返回一个代理对象，支持手动关闭
  const wsProxy = {
    close: () => {
      isManualClose = true
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout)
        reconnectTimeout = null
      }
      if (pingInterval) {
        clearInterval(pingInterval)
        pingInterval = null
      }
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close()
      }
    },
    send: (data: string | ArrayBufferLike | Blob | ArrayBufferView) => ws.send(data),
    get readyState() { return ws.readyState },
  } as unknown as WebSocket

  return wsProxy
}

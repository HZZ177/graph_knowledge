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
  sync_status?: string
  index_status?: string
  page?: number
  page_size?: number
}): Promise<DocumentListResponse> {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) searchParams.set(key, String(value))
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

// ============== WebSocket ==============

export type WSMessage = IndexProgressMessage | QueueStatusMessage | { type: 'heartbeat' } | { type: 'pong' }

export interface DocCenterWSCallbacks {
  onProgress?: (msg: IndexProgressMessage) => void
  onQueueStatus?: (msg: QueueStatusMessage) => void
  onError?: (error: Error) => void
  onClose?: () => void
}

/**
 * 创建 WebSocket 连接
 */
export function createDocCenterWS(callbacks: DocCenterWSCallbacks): WebSocket {
  const wsUrl = getWebSocketUrl('/api/v1/doc-center/ws')
  const ws = new WebSocket(wsUrl)

  ws.onopen = () => {
    console.log('[DocCenterWS] 连接已建立')
  }

  ws.onmessage = (event) => {
    try {
      const msg: WSMessage = JSON.parse(event.data)
      
      if (msg.type === 'index_progress' && callbacks.onProgress) {
        callbacks.onProgress(msg as IndexProgressMessage)
      } else if (msg.type === 'queue_status' && callbacks.onQueueStatus) {
        callbacks.onQueueStatus(msg as QueueStatusMessage)
      }
      // heartbeat 和 pong 不需要处理
    } catch (e) {
      console.warn('[DocCenterWS] 消息解析失败:', e)
    }
  }

  ws.onerror = (event) => {
    console.error('[DocCenterWS] 连接错误:', event)
    callbacks.onError?.(new Error('WebSocket 连接错误'))
  }

  ws.onclose = () => {
    console.log('[DocCenterWS] 连接已关闭')
    callbacks.onClose?.()
  }

  // 心跳
  const pingInterval = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping' }))
    }
  }, 25000)

  // 清理
  const originalClose = ws.close.bind(ws)
  ws.close = () => {
    clearInterval(pingInterval)
    originalClose()
  }

  return ws
}

/**
 * 文档中心类型定义
 */

// 目录树节点
export interface TreeNode {
  id: string
  title: string
  parent_id: string | null
  is_folder: boolean
  children: TreeNode[]
}

// 源文档（帮助中心）
export interface SourceDocument {
  source_doc_id: string
  title: string
  parent_id: string | null
}

// 本地文档
export interface LocalDocument {
  id: string
  source_doc_id: string
  title: string
  path: string | null
  sync_status: 'pending' | 'syncing' | 'synced' | 'failed'
  sync_error?: string | null
  synced_at: string | null
  local_path: string | null
  image_count?: number
  index_status: 'pending' | 'queued' | 'indexing' | 'indexed' | 'failed'
  index_progress: number
  index_phase: string | null
  index_phase_detail?: string | null
  index_error?: string | null
  chunk_count?: number
  entity_count?: number
  created_at: string | null
  updated_at?: string | null
}

// 文档列表响应
export interface DocumentListResponse {
  items: LocalDocument[]
  total: number
  page: number
  page_size: number
}

// 同步请求
export interface SyncRequest {
  documents: {
    source_doc_id: string
    title: string
    parent_id?: string | null
  }[]
}

// 同步结果
export interface SyncResult {
  source_doc_id: string
  success: boolean
  document?: LocalDocument
  error?: string
}

// 索引请求
export interface IndexRequest {
  document_ids: string[]
  priority?: number
}

// 索引任务
export interface IndexTask {
  document_id: string
  task_id?: string
  success: boolean
  error?: string
}

// 队列状态
export interface QueueStatus {
  is_running: boolean
  pending_count: number
  current_task_id: string | null
  current_task: {
    id: string
    document_id: string
    phase: string
    progress: number
  } | null
}

// WebSocket 进度消息
export interface IndexProgressMessage {
  type: 'index_progress'
  task_id: string
  document_id: string
  phase: string
  phase_name: string
  phase_progress: number
  overall_progress: number
  detail: string
}

// WebSocket 队列状态消息
export interface QueueStatusMessage {
  type: 'queue_status'
  is_running: boolean
  pending_count: number
  current_task_id: string | null
}

// 合并的文档显示项（源文档 + 本地状态）
export interface DocumentDisplayItem {
  source_doc_id: string
  title: string
  parent_id: string | null
  // 本地状态（如果已同步）
  local_id?: string
  sync_status: 'pending' | 'syncing' | 'synced' | 'failed'
  index_status: 'pending' | 'queued' | 'indexing' | 'indexed' | 'failed'
  index_progress: number
  index_phase?: string | null
}

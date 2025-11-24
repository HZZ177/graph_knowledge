import http from './http'

export interface Neo4jHealthResponse {
  connected: boolean
  message: string
  database: string
  error: string | null
}

export interface SyncStatusResponse {
  process_id: string
  process_name: string
  sqlite_status: string
  neo4j_status: 'never_synced' | 'syncing' | 'synced' | 'failed'
  last_sync_at: string | null
  sync_error: string | null
  message: string
}

export interface SystemHealthResponse {
  sqlite: {
    status: string
    message: string
  }
  neo4j: {
    status: string
    connected: boolean
    message: string
    database: string
    error: string | null
  }
  sync_stats: {
    total_processes: number
    synced: number
    failed: number
    never_synced: number
  }
}

/**
 * 检查Neo4j连接健康状态
 */
export const checkNeo4jHealth = async (): Promise<Neo4jHealthResponse> => {
  const response = await http.get('/health/check_neo4j')
  return response.data
}

/**
 * 获取指定流程的同步状态
 */
export const getSyncStatus = async (processId: string): Promise<SyncStatusResponse> => {
  const response = await http.get('/health/get_sync_status', {
    params: { process_id: processId },
  })
  return response.data
}

/**
 * 获取系统整体健康状态
 */
export const getSystemHealth = async (): Promise<SystemHealthResponse> => {
  const response = await http.get('/health/get_system_health')
  return response.data
}

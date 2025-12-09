/**
 * 需求分析测试助手 API
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

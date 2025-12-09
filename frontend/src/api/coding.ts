/**
 * Coding 平台 API
 * 
 * 对接 Coding 平台，获取项目、迭代、需求等信息
 */

import http from './http'

// ==================== 类型定义 ====================

/** 项目信息 */
export interface ProjectInfo {
  id: number
  name: string           // 项目标识名（用于 API 调用）
  display_name: string   // 项目显示名称
  description?: string
  icon?: string
  status: number
  archived: boolean
  created_at: number
  updated_at: number
}

/** 项目列表响应 */
export interface ProjectListResponse {
  page_number: number
  page_size: number
  total_count: number
  project_list: ProjectInfo[]
}

/** 迭代信息 */
export interface IterationInfo {
  id: number
  code: number           // 迭代 Code（用于查询事项）
  name: string           // 迭代名称
  status: string         // 状态：WAIT_PROCESS/PROCESSING/COMPLETED
  goal?: string          // 迭代目标
  start_at: number
  end_at: number
  wait_process_count: number   // 待处理事项数
  processing_count: number     // 进行中事项数
  completed_count: number      // 已完成事项数
  completed_percent: number
}

/** 迭代列表响应 */
export interface IterationListResponse {
  page: number
  page_size: number
  total_page: number
  total_row: number
  iterations: IterationInfo[]
}

/** 事项信息（列表项） */
export interface IssueInfo {
  id: number
  code: number           // 事项 Code（用于获取详情）
  name: string           // 事项名称
  type: string           // 事项类型：REQUIREMENT/DEFECT/MISSION/SUB_TASK
  priority: string       // 优先级
  status_name: string    // 状态名称
  status_type: string    // 状态类型：TODO/PROCESSING/COMPLETED
  iteration_id: number
  iteration_name?: string
  assignee_names: string[]  // 处理人列表
  created_at: number
  updated_at: number
}

/** 事项列表响应 */
export interface IssueListResponse {
  total_count: number
  issues: IssueInfo[]
}

// ==================== API 函数 ====================

/**
 * 获取项目列表
 */
export async function fetchProjects(
  pageNumber: number = 1,
  pageSize: number = 50,
  projectName: string = ''
): Promise<ProjectListResponse> {
  const response = await http.post('/coding/projects', {
    page_number: pageNumber,
    page_size: pageSize,
    project_name: projectName,
  })
  return response.data
}

/**
 * 获取项目迭代列表
 * @param projectName 项目名称
 * @param limit 每页数量
 * @param offset 偏移量
 * @param keywords 关键词搜索
 */
export async function fetchIterations(
  projectName: string,
  limit: number = 100,
  offset: number = 0,
  keywords: string = ''
): Promise<IterationListResponse> {
  const response = await http.post('/coding/iterations', {
    project_name: projectName,
    limit,
    offset,
    keywords,
  })
  return response.data
}

/**
 * 获取迭代下的事项列表（需求）
 * @param projectName 项目名称
 * @param iterationCode 迭代 Code
 * @param issueType 事项类型
 * @param limit 每页数量
 * @param offset 偏移量
 * @param keyword 关键词搜索
 */
export async function fetchIssues(
  projectName: string,
  iterationCode: number,
  issueType: string = 'REQUIREMENT',
  limit: number = 100,
  offset: number = 0,
  keyword: string = ''
): Promise<IssueListResponse> {
  const response = await http.post('/coding/issues', {
    project_name: projectName,
    iteration_code: iterationCode,
    issue_type: issueType,
    limit,
    offset,
    keyword,
  })
  return response.data
}

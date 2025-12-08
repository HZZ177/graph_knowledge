/**
 * File Upload API
 * 
 * 文件上传相关接口
 */

import { API_BASE_PATH } from './config'

// ==================== 类型定义 ====================

export interface FileUploadResponse {
  file_id: string
  url: string
  filename: string
  size: number
  content_type: string
}

export interface FileInfoResponse {
  file_id: string
  url: string
  filename: string
  size: number
  content_type: string
  conversation_id: string | null
  uploaded_at: string
}

export interface UploadedFile {
  id: string
  url: string
  filename: string
  size: number
  type: 'image' | 'document' | 'audio' | 'video' | 'unknown'
  contentType: string
}

// ==================== Helper Functions ====================

/**
 * 判断文件类型
 */
export function determineFileType(contentType: string, filename: string): UploadedFile['type'] {
  if (contentType.startsWith('image/')) {
    return 'image'
  }
  
  if (contentType.startsWith('audio/')) {
    return 'audio'
  }
  
  if (contentType.startsWith('video/')) {
    return 'video'
  }
  
  const documentTypes = [
    'application/pdf',
    'text/plain',
    'text/markdown',
    'text/csv',
    'application/json',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  ]
  
  if (documentTypes.includes(contentType)) {
    return 'document'
  }
  
  // 代码文件
  const codeExtensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.rb', '.php']
  if (codeExtensions.some(ext => filename.toLowerCase().endsWith(ext))) {
    return 'document'
  }
  
  // 日志文件
  if (filename.toLowerCase().endsWith('.log')) {
    return 'document'
  }
  
  return 'unknown'
}

/**
 * 格式化文件大小
 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`
  }
  
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`
  }
  
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// ==================== 统一响应格式 ====================

interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
}

// ==================== API Functions ====================

/**
 * 上传文件
 */
export async function uploadFile(file: File): Promise<UploadedFile> {
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await fetch(`${API_BASE_PATH}/files/upload`, {
    method: 'POST',
    body: formData,
  })
  
  const result: ApiResponse<FileUploadResponse> = await response.json()
  
  if (result.code !== 200) {
    throw new Error(result.message || '文件上传失败')
  }
  
  const data = result.data
  
  return {
    id: data.file_id,
    url: data.url,
    filename: data.filename,
    size: data.size,
    type: determineFileType(data.content_type, data.filename),
    contentType: data.content_type,
  }
}

/**
 * 获取文件信息
 */
export async function getFileInfo(fileId: string): Promise<FileInfoResponse> {
  const response = await fetch(`${API_BASE_PATH}/files/${fileId}`)
  
  const result: ApiResponse<FileInfoResponse> = await response.json()
  
  if (result.code !== 200) {
    throw new Error(result.message || '获取文件信息失败')
  }
  
  return result.data
}

/**
 * 删除文件
 */
export async function deleteFile(fileId: string): Promise<void> {
  const response = await fetch(`${API_BASE_PATH}/files/${fileId}`, {
    method: 'DELETE',
  })
  
  const result: ApiResponse = await response.json()
  
  if (result.code !== 200) {
    throw new Error(result.message || '删除文件失败')
  }
}

/**
 * 列出文件
 */
export async function listFiles(conversationId?: string): Promise<FileInfoResponse[]> {
  const url = conversationId
    ? `${API_BASE_PATH}/files/?conversation_id=${conversationId}`
    : `${API_BASE_PATH}/files/`
  
  const response = await fetch(url)
  
  const result: ApiResponse<FileInfoResponse[]> = await response.json()
  
  if (result.code !== 200) {
    throw new Error(result.message || '获取文件列表失败')
  }
  
  return result.data
}

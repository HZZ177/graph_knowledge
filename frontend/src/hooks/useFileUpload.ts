/**
 * 文件上传 Hook
 * 
 * 支持：
 * - 本地文件选择上传
 * - 拖拽上传
 * - 粘贴上传
 * - 图片压缩（可选）
 * - 上传进度显示
 */

import { useState, useCallback, useEffect } from 'react'
import { message } from 'antd'
import { uploadFile, deleteFile, UploadedFile, formatFileSize } from '../api/files'
import imageCompression from 'browser-image-compression'

export interface UseFileUploadOptions {
  maxFileSize?: number  // 最大文件大小（字节），默认 10MB
  maxFiles?: number  // 最多上传文件数，默认 5
  autoCompress?: boolean  // 是否自动压缩图片，默认 true
  allowedTypes?: string[]  // 允许的文件类型，默认 undefined（无限制）
}

// 上传中的文件（带本地预览）
export interface PendingFile {
  id: string  // 临时 ID
  file: File
  previewUrl: string  // 本地预览 URL
  progress: number  // 上传进度 0-100
  status: 'pending' | 'uploading' | 'done' | 'error'
  error?: string
}

export interface UseFileUploadReturn {
  uploadedFiles: UploadedFile[]
  pendingFiles: PendingFile[]  // 上传中的文件
  uploading: boolean
  handleUpload: (file: File) => Promise<void>
  removeFile: (fileId: string) => Promise<void>
  removePendingFile: (id: string) => void  // 移除上传中的文件
  clearFiles: () => void
  setFiles: (files: UploadedFile[]) => void  // 设置已上传文件（用于回溯恢复附件）
  enableDragDrop: () => () => void
  disableDragDrop: () => void
  enablePaste: () => () => void
  disablePaste: () => void
}

const DEFAULT_OPTIONS: Required<UseFileUploadOptions> = {
  maxFileSize: 10 * 1024 * 1024,  // 10MB
  maxFiles: 5,
  autoCompress: true,
  allowedTypes: [],  // 空数组表示无限制
}

export function useFileUpload(options: UseFileUploadOptions = {}): UseFileUploadReturn {
  const opts = { ...DEFAULT_OPTIONS, ...options }
  
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([])
  const [uploading, setUploading] = useState(false)
  
  /**
   * 验证文件
   */
  const validateFile = useCallback((file: File): boolean => {
    // 检查文件大小
    if (opts.maxFileSize && file.size > opts.maxFileSize) {
      message.error(`文件大小不能超过 ${formatFileSize(opts.maxFileSize)}`)
      return false
    }
    
    // 检查文件数量
    if (opts.maxFiles && uploadedFiles.length >= opts.maxFiles) {
      message.error(`最多只能上传 ${opts.maxFiles} 个文件`)
      return false
    }
    
    // 检查文件类型
    if (opts.allowedTypes && opts.allowedTypes.length > 0) {
      const ext = file.name.split('.').pop()?.toLowerCase()
      if (!ext || !opts.allowedTypes.includes(ext)) {
        message.error(`不支持的文件类型: .${ext}`)
        return false
      }
    }
    
    return true
  }, [uploadedFiles.length, opts])
  
  /**
   * 压缩图片（如果是图片且启用压缩）
   */
  const compressImageIfNeeded = useCallback(async (file: File): Promise<File> => {
    // 仅压缩图片
    if (!file.type.startsWith('image/')) {
      return file
    }
    
    // 检查是否启用压缩
    if (!opts.autoCompress) {
      return file
    }
    
    try {
      const compressedFile = await imageCompression(file, {
        maxSizeMB: 1,  // 压缩到 1MB 以下
        maxWidthOrHeight: 1920,  // 最大宽高 1920px
        useWebWorker: true,
      })
      
      console.log(`[FileUpload] 图片压缩: ${formatFileSize(file.size)} -> ${formatFileSize(compressedFile.size)}`)
      return compressedFile
    } catch (error) {
      console.warn('[FileUpload] 图片压缩失败，使用原图:', error)
      return file
    }
  }, [opts.autoCompress])
  
  /**
   * 上传文件
   */
  const handleUpload = useCallback(async (file: File) => {
    // 验证文件
    if (!validateFile(file)) {
      return
    }
    
    // 生成临时 ID 和预览 URL
    const tempId = `pending-${Date.now()}-${Math.random().toString(36).slice(2)}`
    const previewUrl = file.type.startsWith('image/') ? URL.createObjectURL(file) : ''
    
    // 添加到上传中列表
    const pendingFile: PendingFile = {
      id: tempId,
      file,
      previewUrl,
      progress: 0,
      status: 'uploading',
    }
    setPendingFiles(prev => [...prev, pendingFile])
    setUploading(true)
    
    try {
      // 压缩图片
      const processedFile = await compressImageIfNeeded(file)
      
      // 更新进度（压缩完成 30%）
      setPendingFiles(prev => prev.map(f => 
        f.id === tempId ? { ...f, progress: 30 } : f
      ))
      
      // 上传文件
      const uploadedFile = await uploadFile(processedFile)
      
      // 更新进度（上传完成 100%）
      setPendingFiles(prev => prev.map(f => 
        f.id === tempId ? { ...f, progress: 100, status: 'done' } : f
      ))
      
      // 从 pending 移除，添加到 uploaded
      setPendingFiles(prev => prev.filter(f => f.id !== tempId))
      setUploadedFiles(prev => [...prev, uploadedFile])
      
      // 释放预览 URL
      if (previewUrl) URL.revokeObjectURL(previewUrl)
      
    } catch (error) {
      console.error('[FileUpload] 上传失败:', error)
      // 更新状态为错误
      setPendingFiles(prev => prev.map(f => 
        f.id === tempId ? { ...f, status: 'error', error: error instanceof Error ? error.message : '上传失败' } : f
      ))
      message.error(`文件上传失败: ${error instanceof Error ? error.message : '未知错误'}`)
    } finally {
      setUploading(false)
    }
  }, [validateFile, compressImageIfNeeded])
  
  /**
   * 移除上传中的文件
   */
  const removePendingFile = useCallback((id: string) => {
    setPendingFiles(prev => {
      const file = prev.find(f => f.id === id)
      if (file?.previewUrl) {
        URL.revokeObjectURL(file.previewUrl)
      }
      return prev.filter(f => f.id !== id)
    })
  }, [])
  
  /**
   * 删除文件（UI 立即移除，服务器异步删除）
   */
  const removeFile = useCallback(async (fileId: string) => {
    // 立即从 UI 移除，不阻塞
    setUploadedFiles(prev => prev.filter(f => f.id !== fileId))
    
    // 异步删除服务器文件（不等待结果）
    deleteFile(fileId).catch(error => {
      console.error('[FileUpload] 服务器文件删除失败:', error)
      // 不提示用户，静默处理
    })
  }, [])
  
  /**
   * 清空文件列表
   */
  const clearFiles = useCallback(() => {
    setUploadedFiles([])
  }, [])
  
  /**
   * 启用拖拽上传
   */
  const enableDragDrop = useCallback(() => {
    const handleDrop = (e: DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      
      const files = e.dataTransfer?.files
      if (files && files.length > 0) {
        Array.from(files).forEach(file => {
          handleUpload(file)
        })
      }
    }
    
    const handleDragOver = (e: DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
    }
    
    document.addEventListener('drop', handleDrop)
    document.addEventListener('dragover', handleDragOver)
    
    return () => {
      document.removeEventListener('drop', handleDrop)
      document.removeEventListener('dragover', handleDragOver)
    }
  }, [handleUpload])
  
  /**
   * 禁用拖拽上传
   */
  const disableDragDrop = useCallback(() => {
    // 实际的清理逻辑在 enableDragDrop 返回的 cleanup 函数中
  }, [])
  
  /**
   * 启用粘贴上传
   */
  const enablePaste = useCallback(() => {
    const handlePaste = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items
      if (!items) return
      
      for (let i = 0; i < items.length; i++) {
        const item = items[i]
        
        // 仅处理图片
        if (item.type.startsWith('image/')) {
          const file = item.getAsFile()
          if (file) {
            handleUpload(file)
          }
        }
      }
    }
    
    document.addEventListener('paste', handlePaste)
    
    return () => {
      document.removeEventListener('paste', handlePaste)
    }
  }, [handleUpload])
  
  /**
   * 禁用粘贴上传
   */
  const disablePaste = useCallback(() => {
    // 实际的清理逻辑在 enablePaste 返回的 cleanup 函数中
  }, [])
  
  /**
   * 设置已上传文件列表（用于回溯恢复附件）
   */
  const setFiles = useCallback((files: UploadedFile[]) => {
    setUploadedFiles(files)
  }, [])
  
  return {
    uploadedFiles,
    pendingFiles,
    uploading,
    handleUpload,
    removeFile,
    removePendingFile,
    clearFiles,
    setFiles,
    enableDragDrop,
    disableDragDrop,
    enablePaste,
    disablePaste,
  }
}

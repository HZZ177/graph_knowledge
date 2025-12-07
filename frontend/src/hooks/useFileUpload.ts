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

export interface UseFileUploadReturn {
  uploadedFiles: UploadedFile[]
  uploading: boolean
  handleUpload: (file: File) => Promise<void>
  removeFile: (fileId: string) => Promise<void>
  clearFiles: () => void
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
    
    setUploading(true)
    
    try {
      // 压缩图片
      const processedFile = await compressImageIfNeeded(file)
      
      // 上传文件
      const uploadedFile = await uploadFile(processedFile)
      
      // 添加到列表
      setUploadedFiles(prev => [...prev, uploadedFile])
      
      message.success(`文件上传成功: ${uploadedFile.filename}`)
    } catch (error) {
      console.error('[FileUpload] 上传失败:', error)
      message.error(`文件上传失败: ${error instanceof Error ? error.message : '未知错误'}`)
    } finally {
      setUploading(false)
    }
  }, [validateFile, compressImageIfNeeded])
  
  /**
   * 删除文件
   */
  const removeFile = useCallback(async (fileId: string) => {
    try {
      await deleteFile(fileId)
      setUploadedFiles(prev => prev.filter(f => f.id !== fileId))
      message.success('文件已删除')
    } catch (error) {
      console.error('[FileUpload] 删除失败:', error)
      message.error('文件删除失败')
    }
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
  
  return {
    uploadedFiles,
    uploading,
    handleUpload,
    removeFile,
    clearFiles,
    enableDragDrop,
    disableDragDrop,
    enablePaste,
    disablePaste,
  }
}

/**
 * 文件附件卡片组件
 * 用于在聊天消息中显示文件附件，支持点击下载
 */

import React from 'react'
import { message } from 'antd'
import {
  FilePdfOutlined,
  FileWordOutlined,
  FileExcelOutlined,
  FileTextOutlined,
  FileMarkdownOutlined,
  FileZipOutlined,
  FileImageOutlined,
  CodeOutlined,
  FileUnknownOutlined,
  DownloadOutlined,
} from '@ant-design/icons'
import './FileAttachmentCard.css'

// 文件附件类型（兼容 llm.ts 中的 FileAttachment + size）
export interface FileAttachmentData {
  file_id: string
  url: string
  type: 'image' | 'document' | 'audio' | 'video' | 'unknown'
  filename: string
  content_type?: string
  size?: number
}

interface FileAttachmentCardProps {
  attachment: FileAttachmentData
  /** 是否在待发送区域（可删除） */
  pending?: boolean
  /** 删除回调（仅 pending 模式） */
  onRemove?: () => void
}

/**
 * 根据文件名或类型获取对应图标
 */
const getFileIcon = (filename: string, contentType?: string): React.ReactNode => {
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  
  // PDF
  if (ext === 'pdf' || contentType === 'application/pdf') {
    return <FilePdfOutlined style={{ color: '#ff4d4f' }} />
  }
  
  // Word
  if (['doc', 'docx'].includes(ext) || contentType?.includes('wordprocessingml')) {
    return <FileWordOutlined style={{ color: '#1890ff' }} />
  }
  
  // Excel
  if (['xls', 'xlsx', 'csv'].includes(ext) || contentType?.includes('spreadsheet')) {
    return <FileExcelOutlined style={{ color: '#52c41a' }} />
  }
  
  // Markdown
  if (['md', 'markdown'].includes(ext)) {
    return <FileMarkdownOutlined style={{ color: '#722ed1' }} />
  }
  
  // 代码文件
  if (['py', 'js', 'ts', 'jsx', 'tsx', 'java', 'cpp', 'c', 'go', 'rs', 'rb', 'php', 'html', 'css', 'json', 'xml', 'yaml', 'yml'].includes(ext)) {
    return <CodeOutlined style={{ color: '#fa8c16' }} />
  }
  
  // 压缩文件
  if (['zip', 'rar', '7z', 'tar', 'gz'].includes(ext)) {
    return <FileZipOutlined style={{ color: '#faad14' }} />
  }
  
  // 图片
  if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp'].includes(ext) || contentType?.startsWith('image/')) {
    return <FileImageOutlined style={{ color: '#13c2c2' }} />
  }
  
  // 纯文本
  if (['txt', 'log'].includes(ext) || contentType?.startsWith('text/')) {
    return <FileTextOutlined style={{ color: '#8c8c8c' }} />
  }
  
  // 默认
  return <FileUnknownOutlined style={{ color: '#8c8c8c' }} />
}

/**
 * 格式化文件大小
 */
const formatFileSize = (bytes?: number): string => {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/**
 * 获取文件类型标签
 */
const getFileTypeLabel = (filename: string): string => {
  const ext = filename.split('.').pop()?.toUpperCase() || ''
  return ext || '文件'
}

const FileAttachmentCard: React.FC<FileAttachmentCardProps> = ({ 
  attachment, 
  pending = false,
  onRemove 
}) => {
  const { filename, url, content_type } = attachment
  
  // 处理下载
  const handleDownload = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    
    if (!url) {
      message.warning('文件链接不可用')
      return
    }
    
    // 在新标签页打开（浏览器会自动处理：可预览的显示，不可预览的下载）
    window.open(url, '_blank')
  }
  
  return (
    <div className={`file-attachment-card ${pending ? 'pending' : ''}`}>
        {/* 文件图标 */}
        <div className="file-icon">
          {getFileIcon(filename, content_type)}
        </div>
        
        {/* 文件信息 */}
        <div className="file-info">
          <div className="file-name" title={filename}>
            {filename.length > 20 ? `${filename.slice(0, 18)}...` : filename}
          </div>
          <div className="file-meta">
            <span className="file-type">{getFileTypeLabel(filename)}</span>
            {(attachment as FileAttachmentData).size && (
              <span className="file-size">{formatFileSize((attachment as FileAttachmentData).size)}</span>
            )}
          </div>
        </div>
        
        {/* 下载按钮（非 pending 模式） */}
        {!pending && (
          <div className="file-download-btn" onClick={handleDownload} title="下载文件">
            <DownloadOutlined />
          </div>
        )}
        
        {/* 删除按钮（pending 模式） */}
        {pending && onRemove && (
          <div className="file-remove" onClick={(e) => { e.stopPropagation(); onRemove(); }}>
            ×
          </div>
        )}
      </div>
  )
}

export default FileAttachmentCard

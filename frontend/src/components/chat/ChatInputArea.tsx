/**
 * 聊天输入区域组件
 */

import React from 'react'
import { Upload, Image } from 'antd'
import {
  ArrowUpOutlined,
  PlusOutlined,
  PaperClipOutlined,
  CloseOutlined,
  CloseCircleOutlined,
  FileOutlined,
} from '@ant-design/icons'
import FileAttachmentCard from '../FileAttachmentCard'
import { PendingFile } from '../../hooks/useFileUpload'
import { UploadedFile } from '../../api/files'
import { PhaseId } from '../../hooks/useTestingTaskBoard'

interface ChatInputAreaProps {
  inputRef: React.RefObject<HTMLTextAreaElement>
  inputValue: string
  setInputValue: (value: string) => void
  isLoading: boolean
  uploadedFiles: UploadedFile[]
  pendingFiles: PendingFile[]
  uploading: boolean
  handleUpload: (file: File) => void
  removeFile: (id: string) => void
  removePendingFile: (id: string) => void
  isFileToolsOpen: boolean
  setIsFileToolsOpen: (open: boolean) => void
  onSendMessage: (content?: string) => void
  onStop: () => void
  currentAgentType: string
  messagesLength: number
  testingActivePhase: PhaseId
}

export const ChatInputArea: React.FC<ChatInputAreaProps> = ({
  inputRef,
  inputValue,
  setInputValue,
  isLoading,
  uploadedFiles,
  pendingFiles,
  uploading,
  handleUpload,
  removeFile,
  removePendingFile,
  isFileToolsOpen,
  setIsFileToolsOpen,
  onSendMessage,
  onStop,
  currentAgentType,
  messagesLength,
  testingActivePhase,
}) => {
  const isTestingEmpty = currentAgentType === 'intelligent_testing' && messagesLength === 0
  const testingPresetText: Record<string, string> = {
    analysis: '开始分析需求',
    plan: '开始生成测试方案',
    generate: '开始生成测试用例',
  }
  const presetValue = isTestingEmpty ? testingPresetText[testingActivePhase] || '' : ''

  return (
    <div className="input-area-wrapper">
      <div className="input-container" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
        {/* 文件预览区域 - 在输入框内部上方 */}
        {(uploadedFiles.length > 0 || pendingFiles.length > 0) && (
          <div style={{ 
            display: 'flex', 
            flexWrap: 'wrap', 
            gap: '6px',
            padding: '8px 8px 6px 8px',
          }}>
            {/* 上传中的文件 */}
            {pendingFiles.map(file => (
              <div 
                key={file.id}
                title={file.file.name}
                className="file-thumbnail-wrapper"
                style={{ 
                  position: 'relative',
                  width: '48px',
                  height: '48px',
                  marginRight: '8px',
                  marginTop: '8px',
                }}
              >
                <div style={{
                  width: '100%',
                  height: '100%',
                  borderRadius: '8px',
                  border: '1px solid #e0e0e0',
                  background: '#f5f5f5',
                  overflow: 'hidden',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                }}>
                  {file.previewUrl ? (
                    <img 
                      src={file.previewUrl} 
                      alt={file.file.name}
                      style={{ 
                        width: '100%', 
                        height: '100%', 
                        objectFit: 'cover',
                        opacity: file.status === 'uploading' ? 0.7 : 1,
                      }} 
                    />
                  ) : (
                    <FileOutlined style={{ fontSize: 18, color: '#999' }} />
                  )}
                  {/* 上传进度 - 白色圆环 loading 动画 */}
                  {file.status === 'uploading' && (
                    <div style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      right: 0,
                      bottom: 0,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: 'rgba(0,0,0,0.3)',
                      borderRadius: '8px',
                    }}>
                      <div className="upload-spinner" />
                    </div>
                  )}
                  {/* 错误状态 */}
                  {file.status === 'error' && (
                    <div style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      right: 0,
                      bottom: 0,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: 'rgba(255,77,79,0.15)',
                      borderRadius: '8px',
                    }}>
                      <CloseCircleOutlined style={{ fontSize: 14, color: '#ff4d4f' }} />
                    </div>
                  )}
                </div>
                {/* 删除按钮 - 在边线上，hover 时显示 */}
                <div
                  className="file-thumbnail-close"
                  onClick={(e) => { e.stopPropagation(); removePendingFile(file.id) }}
                >
                  <CloseOutlined style={{ fontSize: 10, color: '#666' }} />
                </div>
              </div>
            ))}
            
            {/* 已上传的文件 - 图片用缩略图，文档用卡片 */}
            {uploadedFiles.map(file => (
              file.type === 'image' ? (
                <div 
                  key={file.id}
                  title={file.filename}
                  className="file-thumbnail-wrapper"
                  style={{ 
                    position: 'relative',
                    width: '48px',
                    height: '48px',
                    marginRight: '8px',
                    marginTop: '8px',
                  }}
                >
                  <div style={{
                    width: '100%',
                    height: '100%',
                    borderRadius: '8px',
                    border: '1px solid #e0e0e0',
                    background: '#f5f5f5',
                    overflow: 'hidden',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}>
                    <Image
                      src={file.url}
                      width={48}
                      height={48}
                      style={{ objectFit: 'cover', cursor: 'pointer' }}
                      preview={{ mask: null }}
                    />
                  </div>
                  <div
                    className="file-thumbnail-close"
                    onClick={(e) => { e.stopPropagation(); removeFile(file.id) }}
                  >
                    <CloseOutlined style={{ fontSize: 10, color: '#666' }} />
                  </div>
                </div>
              ) : (
                <FileAttachmentCard 
                  key={file.id}
                  attachment={{
                    file_id: file.id,
                    url: file.url,
                    type: file.type as 'document',
                    filename: file.filename,
                    content_type: file.contentType,
                    size: file.size,
                  }}
                  pending
                  onRemove={() => removeFile(file.id)}
                />
              )
            ))}
          </div>
        )}
        
        {/* 输入行 */}
        <div style={{ display: 'flex', alignItems: 'center', width: '100%' }}>
          {/* 左侧文件工具按钮 */}
          <div className="file-tools-wrapper">
            <button
              className="file-tools-btn"
              onClick={() => setIsFileToolsOpen(!isFileToolsOpen)}
              disabled={isLoading}
              title="添加内容"
            >
              <PlusOutlined style={{ fontSize: 18 }} />
            </button>
            
            {/* 文件工具弹窗 */}
            {isFileToolsOpen && (
              <div className="file-tools-menu">
                <Upload
                  customRequest={({ file }) => {
                    handleUpload(file as File)
                    setIsFileToolsOpen(false)
                  }}
                  showUploadList={false}
                  accept="image/*,.pdf,.txt,.md,.log,.json,.py,.js,.ts,.java,.cpp,.c,.go"
                  disabled={isLoading || uploading}
                >
                  <div className="file-tools-item">
                    <PaperClipOutlined className="file-tools-item-icon" />
                    <div className="file-tools-item-content">
                      <span className="file-tools-item-name">上传附件</span>
                      <span className="file-tools-item-desc">支持图片、文档、代码文件等</span>
                    </div>
                  </div>
                </Upload>
              </div>
            )}
          </div>
          
          {/* 输入框 */}
          <textarea
            ref={inputRef}
            className={`chat-textarea ${isTestingEmpty ? 'testing-preset' : ''}`}
            placeholder="输入问题，开始探索（支持拖拽/粘贴图片）"
            value={isTestingEmpty ? presetValue : inputValue}
            onChange={e => !isTestingEmpty && setInputValue(e.target.value)}
            readOnly={isTestingEmpty}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                if (!isLoading) {
                  isTestingEmpty ? onSendMessage(presetValue) : onSendMessage()
                }
              }
            }}
            rows={1}
          />
          
          <div className="action-buttons">
            {isLoading ? (
              <button className="stop-btn" onClick={onStop} aria-label="停止生成" />
            ) : (
              <button 
                className="send-btn" 
                onClick={() => {
                  isTestingEmpty ? onSendMessage(testingPresetText[testingActivePhase]) : onSendMessage()
                }}
                disabled={
                  isTestingEmpty
                    ? false  // 测试助手空状态时始终可点击
                    : !inputValue.trim() && uploadedFiles.length === 0
                }
              >
                <ArrowUpOutlined style={{ fontSize: 20, fontWeight: 'bold' }} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default ChatInputArea

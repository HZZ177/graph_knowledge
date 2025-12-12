/**
 * 消息气泡组件
 */

import React from 'react'
import { Image } from 'antd'
import {
  UserOutlined,
  RobotOutlined,
  ReloadOutlined,
  RollbackOutlined,
} from '@ant-design/icons'
import { DisplayMessage, ToolSummaryInfo, ActiveToolInfo, ToolProgressStep } from '../../types/chat'
import { buildRenderItems } from '../../utils/chatUtils'
import { MemoizedMarkdown } from './MemoizedMarkdown'
import { ThinkBlock } from './ThinkBlock'
import { ToolProcess, BatchToolProcess } from './ToolProcess'
import FileAttachmentCard from '../FileAttachmentCard'

interface MessageItemProps {
  message: DisplayMessage
  isLoading?: boolean
  canRegenerate?: boolean  // 是否可以重新生成（非最后一条正在生成的消息）
  onRegenerate?: () => void
  onRollback?: () => void
  toolSummaries?: Map<string, ToolSummaryInfo>  // 工具摘要（包含批次信息）
  activeTools?: Map<number, ActiveToolInfo>     // 活跃工具信息（用于批次分组）
  activeToolsRef?: React.MutableRefObject<Map<number, ActiveToolInfo>>  // ref版本，用于同步获取
  toolProgress?: Map<number, ToolProgressStep[]>  // 工具内部进度步骤
}

export const MessageItem: React.FC<MessageItemProps> = React.memo(({ 
  message, 
  isLoading, 
  canRegenerate, 
  onRegenerate, 
  onRollback, 
  toolSummaries, 
  activeTools, 
  activeToolsRef,
  toolProgress,
}) => {
  const isUser = message.role === 'user'
  
  // 用户消息使用 Markdown 渲染（和 AI 消息一致）
  if (isUser) {
    const imageAttachments = message.attachments?.filter(a => a.type === 'image') || []
    const otherAttachments = message.attachments?.filter(a => a.type !== 'image') || []
    
    return (
      <div className={`message-item user`}>
        <div className="message-header">
          <div className="avatar user">
            <UserOutlined />
          </div>
          <span className="role-name">You</span>
        </div>
        <div className="message-bubble-wrapper">
          <div className="message-bubble">
            {/* 显示图片附件 */}
            {imageAttachments.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: message.content ? '8px' : 0 }}>
                {imageAttachments.map(att => (
                  <Image
                    key={att.file_id}
                    src={att.url}
                    width={120}
                    style={{ borderRadius: '8px', objectFit: 'cover' }}
                    preview={{ mask: <div style={{ fontSize: 11 }}>预览</div> }}
                  />
                ))}
              </div>
            )}
            {/* 显示其他附件（文档等） */}
            {otherAttachments.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: message.content ? '12px' : 0 }}>
                {otherAttachments.map(att => (
                  <FileAttachmentCard key={att.file_id} attachment={att} />
                ))}
              </div>
            )}
            {/* 消息文本 */}
            {message.content && <MemoizedMarkdown source={message.content} />}
          </div>
          {onRollback && !isLoading && (
            <div className="message-actions-external">
              <button className="action-btn" onClick={onRollback} title="回溯到此处，重新开始对话">
                <RollbackOutlined /> 回溯
              </button>
            </div>
          )}
        </div>
      </div>
    )
  }
  
  // Assistant 消息：直接调用 buildRenderItems，不使用 useMemo
  // 因为 Map 对象作为依赖项会导致每次都重新计算（每次 setState 创建新 Map）
  // buildRenderItems 本身不是重计算，真正的性能问题来自无限调用循环
  // 通过合理的组件设计避免无限循环，而不是依赖 useMemo
  // 优先使用消息自带的 toolSummaries（已完成的历史消息），否则使用 props 传入的全局 toolSummaries（当前正在流式输出）
  const effectiveToolSummaries = message.toolSummaries || toolSummaries
  const renderItems = buildRenderItems(message.content, message.currentToolName, effectiveToolSummaries, activeTools, activeToolsRef, toolProgress)
  
  // 初始思考状态：正在思考但还没有任何内容
  const isInitialThinking = message.isThinking && renderItems.length === 0
  
  // 检查是否有正文内容
  const hasTextContent = renderItems.some(item => item.type === 'text' && item.textContent)
  
  // 检查是否有工具调用
  const hasTools = renderItems.some(item => item.type === 'tool' || item.type === 'batch_tool')
  
  // 检查是否有任何工具正在执行（通过 renderItems 中的 isActive 状态判断）
  const hasActiveTools = renderItems.some(item => 
    (item.type === 'tool' && item.toolIsActive) ||
    (item.type === 'batch_tool' && item.batchTools?.some(t => t.isActive))
  )
  
  // 工具全部结束但正文尚未输出：有工具、无活跃工具、无当前工具名、无正文、isThinking
  const isWaitingMainAfterTools = hasTools && !hasActiveTools && !message.currentToolName && !hasTextContent && !!message.isThinking
  
  return (
    <div className={`message-item assistant`}>
      <div className="message-header">
        <div className="avatar assistant">
          <RobotOutlined />
        </div>
        <span className="role-name">Keytop AI</span>
      </div>
      
      <div className="message-bubble-wrapper">
        <div className="message-bubble">
          {/* 初始思考状态 */}
          {isInitialThinking && (
            <div className="inline-expandable">
              <span className="status-text">Thinking</span>
            </div>
          )}
          
          {/* 按顺序渲染所有内容 */}
          {renderItems.map(item => {
            if (item.type === 'think') {
              return (
                <ThinkBlock
                  key={item.key}
                  content={item.thinkContent || ''}
                  isStreaming={item.isThinkStreaming}
                  isComplete={item.isThinkComplete}
                />
              )
            }
            if (item.type === 'tool') {
              return (
                <ToolProcess
                  key={item.key}
                  name={item.toolName || ''}
                  isActive={item.toolIsActive || false}
                  inputSummary={item.toolInputSummary}
                  outputSummary={item.toolOutputSummary}
                  elapsed={item.toolElapsed}
                  progressSteps={item.toolProgressSteps}
                />
              )
            }
            if (item.type === 'batch_tool' && item.batchTools) {
              return (
                <BatchToolProcess
                  key={item.key}
                  batchId={item.batchId || 0}
                  tools={item.batchTools}
                />
              )
            }
            if (item.type === 'text') {
              return (
                <div key={item.key} className="markdown-body">
                  <MemoizedMarkdown source={item.textContent || ''} />
                </div>
              )
            }
            return null
          })}
          
          {/* 等待正文输出状态 */}
          {isWaitingMainAfterTools && (
            <div className="markdown-body">
              <span className="status-text">Answering</span>
            </div>
          )}
          
          {/* AI消息底部：重新回答按钮 */}
          {canRegenerate && !isLoading && hasTextContent && (
            <div className="message-actions">
              <button className="action-btn" onClick={onRegenerate} title="重新生成此回答">
                <ReloadOutlined /> 重新回答
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
})

export default MessageItem

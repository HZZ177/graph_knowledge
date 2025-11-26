/**
 * 流式Chat演示组件
 * 
 * 展示如何使用useWebSocketStream hook和StreamingText组件
 * 可作为集成流式Chat功能的参考
 */

import React, { useState } from 'react'
import { Input, Button, Space, Card, Typography } from 'antd'
import { SendOutlined, StopOutlined, ReloadOutlined } from '@ant-design/icons'

import { useChatStream } from '../hooks/useWebSocketStream'
import { StreamingText, StreamingTextBox } from './StreamingText'

const { TextArea } = Input
const { Text } = Typography

// ==================== 演示组件 ====================

export const StreamingChatDemo: React.FC = () => {
  const [question, setQuestion] = useState('')
  const [processId, setProcessId] = useState('')
  
  const {
    content,
    status,
    error,
    isStreaming,
    ask,
    stop,
    reset,
  } = useChatStream({
    onChunk: (chunk) => {
      console.log('收到chunk:', chunk)
    },
    onDone: (fullContent) => {
      console.log('流式完成，完整内容长度:', fullContent.length)
    },
    onError: (err) => {
      console.error('流式错误:', err)
    },
  })
  
  const handleSubmit = () => {
    if (!question.trim()) return
    ask(question.trim(), processId || undefined)
  }
  
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }
  
  const getStatusText = () => {
    switch (status) {
      case 'idle': return '就绪'
      case 'connecting': return '连接中...'
      case 'streaming': return '生成中...'
      case 'done': return '完成'
      case 'error': return '错误'
      default: return status
    }
  }
  
  const getStatusColor = () => {
    switch (status) {
      case 'idle': return '#8c8c8c'
      case 'connecting': return '#1677ff'
      case 'streaming': return '#52c41a'
      case 'done': return '#52c41a'
      case 'error': return '#ff4d4f'
      default: return '#8c8c8c'
    }
  }
  
  return (
    <Card 
      title="流式Chat演示" 
      extra={
        <Text style={{ color: getStatusColor() }}>
          {getStatusText()}
        </Text>
      }
      style={{ maxWidth: 800, margin: '20px auto' }}
    >
      <Space direction="vertical" style={{ width: '100%' }} size={16}>
        {/* 输入区域 */}
        <div>
          <Text type="secondary" style={{ fontSize: 12, marginBottom: 4, display: 'block' }}>
            流程ID（可选）
          </Text>
          <Input
            placeholder="输入流程ID以获取上下文"
            value={processId}
            onChange={(e) => setProcessId(e.target.value)}
            disabled={isStreaming}
            style={{ marginBottom: 8 }}
          />
          
          <Text type="secondary" style={{ fontSize: 12, marginBottom: 4, display: 'block' }}>
            问题
          </Text>
          <TextArea
            placeholder="输入你的问题，按Enter发送"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
            rows={3}
            style={{ marginBottom: 8 }}
          />
          
          <Space>
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSubmit}
              disabled={!question.trim() || isStreaming}
              loading={status === 'connecting'}
            >
              发送
            </Button>
            
            {isStreaming && (
              <Button
                icon={<StopOutlined />}
                onClick={stop}
                danger
              >
                停止
              </Button>
            )}
            
            <Button
              icon={<ReloadOutlined />}
              onClick={reset}
              disabled={isStreaming}
            >
              重置
            </Button>
          </Space>
        </div>
        
        {/* 响应区域 */}
        <StreamingTextBox
          title="AI 响应"
          content={content}
          isStreaming={isStreaming}
          maxHeight={400}
          placeholder="AI响应将在这里显示..."
          loadingText="AI正在思考"
        />
        
        {/* 错误显示 */}
        {error && (
          <div style={{ 
            padding: '8px 12px', 
            background: '#fff2f0', 
            border: '1px solid #ffccc7',
            borderRadius: 6,
            color: '#ff4d4f',
            fontSize: 13,
          }}>
            错误: {error}
          </div>
        )}
      </Space>
    </Card>
  )
}

export default StreamingChatDemo

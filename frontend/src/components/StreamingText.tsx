/**
 * 流式文本显示组件
 * 
 * 功能：
 * 1. 打字机效果显示流式内容
 * 2. 光标闪烁动画
 * 3. 自动滚动到底部
 * 4. 支持Markdown渲染（可选）
 */

import React, { useEffect, useRef } from 'react'
import { Typography, Spin } from 'antd'
import { LoadingOutlined } from '@ant-design/icons'

const { Paragraph } = Typography

// ==================== 类型定义 ====================

export interface StreamingTextProps {
  /** 要显示的文本内容 */
  content: string
  /** 是否正在流式传输 */
  isStreaming?: boolean
  /** 是否显示光标 */
  showCursor?: boolean
  /** 是否自动滚动到底部 */
  autoScroll?: boolean
  /** 自定义样式 */
  style?: React.CSSProperties
  /** 自定义类名 */
  className?: string
  /** 占位文本（内容为空时显示） */
  placeholder?: string
  /** 加载中文本 */
  loadingText?: string
}

// ==================== 样式 ====================

const cursorStyle: React.CSSProperties = {
  display: 'inline-block',
  width: 2,
  height: '1em',
  backgroundColor: '#1677ff',
  marginLeft: 2,
  animation: 'cursor-blink 1s infinite',
  verticalAlign: 'text-bottom',
}

const containerStyle: React.CSSProperties = {
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
  lineHeight: 1.8,
  fontSize: 14,
}

// ==================== 组件实现 ====================

export const StreamingText: React.FC<StreamingTextProps> = ({
  content,
  isStreaming = false,
  showCursor = true,
  autoScroll = true,
  style,
  className,
  placeholder = '等待响应...',
  loadingText = '思考中',
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  
  // 自动滚动到底部
  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [content, autoScroll])
  
  // 空内容且正在流式传输时显示加载状态
  if (!content && isStreaming) {
    return (
      <div 
        ref={containerRef}
        className={className}
        style={{ 
          ...containerStyle, 
          ...style,
          color: '#8c8c8c',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <Spin indicator={<LoadingOutlined style={{ fontSize: 14 }} spin />} />
        <span>{loadingText}</span>
      </div>
    )
  }
  
  // 空内容显示占位符
  if (!content) {
    return (
      <div 
        ref={containerRef}
        className={className}
        style={{ 
          ...containerStyle, 
          ...style,
          color: '#bfbfbf',
        }}
      >
        {placeholder}
      </div>
    )
  }
  
  return (
    <div 
      ref={containerRef}
      className={className}
      style={{ ...containerStyle, ...style }}
    >
      {/* 注入光标闪烁动画 */}
      <style>
        {`
          @keyframes cursor-blink {
            0%, 50% { opacity: 1; }
            51%, 100% { opacity: 0; }
          }
        `}
      </style>
      
      {content}
      
      {/* 流式传输时显示光标 */}
      {isStreaming && showCursor && (
        <span style={cursorStyle} />
      )}
    </div>
  )
}

// ==================== 带容器的版本 ====================

export interface StreamingTextBoxProps extends StreamingTextProps {
  /** 标题 */
  title?: string
  /** 最大高度 */
  maxHeight?: number | string
  /** 是否显示边框 */
  bordered?: boolean
}

export const StreamingTextBox: React.FC<StreamingTextBoxProps> = ({
  title,
  maxHeight = 300,
  bordered = true,
  ...textProps
}) => {
  return (
    <div
      style={{
        border: bordered ? '1px solid #f0f0f0' : 'none',
        borderRadius: 8,
        overflow: 'hidden',
      }}
    >
      {title && (
        <div
          style={{
            padding: '8px 12px',
            background: '#fafafa',
            borderBottom: '1px solid #f0f0f0',
            fontWeight: 500,
            fontSize: 13,
          }}
        >
          {title}
        </div>
      )}
      <div
        style={{
          padding: 12,
          maxHeight,
          overflow: 'auto',
        }}
      >
        <StreamingText {...textProps} />
      </div>
    </div>
  )
}

export default StreamingText

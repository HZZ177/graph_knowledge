/**
 * 思考过程展示组件（Cursor 风格：Thought for Xs）
 */

import React, { useState, useEffect, useRef } from 'react'
import { ExpandableContent } from './ExpandableContent'
import { MemoizedMarkdown } from './MemoizedMarkdown'

interface ThinkBlockProps {
  content: string
  isStreaming?: boolean
  isComplete?: boolean  // think 标签是否已关闭
}

export const ThinkBlock: React.FC<ThinkBlockProps> = ({ content, isStreaming, isComplete }) => {
  const [isExpanded, setIsExpanded] = useState(true)  // 默认展开
  const [userToggled, setUserToggled] = useState(false)
  const [durationMs, setDurationMs] = useState<number | null>(null)
  const thinkStartRef = useRef<number | null>(null)
  
  // 自动收起：think 完成后收起
  useEffect(() => {
    if (userToggled) return
    if (isComplete) {
      setIsExpanded(false)
    }
  }, [isComplete, userToggled])

  // 记录思考耗时：isStreaming 从 false -> true 记开始，完成时计算总时长
  useEffect(() => {
    if (isStreaming && thinkStartRef.current === null) {
      thinkStartRef.current = performance.now()
    }
    if (!isStreaming && isComplete && thinkStartRef.current !== null && durationMs === null) {
      const end = performance.now()
      setDurationMs(end - thinkStartRef.current)
    }
  }, [isStreaming, isComplete, durationMs])
  
  const handleToggle = () => {
    setUserToggled(true)
    setIsExpanded(!isExpanded)
  }
  
  if (!content) return null
  
  let title: React.ReactNode
  if (isStreaming) {
    title = <span className="status-text">Thinking</span>
  } else if (durationMs !== null) {
    const seconds = Math.max(0.1, durationMs / 1000)
    title = `Thought for ${seconds.toFixed(1)}s`
  } else {
    title = 'Thought'
  }
  
  return (
    <div className={`inline-expandable ${isExpanded ? 'expanded' : ''}`}>
      <span className="inline-expandable-toggle" onClick={handleToggle}>
        {title}
        <span className="inline-chevron">›</span>
      </span>
      <ExpandableContent isExpanded={isExpanded} className="inline-expandable-content think-text markdown-body">
        <MemoizedMarkdown source={content} fontSize={14} />
      </ExpandableContent>
    </div>
  )
}

export default ThinkBlock

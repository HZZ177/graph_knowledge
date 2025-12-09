/**
 * 工具调用过程展示组件（单个调用和批量调用）
 */

import React, { useState } from 'react'
import { ExpandableContent } from './ExpandableContent'
import { BatchToolItemInfo } from '../../types/chat'

// ==========================================
// 单个工具调用展示
// ==========================================

interface ToolProcessProps {
  name: string
  isActive: boolean
  inputSummary?: string   // 输入摘要，如 "关键词: 开卡"
  outputSummary?: string  // 输出摘要，如 "找到 3 个结果"
  elapsed?: number        // 耗时（秒）
}

export const ToolProcess: React.FC<ToolProcessProps> = ({ name, isActive, inputSummary, outputSummary, elapsed }) => {
  const [isExpanded, setIsExpanded] = useState(false)
  
  if (!name) return null
  const prettyName = name.replace(/_/g, ' ')
  
  // 格式化耗时
  const formatElapsed = (seconds?: number) => {
    if (seconds === undefined) return ''
    if (seconds < 1) return `${Math.round(seconds * 1000)}ms`
    return `${seconds.toFixed(1)}s`
  }
  
  // 统一格式：calling tool: xxx / called tool: xxx
  let label: React.ReactNode
  if (isActive) {
    label = <span className="status-text">calling tool: {prettyName}</span>
  } else {
    const elapsedStr = formatElapsed(elapsed)
    const extras = [elapsedStr, outputSummary].filter(Boolean)
    const suffix = extras.length > 0 ? ` (${extras.join(' · ')})` : ''
    label = `called tool: ${prettyName}${suffix}`
  }

  // 只有完成后有摘要时才能展开
  const canExpand = !isActive && (inputSummary || outputSummary)

  return (
    <div className={`inline-expandable ${isExpanded ? 'expanded' : ''}`}>
      <span 
        className="inline-expandable-toggle" 
        onClick={() => canExpand && setIsExpanded(!isExpanded)}
        style={{ cursor: canExpand ? 'pointer' : 'default' }}
      >
        {label}
        {canExpand && <span className="inline-chevron">›</span>}
      </span>
      {canExpand && (
        <ExpandableContent isExpanded={isExpanded} className="inline-expandable-content">
          {inputSummary && (
            <div className="tool-summary-item">
              <span className="tool-summary-label">查询:</span> {inputSummary}
            </div>
          )}
          {outputSummary && (
            <div className="tool-summary-item">
              <span className="tool-summary-label">结果:</span> {outputSummary}
            </div>
          )}
        </ExpandableContent>
      )}
    </div>
  )
}

// ==========================================
// 批量工具调用展示
// ==========================================

interface BatchToolProcessProps {
  batchId: number
  tools: BatchToolItemInfo[]
}

export const BatchToolProcess: React.FC<BatchToolProcessProps> = ({ tools }) => {
  const [isExpanded, setIsExpanded] = useState(false)
  
  const activeCount = tools.filter(t => t.isActive).length
  const completedCount = tools.filter(t => !t.isActive).length
  const totalCount = tools.length
  const isActive = activeCount > 0
  
  // 计算最大耗时（并行执行以最长的为准）
  const maxElapsed = Math.max(...tools.map(t => t.elapsed ?? 0))
  const formatElapsed = (seconds: number) => {
    if (seconds === 0) return ''
    if (seconds < 1) return `${Math.round(seconds * 1000)}ms`
    return `${seconds.toFixed(1)}s`
  }
  
  // 统一格式：calling tool: xxx, yyy / called tool: xxx, yyy
  const toolNames = tools.map(t => t.name.replace(/_/g, ' ')).join(', ')
  let label: React.ReactNode
  if (isActive) {
    label = <span className="status-text">calling tool: {toolNames} ({completedCount}/{totalCount})</span>
  } else {
    const elapsedStr = formatElapsed(maxElapsed)
    const suffix = elapsedStr ? ` (${elapsedStr})` : ''
    label = `called tool: ${toolNames}${suffix}`
  }

  // 批量工具调用时始终可以展开（执行中也可以查看各工具状态）
  const canExpand = totalCount > 1

  return (
    <div className={`inline-expandable ${isExpanded ? 'expanded' : ''} ${isActive ? 'active' : ''}`}>
      <span 
        className="inline-expandable-toggle" 
        onClick={() => canExpand && setIsExpanded(!isExpanded)}
        style={{ cursor: canExpand ? 'pointer' : 'default' }}
      >
        {label}
        {canExpand && <span className="inline-chevron">›</span>}
      </span>
      {canExpand && (
        <ExpandableContent isExpanded={isExpanded} className="inline-expandable-content">
          {tools.map((tool, idx) => {
            const prettyName = tool.name.replace(/_/g, ' ')
            const elapsedStr = tool.elapsed ? (tool.elapsed < 1 ? `${Math.round(tool.elapsed * 1000)}ms` : `${tool.elapsed.toFixed(1)}s`) : ''
            return (
              <div key={`${tool.toolId}-${idx}`} className="tool-summary-item">
                {tool.isActive ? (
                  <span className="loading-dots">calling tool: {prettyName}</span>
                ) : (
                  <span>
                    <strong>{prettyName}</strong>
                    {tool.inputSummary && <> · <span className="tool-summary-label">查询:</span> {tool.inputSummary}</>}
                    {tool.outputSummary && <> · <span className="tool-summary-label">结果:</span> {tool.outputSummary}</>}
                    {elapsedStr && <> · {elapsedStr}</>}
                  </span>
                )}
              </div>
            )
          })}
        </ExpandableContent>
      )}
    </div>
  )
}

export default ToolProcess

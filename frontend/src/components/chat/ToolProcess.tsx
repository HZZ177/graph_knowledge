/**
 * 工具调用过程展示组件（单个调用和批量调用）
 */

import React, { useState } from 'react'
import { LoadingOutlined } from '@ant-design/icons'
import { ExpandableContent } from './ExpandableContent'
import { BatchToolItemInfo, ToolProgressStep } from '../../types/chat'

// ==========================================
// 单个工具调用展示
// ==========================================

// 阶段名称映射（英文 -> 中文，用户友好版本）
const PHASE_LABELS: Record<string, string> = {
  mode_info: '查询模式',
  start_search: '开始检索',
  init_workers: '初始化引擎',
  extracting_keywords: '理解问题',
  keywords_extracted: '问题分析完成',
  embedding: '语义分析',
  querying_entities: '查找相关信息',
  querying_relations: '关联分析',
  local_query: '精准定位',
  global_query: '全局搜索',
  vector_search: '内容检索',
  search_complete: '检索完成',
  selecting_chunks: '筛选内容',
  rerank: '智能排序',
  finalize: '整理结果',
}

interface ToolProcessProps {
  name: string
  isActive: boolean
  inputSummary?: string   // 输入摘要，如 "关键词: 开卡"
  outputSummary?: string  // 输出摘要，如 "找到 3 个结果"
  elapsed?: number        // 耗时（秒）
  progressSteps?: ToolProgressStep[]  // 工具内部进度步骤
}

export const ToolProcess: React.FC<ToolProcessProps> = ({ name, isActive, inputSummary, outputSummary, elapsed, progressSteps }) => {
  const hasProgress = progressSteps && progressSteps.length > 0
  // 工具执行中时默认展开，完成后保持用户的展开状态
  const [isExpanded, setIsExpanded] = useState(isActive)
  const [wasManuallyToggled, setWasManuallyToggled] = useState(false)
  
  // 工具开始执行时自动展开（除非用户手动操作过）
  React.useEffect(() => {
    if (isActive && !wasManuallyToggled) {
      setIsExpanded(true)
    }
  }, [isActive, wasManuallyToggled])
  
  // 处理用户手动点击
  const handleToggle = () => {
    setWasManuallyToggled(true)
    setIsExpanded(!isExpanded)
  }
  
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

  // 工具执行中、有摘要或有进度步骤时可以展开
  const canExpand = (isActive || inputSummary || outputSummary || hasProgress)

  return (
    <div className={`inline-expandable ${isExpanded ? 'expanded' : ''}`}>
      <span 
        className="inline-expandable-toggle" 
        onClick={() => canExpand && handleToggle()}
        style={{ cursor: canExpand ? 'pointer' : 'default' }}
      >
        {label}
        {canExpand && <span className="inline-chevron">›</span>}
      </span>
      {canExpand && (
        <ExpandableContent isExpanded={isExpanded} className="inline-expandable-content">
          {/* 进度步骤（工具执行中或有进度时显示） */}
          {(isActive || hasProgress) && (
            <div className={`tool-progress-steps ${isActive ? 'active' : ''}`}>
              {hasProgress && progressSteps.map((step, idx) => (
                <div key={`${step.phase}-${idx}`} className="tool-progress-step">
                  <span className="tool-progress-icon">✓</span>
                  <span className="tool-progress-label">{PHASE_LABELS[step.phase] || step.phase}</span>
                  <span className="tool-progress-detail">{step.detail}</span>
                </div>
              ))}
              {/* 工具执行中时显示"处理中"占位 */}
              {isActive && (
                <div className="tool-progress-step loading">
                  <LoadingOutlined className="tool-progress-icon" style={{ color: 'var(--text-tertiary)' }} />
                  <span className="tool-progress-label status-text">处理中</span>
                </div>
              )}
            </div>
          )}
          {/* 输入输出摘要 */}
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

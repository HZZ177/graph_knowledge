import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import MarkdownPreview from '@uiw/react-markdown-preview'
import {
  ArrowUpOutlined,
  StopOutlined,
  DeleteOutlined,
  UserOutlined,
  RobotOutlined,
  RightOutlined,
  DownOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  ToolOutlined,
  SearchOutlined,
  EditOutlined,
  AudioOutlined,
  PictureOutlined,
  FolderOutlined,
  HistoryOutlined,
  DoubleLeftOutlined,
  GlobalOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  ReloadOutlined,
  RollbackOutlined,
  PlusOutlined,
} from '@ant-design/icons'
import { createChatClient, ChatClient, ToolCallInfo, fetchConversationHistory, generateConversationTitle, listConversations, deleteConversation, truncateConversation, createRegenerateClient, RegenerateClient, ChatMessage, BatchInfo, AgentType, fetchAgentTypes, fetchLogQueryOptions, LogQueryOption, FileAttachment } from '../api/llm'
import { useTypewriter } from '../hooks/useTypewriter'
import { useFileUpload } from '../hooks/useFileUpload'
import { formatFileSize } from '../api/files'
import '../styles/ChatPage.css'
import { showConfirm } from '../utils/confirm'
import { Upload, Image, Spin } from 'antd'
import { PaperClipOutlined, CloseCircleOutlined, CloseOutlined, FileOutlined } from '@ant-design/icons'
import FileAttachmentCard from '../components/FileAttachmentCard'

// ==========================================
// Interfaces
// ==========================================

// 工具摘要信息（包含批次信息）
interface ToolSummaryInfo {
  input: string
  output: string
  elapsed?: number    // 耗时（秒）
  batchId?: number    // 批次 ID
  batchSize?: number  // 批次大小
  batchIndex?: number // 批次内索引
}

interface DisplayMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  toolCalls?: ToolCallInfo[]
  isThinking?: boolean // 是否正在思考（等待工具返回）
  currentToolName?: string // 当前正在调用的工具名称
  toolSummaries?: Map<string, ToolSummaryInfo> // 该消息关联的工具摘要，key 为 "toolName:toolId"
  attachments?: FileAttachment[] // 用户消息的附件（图片、文档等）
}

// 后端返回的原始消息格式
interface RawHistoryMessage {
  role: 'user' | 'assistant' | 'tool'
  content: string
  tool_calls?: Array<{ name: string; args?: Record<string, unknown> }>
  tool_name?: string
  attachments?: FileAttachment[]  // 用户消息的附件
}

interface ConversationSummary {
  threadId: string
  title: string
  agentType?: string  // Agent 类型，用于恢复历史会话时切换 Agent
  updatedAt: string
}

// 历史记录分组接口
interface ConversationGroup {
  label: string
  conversations: ConversationSummary[]
}

// ==========================================
// Components
// ==========================================

// 0. 缓存的 Markdown 组件（避免重复渲染已完成的内容）
interface MemoizedMarkdownProps {
  source: string
  fontSize?: number
}

const MemoizedMarkdown = React.memo<MemoizedMarkdownProps>(({ source, fontSize = 16 }) => {
  return (
    <MarkdownPreview
      source={source}
      style={{ background: 'transparent', fontSize }}
      wrapperElement={{ "data-color-mode": "light" }}
    />
  )
}, (prevProps, nextProps) => {
  // 只有 source 变化才重新渲染
  return prevProps.source === nextProps.source && prevProps.fontSize === nextProps.fontSize
})

// 1. Agent 配置
const agentWelcomeConfig: Record<string, {
  icon: string
  title: string
  subtitle: string
  suggestions: string[]
}> = {
  knowledge_qa: {
    icon: '🤖',
    title: '业务知识助手',
    subtitle: '探索业务流程、接口实现和数据资源，基于实时图谱提供准确洞察',
    suggestions: [
      'C端封闭的开卡流程是怎样的？',
      '订单相关的接口有哪些？',
      '用户表被哪些服务使用？',
      '微信公众号登录时的校验逻辑是怎么走的？',
    ]
  },
  log_troubleshoot: {
    icon: '🔍',
    title: '日志排查助手',
    subtitle: '智能分析业务日志，快速定位问题根因，提供排查建议',
    suggestions: [
      '最近有哪些错误日志？',
      '支付接口的超时问题如何排查？',
      '用户登录失败的常见原因有哪些？',
      '数据库连接异常如何定位？',
    ]
  },
  code_review: {
    icon: '📝',
    title: '代码审查助手',
    subtitle: '分析代码质量，发现潜在问题，提供优化建议',
    suggestions: [
      '这段代码有什么潜在问题？',
      '如何优化这个函数的性能？',
      '代码中是否存在安全隐患？',
      '有没有更优雅的实现方式？',
    ]
  }
}

// 2. 欢迎屏幕（动态适配 Agent）
const WelcomeScreen: React.FC<{ 
  onSuggestionClick: (q: string) => void
  agentType: string
  businessLine?: string
  privateServer?: string | null
}> = ({ onSuggestionClick, agentType, businessLine, privateServer }) => {
  const config = agentWelcomeConfig[agentType] || agentWelcomeConfig.knowledge_qa

  return (
    <div className="welcome-screen">
      <h1 className="welcome-title">{config.title}</h1>
      
      {/* 日志排查助手显示当前配置 */}
      {agentType === 'log_troubleshoot' && businessLine && (
        <div className="welcome-config">
          <span className="welcome-config-label">当前业务线：</span>
          <span className="welcome-config-value">{businessLine}</span>
          {businessLine === '私有化' && privateServer && (
            <>
              <span className="welcome-config-separator">·</span>
              <span className="welcome-config-label">私有化集团：</span>
              <span className="welcome-config-value">{privateServer}</span>
            </>
          )}
        </div>
      )}
      
      <p className="welcome-subtitle">{config.subtitle}</p>
    </div>
  )
}

// 3. 通用可展开内容组件（动态测量高度，实现平滑动画）
interface ExpandableContentProps {
  isExpanded: boolean
  className?: string
  children: React.ReactNode
}

const ExpandableContent: React.FC<ExpandableContentProps> = ({ isExpanded, className, children }) => {
  const contentRef = useRef<HTMLDivElement>(null)
  const [height, setHeight] = useState<number | 'auto'>(0)
  
  useEffect(() => {
    if (!contentRef.current) return
    
    if (isExpanded) {
      // 展开：测量实际高度
      const scrollHeight = contentRef.current.scrollHeight
      setHeight(scrollHeight)
      // 动画结束后设为 auto，允许内容动态变化
      const timer = setTimeout(() => setHeight('auto'), 300)
      return () => clearTimeout(timer)
    } else {
      // 收起：先设为当前高度（触发过渡），再设为 0
      const scrollHeight = contentRef.current.scrollHeight
      setHeight(scrollHeight)
      requestAnimationFrame(() => {
        requestAnimationFrame(() => setHeight(0))
      })
    }
  }, [isExpanded])
  
  return (
    <div
      ref={contentRef}
      className={`expandable-content ${className || ''}`}
      style={{
        height: height === 'auto' ? 'auto' : height,
        opacity: isExpanded ? 1 : 0,
        visibility: isExpanded || height !== 0 ? 'visible' : 'hidden',
      }}
    >
      {children}
    </div>
  )
}

// 3. 工具调用过程展示（单个调用，一个面板）
interface ToolProcessProps {
  name: string
  isActive: boolean
  inputSummary?: string   // 输入摘要，如 "关键词: 开卡"
  outputSummary?: string  // 输出摘要，如 "找到 3 个结果"
  elapsed?: number        // 耗时（秒）
}

const ToolProcess: React.FC<ToolProcessProps> = ({ name, isActive, inputSummary, outputSummary, elapsed }) => {
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

// 4. 批量工具调用展示组件（合并展示，但保持和单个工具一样的 UI 样式）
interface BatchToolItemInfo {
  toolId: number
  name: string
  isActive: boolean
  inputSummary?: string
  outputSummary?: string
  elapsed?: number
}

interface BatchToolProcessProps {
  batchId: number
  tools: BatchToolItemInfo[]
}

const BatchToolProcess: React.FC<BatchToolProcessProps> = ({ tools }) => {
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

// 5. 内容段落类型定义
// 工具占位符格式: <!--TOOL:toolName--> 或 <!--TOOL:toolName|inputSummary|outputSummary-->

interface ContentSegment {
  type: 'think' | 'text' | 'tool'
  content: string  // think/text 的内容，或 tool 的名称
  startPos: number
  endPos: number
  isComplete?: boolean  // 仅 think 类型：标签是否已闭合
  isToolActive?: boolean  // 仅 tool 类型：是否正在执行
  inputSummary?: string   // 仅 tool 类型：输入摘要
  outputSummary?: string  // 仅 tool 类型：输出摘要
  toolId?: number         // 仅 tool 类型：工具占位符 ID
}

/**
 * 根据工具名称生成输入摘要和输出摘要（与后端 _generate_tool_summaries 保持一致）
 */
const generateToolSummary = (
  toolName: string, 
  toolInput: Record<string, unknown>, 
  toolOutput: string
): { input: string; output: string } => {
  let inputSummary = ''
  let outputSummary = ''
  
  // 尝试解析输出为 JSON
  let outputData: Record<string, unknown> | null = null
  try {
    outputData = JSON.parse(toolOutput)
  } catch {
    // 解析失败，保持 null
  }
  
  // ========== 搜索类工具 ==========
  if (['search_businesses', 'search_steps', 'search_implementations', 'search_data_resources'].includes(toolName)) {
    const query = String(toolInput.query || '')
    if (query) {
      inputSummary = `关键词: ${query}`
    }
    
    if (outputData) {
      if (Array.isArray(outputData.candidates)) {
        const count = outputData.candidates.length
        const total = typeof outputData.total_count === 'number' ? outputData.total_count : count
        if (count > 0) {
          outputSummary = `找到 ${count} 个结果` + (total > count ? ` (共 ${total} 个)` : '')
        } else {
          outputSummary = String(outputData.message || '未找到结果')
        }
      } else if (Array.isArray(outputData.results)) {
        const count = outputData.results.length
        outputSummary = count > 0 ? `找到 ${count} 个相关代码片段` : '未找到相关代码'
      } else if (outputData.error) {
        outputSummary = '查询失败'
      }
    }
  }
  
  // ========== 代码上下文搜索 ==========
  else if (toolName === 'search_code_context') {
    const workspace = String(toolInput.workspace || '')
    const query = String(toolInput.query || '')
    const parts: string[] = []
    if (workspace) {
      parts.push(`代码库: ${workspace}`)
    }
    if (query) {
      const displayQuery = query.length > 40 ? query.slice(0, 40) + '...' : query
      parts.push(`查询: ${displayQuery}`)
    }
    inputSummary = parts.join(' | ')
    
    if (outputData) {
      if (Array.isArray(outputData.content)) {
        const count = outputData.content.length
        outputSummary = count > 0 ? `找到 ${count} 个相关代码片段` : '未找到相关代码'
      } else if (outputData.error) {
        outputSummary = '查询失败'
      } else if (outputData.text) {
        outputSummary = '找到相关代码'
      } else {
        outputSummary = '执行完成'
      }
    }
  }
  
  // ========== 文件读取类工具 ==========
  else if (toolName === 'read_file') {
    const path = String(toolInput.path || '')
    if (path) {
      const filename = path.split('/').pop()?.split('\\').pop() || path
      inputSummary = `文件: ${filename}`
    }
    
    if (outputData) {
      if (typeof outputData.content === 'string') {
        const lines = outputData.content.split('\n').length
        outputSummary = `读取成功 (${lines} 行)`
      } else if (outputData.error) {
        outputSummary = '读取失败'
      }
    } else if (toolOutput && !toolOutput.startsWith('{')) {
      const lines = toolOutput.split('\n').length
      outputSummary = `读取成功 (${lines} 行)`
    }
  }
  
  else if (toolName === 'read_file_range') {
    const path = String(toolInput.path || '')
    const startLine = Number(toolInput.start_line || 0)
    const endLine = Number(toolInput.end_line || 0)
    if (path) {
      const filename = path.split('/').pop()?.split('\\').pop() || path
      inputSummary = `文件: ${filename} (L${startLine}-${endLine})`
    }
    
    if (toolOutput && !toolOutput.toLowerCase().includes('error')) {
      outputSummary = `读取成功 (${endLine - startLine + 1} 行)`
    } else {
      outputSummary = '读取失败'
    }
  }
  
  else if (toolName === 'list_directory') {
    const path = String(toolInput.path || '/')
    const depth = Number(toolInput.max_depth || 2)
    inputSummary = `目录: ${path}` + (depth !== 2 ? ` (深度 ${depth})` : '')
    
    if (outputData) {
      if (Array.isArray(outputData.entries)) {
        outputSummary = `列出 ${outputData.entries.length} 个条目`
      } else if (outputData.error) {
        outputSummary = '列出失败'
      }
    }
  }
  
  // ========== 上下文获取类工具 ==========
  else if (toolName === 'get_business_context') {
    const processIds = Array.isArray(toolInput.process_ids) ? toolInput.process_ids : []
    const count = processIds.length
    inputSummary = count > 1 ? `批量查询 ${count} 个业务` : `业务ID: ${String(processIds[0] || '').slice(0, 20)}`
    
    if (outputData?.results) {
      const total = typeof outputData.total === 'number' ? outputData.total : 0
      outputSummary = `获取 ${total} 个业务上下文`
    } else if (outputData?.error) {
      outputSummary = '获取失败'
    }
  }
  
  else if (toolName === 'get_implementation_context') {
    const implIds = Array.isArray(toolInput.impl_ids) ? toolInput.impl_ids : []
    const count = implIds.length
    inputSummary = count > 1 ? `批量查询 ${count} 个接口` : `接口ID: ${String(implIds[0] || '').slice(0, 20)}`
    
    if (outputData?.results) {
      const total = typeof outputData.total === 'number' ? outputData.total : 0
      outputSummary = `获取 ${total} 个接口上下文`
    } else if (outputData?.error) {
      outputSummary = '获取失败'
    }
  }
  
  else if (toolName === 'get_implementation_business_usages') {
    const implIds = Array.isArray(toolInput.impl_ids) ? toolInput.impl_ids : []
    const count = implIds.length
    inputSummary = count > 1 ? `批量查询 ${count} 个接口使用情况` : `接口ID: ${String(implIds[0] || '').slice(0, 20)}`
    
    if (outputData?.results) {
      const total = typeof outputData.total === 'number' ? outputData.total : 0
      outputSummary = `获取 ${total} 个接口的业务使用`
    } else if (outputData?.error) {
      outputSummary = '查询失败'
    }
  }
  
  else if (toolName === 'get_resource_context') {
    const resourceIds = Array.isArray(toolInput.resource_ids) ? toolInput.resource_ids : []
    const count = resourceIds.length
    inputSummary = count > 1 ? `批量查询 ${count} 个资源` : `资源ID: ${String(resourceIds[0] || '').slice(0, 20)}`
    
    if (outputData?.results) {
      const total = typeof outputData.total === 'number' ? outputData.total : 0
      outputSummary = `获取 ${total} 个资源上下文`
    } else if (outputData?.error) {
      outputSummary = '获取失败'
    }
  }
  
  else if (toolName === 'get_resource_business_usages') {
    const resourceIds = Array.isArray(toolInput.resource_ids) ? toolInput.resource_ids : []
    const count = resourceIds.length
    inputSummary = count > 1 ? `批量查询 ${count} 个资源使用情况` : `资源ID: ${String(resourceIds[0] || '').slice(0, 20)}`
    
    if (outputData?.results) {
      const total = typeof outputData.total === 'number' ? outputData.total : 0
      outputSummary = `获取 ${total} 个资源的业务使用`
    } else if (outputData?.error) {
      outputSummary = '查询失败'
    }
  }
  
  // ========== 图遍历类工具 ==========
  else if (toolName === 'get_neighbors') {
    const nodeIds = Array.isArray(toolInput.node_ids) ? toolInput.node_ids : []
    const depth = Number(toolInput.depth || 1)
    const count = nodeIds.length
    inputSummary = count > 1 ? `批量查询 ${count} 个节点邻居` : `节点: ${String(nodeIds[0] || '').slice(0, 20)}`
    if (depth > 1) {
      inputSummary += ` (深度 ${depth})`
    }
    
    if (outputData?.neighbors) {
      const neighborCount = Array.isArray(outputData.neighbors) ? outputData.neighbors.length : 0
      outputSummary = `找到 ${neighborCount} 个邻居节点`
    } else if (outputData?.error) {
      outputSummary = '查询失败'
    }
  }
  
  else if (toolName === 'get_path_between_entities') {
    inputSummary = '路径查询'
    
    if (outputData) {
      if (Array.isArray(outputData.path)) {
        outputSummary = `找到路径 (${outputData.path.length} 跳)`
      } else if (outputData.error || outputData.path === null) {
        outputSummary = '未找到路径'
      }
    }
  }
  
  // ========== 代码精确搜索 ==========
  else if (toolName === 'grep_code') {
    const pattern = String(toolInput.pattern || '')
    const workspace = String(toolInput.workspace || '')
    const filePattern = String(toolInput.file_pattern || '')
    
    const parts: string[] = []
    if (workspace) {
      parts.push(`代码库: ${workspace}`)
    }
    if (pattern) {
      const displayPattern = pattern.length > 30 ? pattern.slice(0, 30) + '...' : pattern
      parts.push(`搜索: ${displayPattern}`)
    }
    if (filePattern) {
      parts.push(`文件: ${filePattern}`)
    }
    inputSummary = parts.join(' | ')
    
    if (outputData) {
      if (Array.isArray(outputData.matches)) {
        const count = outputData.matches.length
        outputSummary = count > 0 ? `找到 ${count} 处匹配` : '未找到匹配'
      } else if (outputData.error) {
        outputSummary = '搜索失败'
      }
    }
  }
  
  // 默认处理
  if (!inputSummary && toolInput) {
    const firstKey = Object.keys(toolInput)[0]
    if (firstKey) {
      const firstVal = String(toolInput[firstKey])
      inputSummary = firstVal.length > 30 ? `${firstKey}: ${firstVal.slice(0, 30)}...` : `${firstKey}: ${firstVal}`
    }
  }
  
  if (!outputSummary) {
    if (outputData?.error) {
      outputSummary = '执行失败'
    } else if (toolOutput.length > 0) {
      outputSummary = '执行完成'
    } else {
      outputSummary = '无结果'
    }
  }
  
  return { input: inputSummary, output: outputSummary }
}

/**
 * 统一的消息转换函数：将后端原始消息转换为前端显示格式
 * 处理逻辑：
 * 1. 合并连续的assistant消息（模拟流式输出的累积效果）
 * 2. 在content中插入工具占位符（保持原始顺序）
 * 3. 生成toolSummaries（包含batch信息）
 */
const convertRawMessagesToDisplay = (
  rawMessages: RawHistoryMessage[],
  threadId: string
): { 
  messages: DisplayMessage[], 
  toolSummaries: Map<string, ToolSummaryInfo> 
} => {
  const display: DisplayMessage[] = []
  const globalToolSummaries = new Map<string, ToolSummaryInfo>()
  
  let globalToolId = 0
  let globalBatchId = 0
  let accumulatedContent = ''
  let accumulatedToolCalls: ToolCallInfo[] = []
  let accumulatedToolSummaries = new Map<string, ToolSummaryInfo>() // 当前消息的工具摘要
  let aiMessageStartIndex = -1

  const flushAIMessage = () => {
    if (aiMessageStartIndex === -1) return
    
    display.push({
      id: `assistant-${aiMessageStartIndex}-${threadId}`,
      role: 'assistant',
      content: accumulatedContent,
      toolCalls: accumulatedToolCalls.length > 0 ? accumulatedToolCalls : undefined,
      toolSummaries: accumulatedToolSummaries.size > 0 ? new Map(accumulatedToolSummaries) : undefined,
    })
    
    accumulatedContent = ''
    accumulatedToolCalls = []
    accumulatedToolSummaries = new Map()
    aiMessageStartIndex = -1
  }

  rawMessages.forEach((m, i) => {
    if (m.role === 'user') {
      flushAIMessage()
      
      display.push({
        id: `user-${i}-${threadId}`,
        role: 'user',
        content: m.content,
        attachments: m.attachments,  // 保留附件信息
      })
    } else if (m.role === 'assistant') {
      if (aiMessageStartIndex === -1) {
        aiMessageStartIndex = i
      }
      
      // 添加content
      if (m.content) {
        accumulatedContent += m.content
      }
      
      // 如果有工具调用，生成占位符并追加
      if (m.tool_calls && m.tool_calls.length > 0) {
        globalBatchId++
        const batchSize = m.tool_calls.length
        
        for (let idx = 0; idx < m.tool_calls.length; idx++) {
          const tc = m.tool_calls[idx]
          globalToolId++
          
          // 查找对应的 tool 返回消息
          let toolOutput = ''
          for (let j = i + 1; j < rawMessages.length; j++) {
            if (rawMessages[j].role === 'tool' && rawMessages[j].tool_name === tc.name) {
              toolOutput = rawMessages[j].content
              break
            }
          }
          
          // 使用与后端一致的摘要生成函数
          const { input: inputSummary, output: outputSummary } = generateToolSummary(
            tc.name,
            tc.args || {},
            toolOutput
          )
          
          const toolKey = `${tc.name}:${globalToolId}`
          const summaryInfo: ToolSummaryInfo = {
            input: inputSummary,
            output: outputSummary,
            batchId: batchSize > 1 ? globalBatchId : undefined,
            batchSize: batchSize > 1 ? batchSize : undefined,
            batchIndex: batchSize > 1 ? idx : undefined,
          }
          
          // 存入当前消息的摘要Map
          accumulatedToolSummaries.set(toolKey, summaryInfo)
          // 同时存入全局Map（保持向后兼容）
          globalToolSummaries.set(toolKey, summaryInfo)
          
          // 追加工具占位符（保持原始顺序）
          accumulatedContent += `<!--TOOL:${tc.name}:${globalToolId}-->`
          
          // 记录到toolCalls
          accumulatedToolCalls.push({
            name: tc.name,
            output_length: toolOutput.length,
          })
        }
      }
    }
    // tool消息跳过，已通过占位符展示
  })
  
  flushAIMessage()
  
  return { messages: display, toolSummaries: globalToolSummaries }
}

const parseContentSegments = (
  content: string, 
  currentToolName?: string,
  toolSummaries?: Map<string, {input: string, output: string}>
): ContentSegment[] => {
  const segments: ContentSegment[] = []
  const str = content || ''
  const len = str.length

  let i = 0
  let buffer = ''
  let bufferStart = 0
  let inThink = false
  let thinkStartPos = -1

  const flushTextBuffer = (endPos: number) => {
    if (!buffer) return
    const text = buffer.trim()
    if (text) {
      segments.push({
        type: 'text',
        content: text,
        startPos: bufferStart,
        endPos,
      })
    }
    buffer = ''
  }

  while (i < len) {
    // 工具占位符：无论是否在 think 块内，都将其视为一个硬边界
    if (str.startsWith('<!--TOOL:', i)) {
      // 如果当前在 think 中，先结束未闭合的 think 段
      // 遇到工具调用说明思考阶段已结束，标记为已完成（避免一直显示加载动画）
      if (inThink) {
        const raw = buffer
        const trimmed = raw.trim()
        if (trimmed) {
          segments.push({
            type: 'think',
            content: trimmed,
            startPos: thinkStartPos >= 0 ? thinkStartPos : bufferStart,
            endPos: i,
            isComplete: true,  // 工具调用开始 = 思考结束
          })
        }
        inThink = false
        buffer = ''
      } else {
        // 不在 think 中则先 flush 之前累积的正文
        flushTextBuffer(i)
      }

      const end = str.indexOf('-->', i)
      if (end === -1) {
        // 工具标签尚未完整输出，作为普通文本暂存，等待后续内容
        bufferStart = i
        buffer += str.slice(i)
        break
      }

      const markerStart = i
      const markerEnd = end + 3
      const inner = str.slice(i + '<!--TOOL:'.length, end)

      let toolName = ''
      let toolId = ''
      const firstColon = inner.indexOf(':')
      if (firstColon === -1) {
        toolName = inner.trim()
      } else {
        toolName = inner.slice(0, firstColon).trim()
        toolId = inner.slice(firstColon + 1).trim()
      }

      const toolIdNum = toolId ? parseInt(toolId, 10) : undefined
      const toolKey = toolName && toolId ? `${toolName}:${toolId}` : undefined
      const summary = toolKey ? toolSummaries?.get(toolKey) : undefined

      segments.push({
        type: 'tool',
        content: toolName,
        startPos: markerStart,
        endPos: markerEnd,
        isToolActive: false, // 稍后根据 currentToolName 单独标记
        inputSummary: summary?.input,
        outputSummary: summary?.output,
        toolId: toolIdNum,
      })

      i = markerEnd
      bufferStart = i
      buffer = ''
      continue
    }

    // 解析 <think> 开始标签
    if (!inThink && str.startsWith('<think>', i)) {
      // 先 flush 之前的正文
      flushTextBuffer(i)

      inThink = true
      thinkStartPos = i
      i += '<think>'.length
      bufferStart = i
      buffer = ''
      continue
    }

    // 解析 </think> 结束标签
    if (inThink && str.startsWith('</think>', i)) {
      const raw = buffer
      const trimmed = raw.trim()
      if (trimmed) {
        segments.push({
          type: 'think',
          content: trimmed,
          startPos: thinkStartPos,
          endPos: i + '</think>'.length,
          isComplete: true,
        })
      }

      inThink = false
      i += '</think>'.length
      bufferStart = i
      buffer = ''
      continue
    }

    // 普通字符累积到 buffer
    if (!buffer) {
      bufferStart = i
    }
    buffer += str[i]
    i += 1
  }

  // 处理剩余缓冲区内容
  if (buffer) {
    if (inThink) {
      const trimmed = buffer.trim()
      if (trimmed) {
        segments.push({
          type: 'think',
          content: trimmed,
          startPos: thinkStartPos >= 0 ? thinkStartPos : bufferStart,
          endPos: len,
          isComplete: false,
        })
      }
    } else {
      flushTextBuffer(len)
    }
  }

  // 第二遍：根据 currentToolName 标记当前正在执行的工具
  if (currentToolName) {
    let activeIndex = -1
    for (let idx = 0; idx < segments.length; idx++) {
      const seg = segments[idx]
      if (seg.type === 'tool' && seg.content === currentToolName) {
        const hasSummary = !!(seg.inputSummary || seg.outputSummary)
        if (!hasSummary) {
          activeIndex = idx
        }
      }
    }
    if (activeIndex !== -1) {
      segments[activeIndex].isToolActive = true
    }
  }

  return segments
}

// 4. 思考过程展示组件（Cursor 风格：Thought for Xs）
interface ThinkBlockProps {
  content: string
  isStreaming?: boolean
  isComplete?: boolean  // think 标签是否已关闭
}

const ThinkBlock: React.FC<ThinkBlockProps> = ({ content, isStreaming, isComplete }) => {
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

// 6. 消息气泡
interface MessageItemProps {
  message: DisplayMessage
  isLoading?: boolean
  canRegenerate?: boolean  // 是否可以重新生成（非最后一条正在生成的消息）
  onRegenerate?: () => void
  onRollback?: () => void
  toolSummaries?: Map<string, ToolSummaryInfo>  // 工具摘要（包含批次信息）
  activeTools?: Map<number, ActiveToolInfo>     // 活跃工具信息（用于批次分组）
  activeToolsRef?: React.MutableRefObject<Map<number, ActiveToolInfo>>  // ref版本，用于同步获取
}

// 活跃工具信息（包含批次信息）
interface ActiveToolInfo {
  toolId: number
  batchId?: number
  batchSize?: number
  batchIndex?: number
}

// 渲染项类型：用于交错排列思考、工具、正文、批量工具
interface RenderItem {
  type: 'think' | 'tool' | 'text' | 'batch_tool'
  key: string
  // think 类型
  thinkContent?: string
  isThinkStreaming?: boolean
  isThinkComplete?: boolean
  // tool 类型（单个工具）
  toolName?: string
  toolId?: number
  toolIsActive?: boolean
  toolInputSummary?: string
  toolOutputSummary?: string
  toolElapsed?: number
  // batch_tool 类型（批量工具）
  batchId?: number
  batchTools?: BatchToolItemInfo[]
  // text 类型
  textContent?: string
}

/**
 * 构建交错渲染列表
 * 直接从 parseContentSegments 的结果构建，工具占位符已嵌入 content
 * 支持将同一批次的工具调用合并为 batch_tool 类型
 */
const buildRenderItems = (
  content: string,
  currentToolName?: string,
  toolSummaries?: Map<string, ToolSummaryInfo>,
  activeTools?: Map<number, ActiveToolInfo>,  // toolId -> 活跃工具信息
  activeToolsRef?: React.MutableRefObject<Map<number, ActiveToolInfo>>  // ref版本，用于同步获取最新值
): RenderItem[] => {
  const segments = parseContentSegments(content, currentToolName, toolSummaries)
  
  const result: RenderItem[] = []
  let i = 0
  
  while (i < segments.length) {
    const seg = segments[i]
    
    if (seg.type === 'think') {
      result.push({
        type: 'think' as const,
        key: `think-${i}-${seg.startPos}`,
        thinkContent: seg.content,
        isThinkStreaming: !seg.isComplete,
        isThinkComplete: seg.isComplete
      })
      i++
    } else if (seg.type === 'tool') {
      // 获取该工具的批次信息（优先从ref获取，确保最新）
      const toolKey = seg.toolId ? `${seg.content}:${seg.toolId}` : undefined
      const summary = toolKey ? toolSummaries?.get(toolKey) : undefined
      const activeInfo = seg.toolId ? (activeToolsRef?.current.get(seg.toolId) || activeTools?.get(seg.toolId)) : undefined
      
      const batchId = summary?.batchId ?? activeInfo?.batchId
      const batchSize = summary?.batchSize ?? activeInfo?.batchSize ?? 1
      
      // 如果是批量调用（batchSize > 1），收集同一批次的所有工具
      if (batchSize > 1 && batchId !== undefined) {
        const batchTools: BatchToolItemInfo[] = []
        const batchStartIdx = i
        
        // 收集连续的同批次工具
        while (i < segments.length && segments[i].type === 'tool') {
          const toolSeg = segments[i]
          const tk = toolSeg.toolId ? `${toolSeg.content}:${toolSeg.toolId}` : undefined
          const ts = tk ? toolSummaries?.get(tk) : undefined
          const ai = toolSeg.toolId ? activeTools?.get(toolSeg.toolId) : undefined
          
          const thisBatchId = ts?.batchId ?? ai?.batchId
          
          // 如果不是同一批次，停止收集
          if (thisBatchId !== batchId) break
          
          // 判断是否活跃：activeTools 中存在则为活跃，或者 toolSummaries 中无 output 也视为活跃
          const isToolActive = ai !== undefined || (!!toolSeg.isToolActive && !ts?.output)
          
          batchTools.push({
            toolId: toolSeg.toolId || 0,
            name: toolSeg.content,
            isActive: isToolActive,
            inputSummary: ts?.input || toolSeg.inputSummary,
            outputSummary: ts?.output || toolSeg.outputSummary,
            elapsed: ts?.elapsed,
          })
          i++
        }
        
        result.push({
          type: 'batch_tool' as const,
          key: `batch-${batchId}-${batchStartIdx}`,
          batchId,
          batchTools,
        })
      } else {
        // 单个工具调用 - 使用与批量工具相同的活跃状态判断逻辑
        const singleToolActive = activeInfo !== undefined || (!!seg.isToolActive && !summary?.output)
        
        result.push({
          type: 'tool' as const,
          key: `tool-${i}-${seg.content}-${seg.toolId}`,
          toolName: seg.content,
          toolId: seg.toolId,
          toolIsActive: singleToolActive,
          toolInputSummary: summary?.input || seg.inputSummary,
          toolOutputSummary: summary?.output || seg.outputSummary,
          toolElapsed: summary?.elapsed,
        })
        i++
      }
    } else {
      result.push({
        type: 'text' as const,
        key: `text-${i}-${seg.startPos}`,
        textContent: seg.content
      })
      i++
    }
  }
  
  return result
}

const MessageItem: React.FC<MessageItemProps> = React.memo(({ message, isLoading, canRegenerate, onRegenerate, onRollback, toolSummaries, activeTools, activeToolsRef }) => {
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
  const renderItems = buildRenderItems(message.content, message.currentToolName, effectiveToolSummaries, activeTools, activeToolsRef)
  
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

// ==========================================
// Helper Functions
// ==========================================

// 将对话按时间分组
const groupConversations = (conversations: ConversationSummary[]): ConversationGroup[] => {
  const groups: { [key: string]: ConversationSummary[] } = {
    '今天': [],
    '本周': [],
  }
  
  // 用于存储月份的动态键
  const monthGroups: { [key: string]: ConversationSummary[] } = {}
  const monthOrder: string[] = [] // 保持月份顺序

  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const weekStart = todayStart - 6 * 24 * 60 * 60 * 1000 // 简单定义：过去7天内但不是今天

  conversations.forEach(conv => {
    const d = new Date(conv.updatedAt)
    const t = d.getTime()

    if (t >= todayStart) {
      groups['今天'].push(conv)
    } else if (t >= weekStart) {
      groups['本周'].push(conv)
    } else {
      // 使用英文月份名，如 November, October
      const monthName = d.toLocaleString('en-US', { month: 'long' })
      if (!monthGroups[monthName]) {
        monthGroups[monthName] = []
        // 如果是新出现的月份，记录顺序（其实应该按时间排序，这里简化处理，假设输入已经是倒序的）
        if (!monthOrder.includes(monthName)) {
          monthOrder.push(monthName)
        }
      }
      monthGroups[monthName].push(conv)
    }
  })

  // 构建最终数组
  const result: ConversationGroup[] = []
  
  if (groups['今天'].length > 0) result.push({ label: '今天', conversations: groups['今天'] })
  if (groups['本周'].length > 0) result.push({ label: '本周', conversations: groups['本周'] })
  
  monthOrder.forEach(m => {
    if (monthGroups[m].length > 0) {
      result.push({ label: m, conversations: monthGroups[m] })
    }
  })

  return result
}

// ==========================================
// Main Page Component
// ==========================================

const CONVERSATIONS_STORAGE_KEY = 'graph_chat_conversations_v1'

const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [threadId, setThreadId] = useState<string | null>(null)
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'chat' | 'voice' | 'imagine' | 'projects'>('chat')
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)
  
  // Agent 类型状态
  const [agentTypes, setAgentTypes] = useState<AgentType[]>([])
  const [currentAgentType, setCurrentAgentType] = useState<string>('knowledge_qa')
  const [isAgentDropdownOpen, setIsAgentDropdownOpen] = useState(false)
  
  // 日志查询配置（仅 log_troubleshoot Agent 使用）
  const [businessLines, setBusinessLines] = useState<LogQueryOption[]>([])
  const [privateServers, setPrivateServers] = useState<LogQueryOption[]>([])
  const [businessLine, setBusinessLine] = useState<string>('')
  const [privateServer, setPrivateServer] = useState<string | null>(null)
  
  // 下拉框展开状态
  const [isBusinessLineOpen, setIsBusinessLineOpen] = useState(false)
  const [isPrivateServerOpen, setIsPrivateServerOpen] = useState(false)
  
  // 文件工具弹窗状态
  const [isFileToolsOpen, setIsFileToolsOpen] = useState(false)
  
  // 切换业务线时，如果不是私有化则清空私有化选择
  const handleBusinessLineChange = (value: string) => {
    setBusinessLine(value)
    setIsBusinessLineOpen(false)
    if (value !== '私有化') {
      setPrivateServer(null)
    }
  }
  
  const handlePrivateServerChange = (value: string | null) => {
    setPrivateServer(value)
    setIsPrivateServerOpen(false)
  }
  
  // 实时状态
  const [currentTool, setCurrentTool] = useState<string | null>(null)
  const fullContentRef = useRef('') 
  const currentToolCallsRef = useRef<ToolCallInfo[]>([])
  const toolCallIdRef = useRef(0)  // 工具调用唯一 ID 计数器
  const currentToolIdRef = useRef(0)  // 当前正在执行的工具 ID
  // 工具摘要存储（使用 ref 避免频繁创建新 Map 触发重渲染）
  const toolSummariesRef = useRef<Map<string, ToolSummaryInfo>>(new Map())
  const [toolSummariesVersion, setToolSummariesVersion] = useState(0)
  // 提供给组件使用的稳定引用
  const toolSummaries = toolSummariesRef.current
  
  // 活跃工具存储（使用 ref）
  const activeToolsRef = useRef<Map<number, ActiveToolInfo>>(new Map())
  const [activeToolsVersion, setActiveToolsVersion] = useState(0)
  // 提供给组件使用的稳定引用
  const activeTools = activeToolsRef.current
  
  // 节流更新消息的 RAF ID
  const updateMessageRafRef = useRef<number | null>(null)
  const pendingContentRef = useRef<string>('')
  
  const chatClientRef = useRef<ChatClient | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messageListRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const userScrolledUpRef = useRef(false)
  const lastScrollTopRef = useRef(0)
  
  // 文件上传 Hook
  const { 
    uploadedFiles,
    pendingFiles,
    uploading, 
    handleUpload, 
    removeFile,
    removePendingFile,
    clearFiles,
    setFiles,
    enableDragDrop,
    enablePaste,
  } = useFileUpload()

  // 滚动到底部（只在用户未主动上滑时执行）
  const scrollToBottom = useCallback((force = false) => {
    if (!force && userScrolledUpRef.current) return
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  // 检测用户是否滚动到底部附近
  const isNearBottom = useCallback(() => {
    const container = messageListRef.current
    if (!container) return true
    const threshold = 50 // 距离底部50px内认为在底部
    return container.scrollHeight - container.scrollTop - container.clientHeight < threshold
  }, [])

  // 监听滚动事件：检测滚动方向
  const handleScroll = useCallback(() => {
    const container = messageListRef.current
    if (!container) return
    
    const currentScrollTop = container.scrollTop
    const scrollingUp = currentScrollTop < lastScrollTopRef.current
    lastScrollTopRef.current = currentScrollTop
    
    if (isLoading) {
      if (scrollingUp && !isNearBottom()) {
        // 用户向上滚动且不在底部，标记为打断
        userScrolledUpRef.current = true
      } else if (isNearBottom()) {
        // 用户滚动回底部，恢复自动滚动
        userScrolledUpRef.current = false
      }
    }
  }, [isNearBottom, isLoading])

  // 打字机 Hook（使用默认速度配置）
  const { text: streamingContent, append: appendToTypewriter, finish: finishTypewriter, reset: resetTypewriter, isTyping, bufferLength } = useTypewriter({
    onTick: scrollToBottom,
  })
  
  // 缓冲区长度 ref（用于 setTimeout 回调中获取最新值）
  const bufferLengthRef = useRef(0)
  useEffect(() => {
    bufferLengthRef.current = bufferLength
  }, [bufferLength])

  // 加载本地存储的会话列表
  useEffect(() => {
    const loadConversations = async () => {
      try {
        const data = await listConversations()
        const summaries: ConversationSummary[] = data.map(c => ({
          threadId: c.id,
          title: c.title || '新对话',
          agentType: c.agent_type,
          updatedAt: c.updated_at,
        }))
        setConversations(summaries)
      } catch (e) {
        console.error('加载会话列表失败', e)
      }
    }
    loadConversations()
  }, [])
  
  // 加载 Agent 类型列表
  useEffect(() => {
    const loadAgentTypes = async () => {
      try {
        const types = await fetchAgentTypes()
        setAgentTypes(types)
        // 如果有可用类型且当前未设置，使用第一个作为默认
        if (types.length > 0 && !types.find(t => t.agent_type === currentAgentType)) {
          setCurrentAgentType(types[0].agent_type)
        }
      } catch (e) {
        console.error('加载 Agent 类型失败', e)
      }
    }
    loadAgentTypes()
  }, [])
  
  // 加载日志查询配置选项（仅在切换到日志排查 Agent 时加载）
  useEffect(() => {
    if (currentAgentType !== 'log_troubleshoot') return
    if (businessLines.length > 0) return  // 已加载过则不重复请求
    
    const loadLogQueryOptions = async () => {
      try {
        const options = await fetchLogQueryOptions()
        if (options?.businessLines) {
          setBusinessLines(options.businessLines)
          // 默认选中第一个业务线
          if (options.businessLines.length > 0) {
            setBusinessLine(options.businessLines[0].value)
          }
        }
        if (options?.privateServers) {
          setPrivateServers(options.privateServers)
        }
      } catch (e) {
        console.error('加载日志查询配置失败', e)
      }
    }
    loadLogQueryOptions()
  }, [currentAgentType])
  
  // 点击外部关闭下拉菜单
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      if (!target.closest('.agent-dropdown-wrapper')) {
        setIsAgentDropdownOpen(false)
      }
      if (!target.closest('.log-dropdown-wrapper')) {
        setIsBusinessLineOpen(false)
        setIsPrivateServerOpen(false)
      }
      if (!target.closest('.file-tools-wrapper')) {
        setIsFileToolsOpen(false)
      }
    }
    if (isAgentDropdownOpen || isBusinessLineOpen || isPrivateServerOpen || isFileToolsOpen) {
      document.addEventListener('click', handleClickOutside)
      return () => document.removeEventListener('click', handleClickOutside)
    }
  }, [isAgentDropdownOpen, isBusinessLineOpen, isPrivateServerOpen, isFileToolsOpen])

  const upsertConversation = useCallback((tid: string, title: string, updatedAt: string, agentType?: string) => {
    if (!tid) return
    setConversations(prev => {
      const existing = prev.find(c => c.threadId === tid)
      const others = prev.filter(c => c.threadId !== tid)
      const item: ConversationSummary = {
        threadId: tid,
        title: title || existing?.title || '新对话',
        agentType: agentType || existing?.agentType,
        updatedAt,
      }
      return [item, ...others]
    })
  }, [])

  // 监听流式内容变化，节流更新消息（使用 RAF 避免过于频繁的重渲染）
  useEffect(() => {
    if (messages.length === 0 || (!isLoading && !isTyping)) return
    
    // 存储待更新的内容
    pendingContentRef.current = streamingContent
    
    // 如果已有 RAF 在等待，直接返回（节流）
    if (updateMessageRafRef.current !== null) return
    
    // 使用 RAF 进行节流更新
    updateMessageRafRef.current = requestAnimationFrame(() => {
      updateMessageRafRef.current = null
      const content = pendingContentRef.current
      
      // 查找正在加载的assistant消息（可能不是最后一条，比如regenerate时）
      setMessages(prev => {
        const newPrev = [...prev]
        let updated = false
        
        // 从后往前找第一个isThinking=true的assistant消息
        for (let i = newPrev.length - 1; i >= 0; i--) {
          if (newPrev[i].role === 'assistant' && newPrev[i].isThinking) {
            newPrev[i] = {
              ...newPrev[i],
              content: content,
            }
            updated = true
            break
          }
        }
        
        // 如果没找到isThinking的，更新最后一条assistant消息（兼容旧逻辑）
        if (!updated && isLoading) {
          const lastIdx = newPrev.length - 1
          if (lastIdx >= 0 && newPrev[lastIdx].role === 'assistant') {
            newPrev[lastIdx] = {
              ...newPrev[lastIdx],
              content: content,
            }
          }
        }
        
        return newPrev
      })
    })
    
    return () => {
      // 清理 RAF
      if (updateMessageRafRef.current !== null) {
        cancelAnimationFrame(updateMessageRafRef.current)
        updateMessageRafRef.current = null
      }
    }
  }, [streamingContent, isLoading, isTyping, messages.length])

  // 自动高度 textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 200) + 'px'
    }
  }, [inputValue])
  
  // 启用拖拽和粘贴上传
  useEffect(() => {
    const cleanupDragDrop = enableDragDrop()
    const cleanupPaste = enablePaste()
    
    return () => {
      cleanupDragDrop()
      cleanupPaste()
    }
  }, [enableDragDrop, enablePaste])

  // 发送消息逻辑
  const sendMessage = useCallback(async (content?: string) => {
    const question = (content || inputValue).trim()
    
    // 允许无文本但有附件的情况
    if (!question && uploadedFiles.length === 0) return
    if (isLoading) return

    // 1. 添加 User 消息（包含附件）
    const userAttachments: FileAttachment[] = uploadedFiles.map(file => ({
      file_id: file.id,
      url: file.url,
      type: file.type as 'image' | 'document' | 'audio' | 'video' | 'unknown',
      filename: file.filename,
      content_type: file.contentType,
    }))
    
    const userMessage: DisplayMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: question || '请分析这些文件',
      attachments: userAttachments.length > 0 ? userAttachments : undefined,
    }
    
    // 2. 添加 Assistant 占位消息 (Loading 状态)
    const assistantMessageId = `assistant-${Date.now()}`
    const assistantMessage: DisplayMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      toolCalls: [],
      isThinking: true, // 初始状态为思考中
    }

    setMessages(prev => [...prev, userMessage, assistantMessage])
    setInputValue('')
    clearFiles()  // 清空附件列表
    setIsLoading(true)
    resetTypewriter()
    fullContentRef.current = ''
    currentToolCallsRef.current = []
    toolCallIdRef.current = 0  // 重置工具调用 ID 计数器
    // 清空工具状态（使用 ref.clear() 避免创建新 Map）
    toolSummariesRef.current.clear()
    activeToolsRef.current.clear()
    setToolSummariesVersion(v => v + 1)
    setActiveToolsVersion(v => v + 1)
    setCurrentTool(null)
    userScrolledUpRef.current = false
    
    // 发送消息后强制滚动到底部
    setTimeout(() => scrollToBottom(true), 50)

    // 3. 启动 WebSocket
    const client = createChatClient()
    chatClientRef.current = client

    // 构建请求参数
    const requestPayload: any = {
      question: question || '请分析这些文件',
      thread_id: threadId || undefined,
      agent_type: currentAgentType,
    }
    
    // 添加文件附件
    if (uploadedFiles.length > 0) {
      requestPayload.attachments = uploadedFiles.map(file => ({
        file_id: file.id,
        url: file.url,
        type: file.type,
        filename: file.filename,
        content_type: file.contentType,
      }))
    }
    
    // 日志排查 Agent 需要传递 log_query
    if (currentAgentType === 'log_troubleshoot') {
      requestPayload.log_query = {
        businessLine,
        privateServer: privateServer || null,
      }
    }
    
    client.start(
      requestPayload,
      {
        onStart: (_rid, newThreadId) => {
          setThreadId(newThreadId)
          setActiveConversationId(newThreadId)
          
          // 立即将对话添加到历史列表（不等 AI 回复完成）
          const isNewConversation = !threadId
          if (isNewConversation && newThreadId) {
            upsertConversation(newThreadId, '新对话', new Date().toISOString(), currentAgentType)
          }
        },
        
        onStream: (chunk) => {
          // 收到文本流
          fullContentRef.current += chunk
          appendToTypewriter(chunk)
          
          // 判断是否是真正的正文内容（不是think标签、不是工具占位符）
          const isRealContent = !chunk.includes('<think>') && 
                               !chunk.includes('</think>') && 
                               !chunk.includes('<!--TOOL:')
          
          // 只有在收到真正的正文时，才关闭thinking状态
          if (isRealContent && chunk.trim()) {
            setMessages(prev => {
               const newPrev = [...prev]
               const lastIdx = newPrev.length - 1
               if (lastIdx >= 0 && newPrev[lastIdx].id === assistantMessageId) {
                 newPrev[lastIdx].isThinking = false // 开始输出正文，停止纯思考动画
               }
               return newPrev
            })
          }
        },
        
        onToolStart: (name, _input, toolId, batch) => {
          // 不再插入占位符（后端已经通过 stream 发送了）
          // 只更新工具状态
          
          // 记录当前工具 ID（用于 onToolEnd 时关联摘要）
          if (toolId) {
            currentToolIdRef.current = toolId
          } else {
            // 如果后端没有发 toolId，退化为计数器（兼容旧版本）
            toolCallIdRef.current += 1
            currentToolIdRef.current = toolCallIdRef.current
          }
          
          // 记录活跃工具的批次信息
          if (toolId && batch) {
            const toolInfo = {
              toolId,
              batchId: batch.batchId,
              batchSize: batch.batchSize,
              batchIndex: batch.batchIndex,
            }
            
            // 保存到 ref 并触发版本更新
            activeToolsRef.current.set(toolId, toolInfo)
            setActiveToolsVersion(v => v + 1)
          }
          
          setCurrentTool(name)
          
          // 更新消息状态：显示正在调用工具
          setMessages(prev => {
             const newPrev = [...prev]
             const lastIdx = newPrev.length - 1
             if (lastIdx >= 0 && newPrev[lastIdx].id === assistantMessageId) {
               newPrev[lastIdx].isThinking = true
               newPrev[lastIdx].currentToolName = name
             }
             return newPrev
          })
        },
        
        onToolEnd: (name, inputSummary, outputSummary, elapsed, toolId, batch) => {
          const finalToolId = toolId ?? currentToolIdRef.current
          setCurrentTool(null)
          // 记录工具调用
          currentToolCallsRef.current.push({ name, output_length: 0 })
          
          // 把摘要存入 ref（包含批次信息和耗时）
          const toolKey = `${name}:${finalToolId}`
          toolSummariesRef.current.set(toolKey, { 
            input: inputSummary, 
            output: outputSummary,
            elapsed: elapsed,
            batchId: batch?.batchId,
            batchSize: batch?.batchSize,
            batchIndex: batch?.batchIndex,
          })
          setToolSummariesVersion(v => v + 1)
          
          // 从活跃工具中移除
          if (finalToolId) {
            activeToolsRef.current.delete(finalToolId)
            setActiveToolsVersion(v => v + 1)
          }
          
          setMessages(prev => {
             const newPrev = [...prev]
             const lastIdx = newPrev.length - 1
             if (lastIdx >= 0 && newPrev[lastIdx].id === assistantMessageId) {
               newPrev[lastIdx].toolCalls = [...currentToolCallsRef.current]
               newPrev[lastIdx].isThinking = true
               newPrev[lastIdx].currentToolName = undefined // 清除当前工具名
             }
             return newPrev
          })
        },
        
        onResult: (content, resultThreadId, toolCalls) => {
          // 最终结果 - 触发打字机加速清空缓冲区
          finishTypewriter()
          
          // 快照当前工具摘要（后续会清空 ref，需要先复制一份）
          const snapshotToolSummaries = new Map(toolSummariesRef.current)
          
          // 更新元数据和状态（但不替换content，让打字机继续播放）
          setMessages(prev => {
            const newPrev = [...prev]
            const lastIdx = newPrev.findIndex(m => m.id === assistantMessageId)
            if (lastIdx !== -1) {
              newPrev[lastIdx] = {
                ...newPrev[lastIdx],
                toolCalls: toolCalls.length > 0 ? toolCalls : currentToolCallsRef.current,
                isThinking: false,
                toolSummaries: snapshotToolSummaries.size > 0 ? snapshotToolSummaries : undefined,
              }
            }
            return newPrev
          })
          
          setIsLoading(false)
          chatClientRef.current = null
          
          // 兜底：等待打字机真正完成后，确保内容完整
          const ensureComplete = () => {
            // 检查打字机缓冲区是否还有内容
            const bufferLen = bufferLengthRef.current
            if (bufferLen > 0) {
              // 打字机还在工作，等待后重试
              setTimeout(ensureComplete, 200)
              return
            }
            
            // 打字机已完成，确保内容一致
            setMessages(prev => {
              const newPrev = [...prev]
              const lastIdx = newPrev.findIndex(m => m.id === assistantMessageId)
              if (lastIdx !== -1) {
                const finalContent = fullContentRef.current || content
                // 只在内容不一致时更新（避免不必要的重渲染）
                if (newPrev[lastIdx].content !== finalContent) {
                  newPrev[lastIdx] = {
                    ...newPrev[lastIdx],
                    content: finalContent,
                  }
                }
              }
              return newPrev
            })
          }
          // 延迟 500ms 后开始检查（给打字机一点加速时间）
          setTimeout(ensureComplete, 500)
          
          // 延迟处理：生成对话标题（如果是新对话）
          setTimeout(() => {
            const finalThreadId = resultThreadId || threadId
            const isNewConversation = !threadId
            if (finalThreadId && isNewConversation) {
              generateConversationTitle(finalThreadId)
                .then(title => {
                  upsertConversation(finalThreadId, title, new Date().toISOString(), currentAgentType)
                })
                .catch(e => console.warn('生成标题失败', e))
            }
          }, 200)
        },
        
        onError: (err) => {
          console.error(err)
          finishTypewriter()
          // 更新最后一条 assistant 消息为错误状态，保留已有内容
          setMessages(prev => {
            const newPrev = [...prev]
            const lastIdx = newPrev.findIndex(m => m.id === assistantMessageId)
            if (lastIdx !== -1) {
              const existingContent = newPrev[lastIdx].content || ''
              newPrev[lastIdx] = {
                ...newPrev[lastIdx],
                content: existingContent + `\n\n⚠️ 发生错误: ${err}`,
                isThinking: false,
                currentToolName: undefined,
              }
            }
            return newPrev
          })
          setIsLoading(false)
          setCurrentTool(null)
          chatClientRef.current = null
        }
      }
    )
  }, [inputValue, isLoading, threadId, currentAgentType, businessLine, privateServer, upsertConversation, appendToTypewriter, finishTypewriter, resetTypewriter, scrollToBottom])

  const handleStop = () => {
    if (chatClientRef.current) {
      chatClientRef.current.stop()
      chatClientRef.current = null
    }
    setIsLoading(false)
    setMessages(prev => {
      const newPrev = [...prev]
      const lastMsg = newPrev[newPrev.length - 1]
      if (lastMsg.role === 'assistant') {
        newPrev[newPrev.length - 1] = {
          ...lastMsg,
          content: lastMsg.content + '\n\n[已停止生成]',
          isThinking: false
        }
      }
      return newPrev
    })
  }

  const handleClear = () => {
    setMessages([])
    setThreadId(null)
    setActiveConversationId(null)
    resetTypewriter()
    setInputValue('')
  }

  // 精准重新生成指定 AI 回复（通过对应的用户消息索引）
  const handleRegenerate = useCallback((userMsgIndex: number) => {
    if (isLoading || !threadId) return
    
    // 找到对应的 assistant 消息位置（用于更新 UI）
    let userCount = 0
    let targetAssistantIdx = -1
    for (let i = 0; i < messages.length; i++) {
      if (messages[i].role === 'user') {
        if (userCount === userMsgIndex && i + 1 < messages.length && messages[i + 1].role === 'assistant') {
          targetAssistantIdx = i + 1
          break
        }
        userCount++
      }
    }
    if (targetAssistantIdx === -1) return
    
    // 设置目标 assistant 消息为加载状态
    setMessages(prev => prev.map((msg, idx) => 
      idx === targetAssistantIdx 
        ? { ...msg, content: '', isThinking: true, toolCalls: [], currentToolName: undefined }
        : msg
    ))
    setIsLoading(true)
    resetTypewriter()
    fullContentRef.current = ''
    currentToolCallsRef.current = []
    toolCallIdRef.current = 0  // 重置工具调用 ID 计数器
    // 清空工具状态
    toolSummariesRef.current.clear()
    activeToolsRef.current.clear()
    setToolSummariesVersion(v => v + 1)
    setActiveToolsVersion(v => v + 1)
    
    // 使用 RegenerateClient 调用后端
    const client = createRegenerateClient()
    
    client.start(
      { thread_id: threadId, user_msg_index: userMsgIndex },
      {
        onStream: (chunk) => {
          fullContentRef.current += chunk
          appendToTypewriter(chunk)
          
          // 判断是否是真正的正文内容（不是think标签、不是工具占位符）
          const isRealContent = !chunk.includes('<think>') && 
                               !chunk.includes('</think>') && 
                               !chunk.includes('<!--TOOL:')
          
          // 只有在收到真正的正文时，才关闭thinking状态
          if (isRealContent && chunk.trim()) {
            setMessages(prev => prev.map((msg, idx) => 
              idx === targetAssistantIdx 
                ? { ...msg, isThinking: false }
                : msg
            ))
          }
        },
        onToolStart: (name, _input, toolId) => {
          // 不再插入占位符（后端已经通过 stream 发送了）
          // 只更新工具状态
          
          // 记录当前工具 ID（用于 onToolEnd 时关联摘要）
          if (toolId) {
            currentToolIdRef.current = toolId
          } else {
            toolCallIdRef.current += 1
            currentToolIdRef.current = toolCallIdRef.current
          }
          
          setCurrentTool(name)
          setMessages(prev => prev.map((msg, idx) => 
            idx === targetAssistantIdx 
              ? { ...msg, isThinking: true, currentToolName: name }
              : msg
          ))
        },
        onToolEnd: (name, inputSummary, outputSummary, _elapsed) => {
          const toolId = currentToolIdRef.current
          setCurrentTool(null)
          currentToolCallsRef.current.push({ name, output_length: 0 })
          
          // 把摘要存入 ref
          const toolKey = `${name}:${toolId}`
          toolSummariesRef.current.set(toolKey, { input: inputSummary, output: outputSummary })
          setToolSummariesVersion(v => v + 1)
          
          setMessages(prev => prev.map((msg, idx) => 
            idx === targetAssistantIdx 
              ? { 
                  ...msg, 
                  toolCalls: [...currentToolCallsRef.current], 
                  isThinking: true, 
                  currentToolName: undefined 
                }
              : msg
          ))
        },
        onResult: (content, _threadId, toolCalls) => {
          // 触发打字机加速清空缓冲区
          finishTypewriter()
          
          // 快照当前工具摘要（后续会清空 ref，需要先复制一份）
          const snapshotToolSummaries = new Map(toolSummariesRef.current)
          
          // 更新元数据（但不替换content，让打字机继续播放）
          setMessages(prev => prev.map((msg, idx) => 
            idx === targetAssistantIdx 
              ? { 
                  ...msg, 
                  toolCalls: toolCalls.length > 0 ? toolCalls : currentToolCallsRef.current,
                  isThinking: false,
                  currentToolName: undefined,
                  toolSummaries: snapshotToolSummaries.size > 0 ? snapshotToolSummaries : undefined,
                }
              : msg
          ))
          
          setIsLoading(false)
          
          // 兜底：等待打字机真正完成后，确保内容完整
          const ensureComplete = () => {
            const bufferLen = bufferLengthRef.current
            if (bufferLen > 0) {
              setTimeout(ensureComplete, 200)
              return
            }
            setMessages(prev => prev.map((msg, idx) => {
              if (idx !== targetAssistantIdx) return msg
              const finalContent = fullContentRef.current || content
              if (msg.content !== finalContent) {
                return { ...msg, content: finalContent }
              }
              return msg
            }))
          }
          setTimeout(ensureComplete, 500)
        },
        onError: (err) => {
          console.error(err)
          finishTypewriter()
          // 保留已有内容，追加错误信息
          setMessages(prev => prev.map((msg, idx) => 
            idx === targetAssistantIdx 
              ? { ...msg, content: (msg.content || '') + `\n\n⚠️ 重新生成失败: ${err}`, isThinking: false, currentToolName: undefined }
              : msg
          ))
          setIsLoading(false)
          setCurrentTool(null)
        }
      }
    )
  }, [messages, isLoading, threadId, appendToTypewriter, finishTypewriter, resetTypewriter])

  // 回溯到某条用户消息（删除该消息及之后所有消息，将内容填充到输入框）
  const handleRollback = useCallback(async (messageId: string) => {
    if (isLoading) return
    
    const idx = messages.findIndex(m => m.id === messageId)
    if (idx === -1 || messages[idx].role !== 'user') return
    
    const userMessage = messages[idx]
    const userContent = userMessage.content
    const userAttachments = userMessage.attachments
    
    // 计算要保留的对话对数（该用户消息之前有多少个用户消息）
    let keepPairs = 0
    for (let i = 0; i < idx; i++) {
      if (messages[i].role === 'user') {
        keepPairs++
      }
    }
    
    // 调用后端 API 截断持久化的对话历史
    if (threadId) {
      try {
        await truncateConversation(threadId, keepPairs)
      } catch (e) {
        console.error('截断对话历史失败', e)
      }
    }
    
    // 删除该消息及之后的所有消息
    setMessages(prev => prev.slice(0, idx))
    // 将内容填充到输入框，让用户可以修改后发送
    setInputValue(userContent)
    // 恢复附件到输入框
    if (userAttachments && userAttachments.length > 0) {
      // 将 FileAttachment 转换为 UploadedFile 格式
      const restoredFiles = userAttachments.map(att => ({
        id: att.file_id || `restored-${Date.now()}-${Math.random().toString(36).slice(2)}`,
        url: att.url,
        filename: att.filename,
        size: 0,  // 历史记录中没有大小信息
        type: att.type as 'image' | 'document' | 'audio' | 'video' | 'unknown',
        contentType: att.content_type,
      }))
      setFiles(restoredFiles)
    } else {
      clearFiles()
    }
    // 聚焦输入框
    setTimeout(() => inputRef.current?.focus(), 50)
  }, [messages, isLoading, threadId, setFiles, clearFiles])

  const handleSelectConversation = useCallback(async (conv: ConversationSummary) => {
    if (!conv.threadId) return
    setActiveConversationId(conv.threadId)
    setThreadId(conv.threadId)
    // 恢复历史会话的 Agent 类型
    if (conv.agentType) {
      setCurrentAgentType(conv.agentType)
    }
    setIsLoading(true)
    resetTypewriter()

    try {
      const rawMessages = await fetchConversationHistory(conv.threadId)
      
      // 使用统一的转换函数
      const result = convertRawMessagesToDisplay(rawMessages, conv.threadId)
      
      // 更新工具摘要 ref
      toolSummariesRef.current.clear()
      result.toolSummaries.forEach((value, key) => {
        toolSummariesRef.current.set(key, value)
      })
      setToolSummariesVersion(v => v + 1)
      setMessages(result.messages)
      // 历史会话加载完成后，直接定位到底部（不使用动画）
      setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'instant' })
      }, 50)
    } catch (e) {
      console.error('加载会话历史失败', e)
    } finally {
      setIsLoading(false)
    }
  }, [resetTypewriter, scrollToBottom])

  const handleDeleteConversation = async (e: React.MouseEvent, conv: ConversationSummary) => {
    e.stopPropagation()
    const confirmed = await showConfirm({
      title: '删除对话',
      content: '确定要删除该对话吗？删除后无法恢复。',
      okText: '删除',
      okType: 'primary',
      okButtonProps: { danger: true },
    })
    if (!confirmed) return

    try {
      await deleteConversation(conv.threadId)
      setConversations(prev => prev.filter(c => c.threadId !== conv.threadId))
      
      if (activeConversationId === conv.threadId) {
        handleClear()
      }
    } catch (err) {
      console.error('删除失败', err)
    }
  }

  const groupedConversations = groupConversations(conversations)

  return (
    <div className="chat-page-container">
      <div className={`chat-sidebar ${isSidebarCollapsed ? 'collapsed' : ''}`}>
        {/* 导航菜单 */}
        <div className="sidebar-menu">
          <div 
            className={`menu-item ${activeTab === 'chat' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('chat')
              handleClear() // 点击聊天通常意味着新对话
            }}
            title="新建聊天"
          >
            <EditOutlined className="menu-icon" />
            {!isSidebarCollapsed && <span className="menu-text">新建聊天</span>}
          </div>
        </div>

        {/* 历史记录列表 */}
        <div className="conversation-history-container">
          {isSidebarCollapsed ? (
            <div 
              className="menu-item" 
              onClick={() => setIsSidebarCollapsed(false)}
              title="查看历史记录"
            >
              <HistoryOutlined className="menu-icon" />
            </div>
          ) : (
            <>
              <div className="history-header">
                <HistoryOutlined className="history-icon" />
                <span className="history-title">历史记录</span>
              </div>
              
              <div className="conversation-list">
                {conversations.length === 0 ? (
                  <div className="conversation-list-empty">暂无历史</div>
                ) : (
                  groupedConversations.map(group => (
                    <div key={group.label} className="history-group">
                      <div className="history-group-label">{group.label}</div>
                      {group.conversations.map(conv => (
                        <div
                          key={conv.threadId}
                          className={`conversation-item ${conv.threadId === activeConversationId ? 'active' : ''}`}
                          onClick={() => handleSelectConversation(conv)}
                          title={conv.title || '新对话'}
                        >
                          <div className="conversation-item-title">{conv.title || '新对话'}</div>
                          <div 
                             className="conversation-item-delete"
                             onClick={(e) => handleDeleteConversation(e, conv)}
                             title="删除对话"
                          >
                             <DeleteOutlined />
                          </div>
                        </div>
                      ))}
                    </div>
                  ))
                )}
                
                {conversations.length > 0 && (
                   <div className="view-all-history">查看全部</div>
                )}
              </div>
            </>
          )}
        </div>
        
        {/* 底部折叠按钮 */}
        <div className="sidebar-footer">
          <div 
            className="sidebar-collapse-btn" 
            onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
            title={isSidebarCollapsed ? "展开侧边栏" : "收起侧边栏"}
          >
            {isSidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          </div>
        </div>
      </div>

      <div className={`chat-main ${messages.length === 0 ? 'empty-chat' : ''}`}>
        {/* Agent 选择器 - 对话区域左上角 */}
        {agentTypes.length > 0 && (
          <div className="agent-selector-header">
            <div className="agent-dropdown-wrapper">
              <button 
                className="agent-dropdown-trigger"
                onClick={() => setIsAgentDropdownOpen(!isAgentDropdownOpen)}
              >
                <span className="agent-trigger-name">
                  {agentTypes.find(a => a.agent_type === currentAgentType)?.name || 'Agent'}
                </span>
                <DownOutlined className={`agent-trigger-arrow ${isAgentDropdownOpen ? 'open' : ''}`} />
              </button>
              
              {isAgentDropdownOpen && (
                <div className="agent-dropdown-menu">
                  {agentTypes.map(agent => {
                    const isSelected = currentAgentType === agent.agent_type
                    return (
                      <div
                        key={agent.agent_type}
                        className={`agent-dropdown-item ${isSelected ? 'selected' : ''}`}
                        onClick={() => {
                          setCurrentAgentType(agent.agent_type)
                          setIsAgentDropdownOpen(false)
                        }}
                      >
                        <div className="agent-item-content">
                          <span className="agent-item-name">{agent.name}</span>
                          <span className="agent-item-desc">{agent.description}</span>
                        </div>
                        {isSelected && <CheckCircleOutlined className="agent-item-check" />}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
            
            {/* 日志排查配置选择器 - 仅 log_troubleshoot Agent 显示 */}
            {currentAgentType === 'log_troubleshoot' && businessLines.length > 0 && (
              <div className="log-query-selectors">
                {/* 业务线选择器 */}
                <div className="log-dropdown-wrapper">
                  <button
                    className="log-dropdown-trigger"
                    onClick={() => {
                      setIsBusinessLineOpen(!isBusinessLineOpen)
                      setIsPrivateServerOpen(false)
                    }}
                  >
                    <span className="log-trigger-name">{businessLine || '选择业务线'}</span>
                    <DownOutlined className={`log-trigger-arrow ${isBusinessLineOpen ? 'open' : ''}`} />
                  </button>
                  {isBusinessLineOpen && (
                    <div className="log-dropdown-menu">
                      {businessLines.map(opt => (
                        <div
                          key={opt.value}
                          className={`log-dropdown-item ${businessLine === opt.value ? 'selected' : ''}`}
                          onClick={() => handleBusinessLineChange(opt.value)}
                        >
                          <span>{opt.label}</span>
                          {businessLine === opt.value && <CheckCircleOutlined className="log-item-check" />}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                
                {/* 私有化集团选择器 - 仅私有化业务线显示 */}
                {businessLine === '私有化' && privateServers.length > 0 && (
                  <div className="log-dropdown-wrapper">
                    <button
                      className="log-dropdown-trigger"
                      onClick={() => {
                        setIsPrivateServerOpen(!isPrivateServerOpen)
                        setIsBusinessLineOpen(false)
                      }}
                    >
                      <span className="log-trigger-name">{privateServer || '选择集团'}</span>
                      <DownOutlined className={`log-trigger-arrow ${isPrivateServerOpen ? 'open' : ''}`} />
                    </button>
                    {isPrivateServerOpen && (
                      <div className="log-dropdown-menu">
                        {privateServers.map(opt => (
                          <div
                            key={opt.value}
                            className={`log-dropdown-item ${privateServer === opt.value ? 'selected' : ''}`}
                            onClick={() => handlePrivateServerChange(opt.value)}
                          >
                            <span>{opt.label}</span>
                            {privateServer === opt.value && <CheckCircleOutlined className="log-item-check" />}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        <div className="chat-message-list" ref={messageListRef} onScroll={handleScroll}>
          <div className="chat-content-width">
            {messages.length === 0 ? (
              <WelcomeScreen 
                key={`${currentAgentType}-${businessLine || ''}-${privateServer || ''}`}
                onSuggestionClick={(q) => sendMessage(q)} 
                agentType={currentAgentType}
                businessLine={businessLine}
                privateServer={privateServer}
              />
            ) : (
              <>
                {messages.map((msg, idx) => {
                  // 计算该 assistant 消息对应的用户消息索引
                  let userMsgIndex = -1
                  if (msg.role === 'assistant') {
                    let count = 0
                    for (let i = 0; i < idx; i++) {
                      if (messages[i].role === 'user') {
                        userMsgIndex = count
                        count++
                      }
                    }
                  }
                  
                  // 判断是否可以重新生成（非正在生成的消息）
                  const isCurrentlyGenerating = msg.role === 'assistant' && 
                    idx === messages.length - 1 && isLoading
                  const canRegenerate = msg.role === 'assistant' && !isCurrentlyGenerating
                  
                  return (
                    <MessageItem 
                      key={msg.id} 
                      message={msg}
                      isLoading={isLoading}
                      canRegenerate={canRegenerate}
                      onRegenerate={() => userMsgIndex >= 0 && handleRegenerate(userMsgIndex)}
                      onRollback={() => handleRollback(msg.id)}
                      toolSummaries={toolSummaries}
                      activeTools={activeTools}
                      activeToolsRef={activeToolsRef}
                    />
                  )
                })}
                {/* 占位符，用于滚动 */}
                <div ref={messagesEndRef} style={{ height: 1 }} />
              </>
            )}
          </div>
        </div>

        <div className="input-area-wrapper">
          <div className="input-container" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
            {/* 文件预览区域 - 在输入框内部上方 */}
            {(uploadedFiles.length > 0 || pendingFiles.length > 0) && (
              <div style={{ 
                display: 'flex', 
                flexWrap: 'wrap', 
                gap: '6px',
                padding: '8px 8px 6px 8px',  /* 左右都和按钮对齐 */
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
                  
                  {/* 后续可扩展更多功能 */}
                  {/* <div className="file-tools-item" onClick={() => { ... }}>
                    <FileTextOutlined className="file-tools-item-icon" />
                    <div className="file-tools-item-content">
                      <span className="file-tools-item-name">新建文档</span>
                      <span className="file-tools-item-desc">创建临时文档</span>
                    </div>
                  </div> */}
                </div>
              )}
            </div>
            
            <textarea
              ref={inputRef}
              className="chat-textarea"
              placeholder="输入问题，开始探索（支持拖拽/粘贴图片）"
              value={inputValue}
              onChange={e => setInputValue(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  if (!isLoading) {
                    sendMessage()
                  }
                }
              }}
              rows={1}
            />
            
            <div className="action-buttons">
              {isLoading ? (
                <button className="stop-btn" onClick={handleStop} aria-label="停止生成" />
              ) : (
                <button 
                  className="send-btn" 
                  onClick={() => sendMessage()}
                  disabled={!inputValue.trim() && uploadedFiles.length === 0}
                >
                  <ArrowUpOutlined style={{ fontSize: 20, fontWeight: 'bold' }} />
                </button>
              )}
            </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ChatPage

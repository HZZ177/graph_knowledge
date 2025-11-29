import React, { useState, useRef, useEffect, useCallback } from 'react'
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
} from '@ant-design/icons'
import { createChatClient, ChatClient, ToolCallInfo, fetchConversationHistory, generateConversationTitle, listConversations, deleteConversation, truncateConversation, createRegenerateClient, RegenerateClient, ChatMessage } from '../api/llm'
import { useTypewriter } from '../hooks/useTypewriter'
import '../styles/ChatPage.css'
import { showConfirm } from '../utils/confirm'

// ==========================================
// Interfaces
// ==========================================

interface DisplayMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  toolCalls?: ToolCallInfo[]
  isThinking?: boolean // 是否正在思考（等待工具返回）
  currentToolName?: string // 当前正在调用的工具名称
}

interface ConversationSummary {
  threadId: string
  title: string
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

// 1. 欢迎屏幕
const WelcomeScreen: React.FC<{ onSuggestionClick: (q: string) => void }> = ({ onSuggestionClick }) => {
  const suggestions = [
    '开卡流程是怎样的？',
    '订单相关的接口有哪些？',
    '用户表被哪些服务使用？',
    '支付成功后的回调逻辑是什么？',
  ]

  return (
    <div className="welcome-screen">
      <div className="welcome-logo">
        <RobotOutlined />
      </div>
      <h1 className="welcome-title">业务知识助手</h1>
      <p className="welcome-subtitle">
        我可以帮你探索业务流程、接口实现和数据资源。
        <br />基于实时图谱数据，提供准确的技术洞察。
      </p>
      <div className="suggestion-grid">
        {suggestions.map((q, i) => (
          <button key={i} className="suggestion-card" onClick={() => onSuggestionClick(q)}>
            <span className="suggestion-text">{q}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

// 2. 工具调用过程展示（单个调用，一个面板）
interface ToolProcessProps {
  name: string
  isActive: boolean
  inputSummary?: string   // 输入摘要，如 "关键词: 开卡"
  outputSummary?: string  // 输出摘要，如 "找到 3 个结果"
}

const ToolProcess: React.FC<ToolProcessProps> = ({ name, isActive, inputSummary, outputSummary }) => {
  const [isExpanded, setIsExpanded] = useState(isActive)
  const [userToggled, setUserToggled] = useState(false)
  
  // 根据当前是否正在调用自动展开/收起（除非用户手动改动）
  useEffect(() => {
    if (userToggled) return
    setIsExpanded(isActive)
  }, [isActive, userToggled])
  
  if (!name) return null
  const prettyName = name.replace(/_/g, ' ')
  
  // 构建标签：进行中显示动画，完成后显示结果摘要
  let label: React.ReactNode
  if (isActive) {
    label = <span className="status-text">Searching {prettyName}</span>
  } else if (outputSummary) {
    label = `${prettyName} · ${outputSummary}`
  } else {
    label = `Searched ${prettyName}`
  }

  const handleToggle = () => {
    setUserToggled(true)
    setIsExpanded(!isExpanded)
  }

  return (
    <div className={`inline-expandable ${isExpanded ? 'expanded' : ''}`}>
      <span className="inline-expandable-toggle" onClick={handleToggle}>
        {label}
        <span className="inline-chevron">›</span>
      </span>
      <div className="inline-expandable-content">
        {/* 输入摘要 */}
        {inputSummary && (
          <div className="tool-summary-item">
            <span className="tool-summary-label">查询:</span> {inputSummary}
          </div>
        )}
        {/* 输出摘要 */}
        {outputSummary && !isActive && (
          <div className="tool-summary-item">
            <span className="tool-summary-label">结果:</span> {outputSummary}
          </div>
        )}
        {/* 进行中状态 */}
        {isActive && (
          <div className={`inline-expandable-item active`}>
            正在执行...
          </div>
        )}
      </div>
    </div>
  )
}

// 3. 内容段落类型定义
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
}

/**
 * 解析内容为有序的段落列表
 * 支持 <think> 块、工具占位符 <!--TOOL:name:id--> 和正文交错
 */
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
      // 如果当前在 think 中，先结束未闭合的 think 段（认为是不完整的思考块）
      if (inThink) {
        const raw = buffer
        const trimmed = raw.trim()
        if (trimmed) {
          segments.push({
            type: 'think',
            content: trimmed,
            startPos: thinkStartPos >= 0 ? thinkStartPos : bufferStart,
            endPos: i,
            isComplete: false,
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
      <div className="inline-expandable-content think-text markdown-body">
        <MarkdownPreview 
          source={content} 
          style={{ background: 'transparent', fontSize: 14 }}
          wrapperElement={{ 'data-color-mode': 'light' }}
        />
      </div>
    </div>
  )
}

// 5. 消息气泡
interface MessageItemProps {
  message: DisplayMessage
  isLoading?: boolean
  canRegenerate?: boolean  // 是否可以重新生成（非最后一条正在生成的消息）
  onRegenerate?: () => void
  onRollback?: () => void
  toolSummaries?: Map<string, {input: string, output: string}>  // 工具摘要
}

// 渲染项类型：用于交错排列思考、工具、正文
interface RenderItem {
  type: 'think' | 'tool' | 'text'
  key: string
  // think 类型
  thinkContent?: string
  isThinkStreaming?: boolean
  isThinkComplete?: boolean
  // tool 类型
  toolName?: string
  toolIsActive?: boolean
  toolInputSummary?: string
  toolOutputSummary?: string
  // text 类型
  textContent?: string
}

/**
 * 构建交错渲染列表
 * 直接从 parseContentSegments 的结果构建，工具占位符已嵌入 content
 */
const buildRenderItems = (
  content: string,
  currentToolName?: string,
  toolSummaries?: Map<string, {input: string, output: string}>
): RenderItem[] => {
  const segments = parseContentSegments(content, currentToolName, toolSummaries)
  
  // DEBUG: 打印解析结果
  console.log('[buildRenderItems] segments:', segments.map(s => ({
    type: s.type,
    content: s.content.slice(0, 50) + (s.content.length > 50 ? '...' : ''),
    isComplete: s.isComplete
  })))
  
  return segments.map((seg, idx) => {
    if (seg.type === 'think') {
      return {
        type: 'think' as const,
        key: `think-${idx}-${seg.startPos}`,
        thinkContent: seg.content,
        isThinkStreaming: !seg.isComplete,
        isThinkComplete: seg.isComplete
      }
    } else if (seg.type === 'tool') {
      return {
        type: 'tool' as const,
        key: `tool-${idx}-${seg.content}`,
        toolName: seg.content,
        toolIsActive: seg.isToolActive,
        toolInputSummary: seg.inputSummary,
        toolOutputSummary: seg.outputSummary,
      }
    } else {
      return {
        type: 'text' as const,
        key: `text-${idx}-${seg.startPos}`,
        textContent: seg.content
      }
    }
  })
}

const MessageItem: React.FC<MessageItemProps> = ({ message, isLoading, canRegenerate, onRegenerate, onRollback, toolSummaries }) => {
  const isUser = message.role === 'user'
  
  // 用户消息直接渲染
  if (isUser) {
    return (
      <div className={`message-item user`}>
        <div className="message-bubble-wrapper">
          <div className="message-bubble">
            <div className="markdown-body">{message.content}</div>
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
  
  // Assistant 消息：构建交错渲染列表（工具占位符已嵌入 content）
  const renderItems = buildRenderItems(message.content, message.currentToolName, toolSummaries)
  
  // 初始思考状态：正在思考但还没有任何内容
  const isInitialThinking = message.isThinking && renderItems.length === 0
  
  // 检查是否有正文内容
  const hasTextContent = renderItems.some(item => item.type === 'text' && item.textContent)
  
  // 工具已结束但正文尚未输出
  const hasFinishedTools = renderItems.some(item => item.type === 'tool') && !message.currentToolName
  const isWaitingMainAfterTools = hasFinishedTools && !hasTextContent && !!message.isThinking
  
  return (
    <div className={`message-item assistant`}>
      <div className="message-header">
        <div className="avatar assistant">
          <RobotOutlined />
        </div>
        <span className="role-name">Graph AI</span>
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
                />
              )
            }
            if (item.type === 'text') {
              return (
                <div key={item.key} className="markdown-body">
                  <MarkdownPreview
                    source={item.textContent || ''}
                    style={{ background: 'transparent', fontSize: 16 }}
                    wrapperElement={{ "data-color-mode": "light" }}
                  />
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
}

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
  
  // 实时状态
  const [currentTool, setCurrentTool] = useState<string | null>(null)
  const fullContentRef = useRef('') 
  const currentToolCallsRef = useRef<ToolCallInfo[]>([])
  const toolCallIdRef = useRef(0)  // 工具调用唯一 ID 计数器
  const currentToolIdRef = useRef(0)  // 当前正在执行的工具 ID
  // 工具摘要存储：key = "toolName:id", value = {input, output}
  const [toolSummaries, setToolSummaries] = useState<Map<string, {input: string, output: string}>>(new Map())
  
  const chatClientRef = useRef<ChatClient | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messageListRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const userScrolledUpRef = useRef(false)

  // 滚动到底部（只在用户未主动上滑时执行）
  const scrollToBottom = useCallback((force = false) => {
    if (!force && userScrolledUpRef.current) return
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  // 检测用户是否滚动到底部附近
  const isNearBottom = useCallback(() => {
    const container = messageListRef.current
    if (!container) return true
    const threshold = 100 // 距离底部100px内认为在底部
    return container.scrollHeight - container.scrollTop - container.clientHeight < threshold
  }, [])

  // 监听滚动事件
  const handleScroll = useCallback(() => {
    if (isNearBottom()) {
      userScrolledUpRef.current = false
    } else if (isLoading) {
      // 只有在加载中时，用户上滑才标记为打断
      userScrolledUpRef.current = true
    }
  }, [isNearBottom, isLoading])

  // 打字机 Hook
  const { text: streamingContent, append: appendToTypewriter, finish: finishTypewriter, reset: resetTypewriter, isTyping } = useTypewriter({
    onTick: scrollToBottom,
    normalSpeed: { min: 10, max: 30 }, // 更快的打字速度
  })

  // 加载本地存储的会话列表
  useEffect(() => {
    const loadConversations = async () => {
      try {
        const data = await listConversations()
        const summaries: ConversationSummary[] = data.map(c => ({
          threadId: c.id,
          title: c.title || '新对话',
          updatedAt: c.updated_at,
        }))
        setConversations(summaries)
      } catch (e) {
        console.error('加载会话列表失败', e)
      }
    }
    loadConversations()
  }, [])

  const upsertConversation = useCallback((tid: string, title: string, updatedAt: string) => {
    if (!tid) return
    setConversations(prev => {
      const existing = prev.find(c => c.threadId === tid)
      const others = prev.filter(c => c.threadId !== tid)
      const item: ConversationSummary = {
        threadId: tid,
        title: title || existing?.title || '新对话',
        updatedAt,
      }
      return [item, ...others]
    })
  }, [])

  // 监听流式内容变化，更新最后一条消息
  useEffect(() => {
    if (messages.length === 0) return
    
    const lastMsg = messages[messages.length - 1]
    if (lastMsg.role === 'assistant' && isLoading) {
      setMessages(prev => {
        const newPrev = [...prev]
        newPrev[newPrev.length - 1] = {
          ...newPrev[newPrev.length - 1],
          content: streamingContent,
          // 如果正在打字，说明还在输出
          // 如果 currentTool 不为空，说明正在思考
        }
        return newPrev
      })
    }
  }, [streamingContent, isLoading])

  // 自动高度 textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 200) + 'px'
    }
  }, [inputValue])

  // 发送消息逻辑
  const sendMessage = useCallback(async (content?: string) => {
    const question = (content || inputValue).trim()
    if (!question || isLoading) return

    // 1. 添加 User 消息
    const userMessage: DisplayMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: question,
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
    setIsLoading(true)
    resetTypewriter()
    fullContentRef.current = ''
    currentToolCallsRef.current = []
    toolCallIdRef.current = 0  // 重置工具调用 ID 计数器
    setToolSummaries(new Map())  // 清空工具摘要
    setCurrentTool(null)
    userScrolledUpRef.current = false
    
    // 发送消息后强制滚动到底部
    setTimeout(() => scrollToBottom(true), 50)

    // 3. 启动 WebSocket
    const client = createChatClient()
    chatClientRef.current = client

    client.start(
      { question, thread_id: threadId || undefined },
      {
        onStart: (_rid, newThreadId) => {
          setThreadId(newThreadId)
          setActiveConversationId(newThreadId)
        },
        
        onStream: (chunk) => {
          // 收到文本流，说明不再是纯思考状态，开始输出了
          fullContentRef.current += chunk
          appendToTypewriter(chunk)
          
          // 更新状态：不再仅仅是思考，而是有内容了
          setMessages(prev => {
             const newPrev = [...prev]
             const lastIdx = newPrev.length - 1
             if (lastIdx >= 0 && newPrev[lastIdx].id === assistantMessageId) {
               newPrev[lastIdx].isThinking = false // 开始输出文本，停止纯思考动画
             }
             return newPrev
          })
        },
        
        onToolStart: (name, _input, toolId) => {
          // 不再插入占位符（后端已经通过 stream 发送了）
          // 只更新工具状态
          console.log('Tool Start:', name, 'id:', toolId)
          
          // 记录当前工具 ID（用于 onToolEnd 时关联摘要）
          if (toolId) {
            currentToolIdRef.current = toolId
          } else {
            // 如果后端没有发 toolId，退化为计数器（兼容旧版本）
            toolCallIdRef.current += 1
            currentToolIdRef.current = toolCallIdRef.current
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
        
        onToolEnd: (name, inputSummary, outputSummary, _elapsed) => {
          const toolId = currentToolIdRef.current
          console.log('Tool End:', name, 'id:', toolId, inputSummary, outputSummary)
          setCurrentTool(null)
          // 记录工具调用
          currentToolCallsRef.current.push({ name, output_length: 0 })
          
          // 把摘要存入 state（不再替换内容）
          const toolKey = `${name}:${toolId}`
          setToolSummaries(prev => {
            const newMap = new Map(prev)
            newMap.set(toolKey, { input: inputSummary, output: outputSummary })
            return newMap
          })
          
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
          // 最终结果
          finishTypewriter()
          
          // 更新最终状态
          setTimeout(() => {
            setMessages(prev => {
              const newPrev = [...prev]
              const lastIdx = newPrev.findIndex(m => m.id === assistantMessageId)
              if (lastIdx !== -1) {
                newPrev[lastIdx] = {
                  ...newPrev[lastIdx],
                  content: fullContentRef.current || content,
                  toolCalls: toolCalls.length > 0 ? toolCalls : currentToolCallsRef.current,
                  isThinking: false,
                }
              }
              return newPrev
            })
            setIsLoading(false)
            chatClientRef.current = null
            const finalThreadId = resultThreadId || threadId
            if (finalThreadId) {
              const isNewConversation = !threadId
              upsertConversation(finalThreadId, isNewConversation ? '新对话' : '', new Date().toISOString())
              setActiveConversationId(finalThreadId)
              setThreadId(finalThreadId)
              
              // 如果是新对话，触发标题生成
              if (isNewConversation) {
                generateConversationTitle(finalThreadId)
                  .then(title => {
                    upsertConversation(finalThreadId, title, new Date().toISOString())
                  })
                  .catch(e => console.warn('生成标题失败', e))
              }
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
  }, [inputValue, isLoading, threadId, appendToTypewriter, finishTypewriter, resetTypewriter])

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
    setToolSummaries(new Map())  // 清空工具摘要
    
    // 使用 RegenerateClient 调用后端
    const client = createRegenerateClient()
    
    client.start(
      { thread_id: threadId, user_msg_index: userMsgIndex },
      {
        onStream: (chunk) => {
          fullContentRef.current += chunk
          appendToTypewriter(chunk)
          setMessages(prev => prev.map((msg, idx) => 
            idx === targetAssistantIdx 
              ? { ...msg, content: fullContentRef.current, isThinking: false }
              : msg
          ))
        },
        onToolStart: (name, _input, toolId) => {
          // 不再插入占位符（后端已经通过 stream 发送了）
          // 只更新工具状态
          console.log('Regenerate Tool Start:', name, 'id:', toolId)
          
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
          
          // 把摘要存入 state（不再替换内容）
          const toolKey = `${name}:${toolId}`
          setToolSummaries(prev => {
            const newMap = new Map(prev)
            newMap.set(toolKey, { input: inputSummary, output: outputSummary })
            return newMap
          })
          
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
          finishTypewriter()
          setTimeout(() => {
            setMessages(prev => prev.map((msg, idx) => 
              idx === targetAssistantIdx 
                ? { 
                    ...msg, 
                    content: fullContentRef.current || content,
                    toolCalls: toolCalls.length > 0 ? toolCalls : currentToolCallsRef.current,
                    isThinking: false,
                    currentToolName: undefined,
                  }
                : msg
            ))
            setIsLoading(false)
          }, 200)
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
    
    const userContent = messages[idx].content
    
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
    // 聚焦输入框
    setTimeout(() => inputRef.current?.focus(), 50)
  }, [messages, isLoading, threadId])

  const handleSelectConversation = useCallback(async (conv: ConversationSummary) => {
    if (!conv.threadId) return
    setActiveConversationId(conv.threadId)
    setThreadId(conv.threadId)
    setIsLoading(true)
    resetTypewriter()

    try {
      const msgs = await fetchConversationHistory(conv.threadId)

      const display: DisplayMessage[] = []
      let pendingToolCalls: Array<{ name: string; output_length: number; args?: Record<string, unknown> }> = []
      let globalToolId = 0  // 全局工具调用 ID 计数器
      const historySummaries = new Map<string, { input: string; output: string }>()  // 历史工具摘要

      msgs.forEach((m, i) => {
        if (m.role === 'user') {
          display.push({
            id: `user-${i}-${conv.threadId}`,
            role: 'user',
            content: m.content,
          })
        } else if (m.role === 'assistant') {
          if (m.tool_calls && m.tool_calls.length > 0) {
            // assistant 发起工具调用，记录待插入的工具（累积当前轮所有调用）
            const newCalls = m.tool_calls.map(tc => ({ 
              name: tc.name, 
              output_length: 0,
              args: tc.args  // 保存参数用于生成摘要
            }))
            pendingToolCalls.push(...newCalls)
          } else if (m.content) {
            // assistant 内容：在 think 块之后插入工具占位符
            let contentWithTools = m.content
            if (pendingToolCalls.length > 0) {
              // 找到 </think> 的位置，在其后插入工具占位符（带唯一 ID）
              const thinkEndIdx = contentWithTools.indexOf('</think>')
              const toolMarkers = pendingToolCalls.map(tc => {
                globalToolId++
                // 生成简单的输入摘要
                let inputSummary = ''
                if (tc.args) {
                  const firstKey = Object.keys(tc.args)[0]
                  if (firstKey) {
                    const val = String(tc.args[firstKey])
                    inputSummary = val.length > 30 ? val.slice(0, 30) + '...' : val
                  }
                }
                // 存入摘要 Map
                historySummaries.set(`${tc.name}:${globalToolId}`, {
                  input: inputSummary,
                  output: tc.output_length > 0 ? `返回 ${tc.output_length} 字符` : '已完成'
                })
                return `<!--TOOL:${tc.name}:${globalToolId}-->`
              }).join('')
              if (thinkEndIdx !== -1) {
                // 在 </think> 之后插入
                const insertPos = thinkEndIdx + 8
                contentWithTools =
                  contentWithTools.slice(0, insertPos) +
                  toolMarkers +
                  contentWithTools.slice(insertPos)
              } else {
                // 没有 think 块，在开头插入
                contentWithTools = toolMarkers + contentWithTools
              }
            }
            display.push({
              id: `assistant-${i}-${conv.threadId}`,
              role: 'assistant',
              content: contentWithTools,
              toolCalls: pendingToolCalls.length > 0 ? pendingToolCalls.map(tc => ({ name: tc.name, output_length: tc.output_length })) : undefined,
            })
            pendingToolCalls = []
          }
        } else if (m.role === 'tool') {
          // tool 返回，更新对应工具的 output_length
          const toolIdx = pendingToolCalls.findIndex(tc => tc.name === m.tool_name)
          if (toolIdx !== -1) {
            pendingToolCalls[toolIdx].output_length = m.content.length
          }
        }
      })

      // 设置历史工具摘要
      setToolSummaries(historySummaries)
      setMessages(display)
    } catch (e) {
      console.error('加载会话历史失败', e)
    } finally {
      setIsLoading(false)
    }
  }, [resetTypewriter])

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

      <div className="chat-main">
        <div className="chat-message-list" ref={messageListRef} onScroll={handleScroll}>
          <div className="chat-content-width">
            {messages.length === 0 ? (
              <WelcomeScreen onSuggestionClick={(q) => sendMessage(q)} />
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
          <div className="input-container">
            <textarea
              ref={inputRef}
              className="chat-textarea"
              placeholder="输入你的问题..."
              value={inputValue}
              onChange={e => setInputValue(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  sendMessage()
                }
              }}
              disabled={isLoading}
              rows={1}
            />
            
            <div className="action-buttons">
              {isLoading ? (
                <button className="stop-btn" onClick={handleStop} aria-label="停止生成" />
              ) : (
                <button 
                  className="send-btn" 
                  onClick={() => sendMessage()}
                  disabled={!inputValue.trim()}
                >
                  <ArrowUpOutlined style={{ fontSize: 20, fontWeight: 'bold' }} />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ChatPage

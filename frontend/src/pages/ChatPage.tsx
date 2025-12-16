/**
 * ChatPage - 重构后的聊天页面
 * 
 * 将大量子组件和工具函数拆分到独立文件：
 * - types/chat.ts: 类型定义
 * - utils/chatUtils.ts: 工具函数
 * - components/chat/*: UI 组件
 */

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { CheckCircleOutlined, LoadingOutlined, ArrowDownOutlined } from '@ant-design/icons'
import {
  createChatClient,
  ChatClient,
  ToolCallInfo,
  fetchConversationHistory,
  fetchTestingHistory,
  generateConversationTitle,
  listConversations,
  deleteConversation,
  truncateConversation,
  createRegenerateClient,
  AgentType,
  fetchAgentTypes,
  fetchLogQueryOptions,
  LogQueryOption,
  FileAttachment,
  fetchTestingSessionStatus,
  TestingSessionStatus,
} from '../api/llm'
import { fetchIterations, fetchIssues, IterationInfo, IssueInfo } from '../api/coding'
import { showWarning } from '../utils/message'
import { showConfirm } from '../utils/confirm'
import { useTypewriter } from '../hooks/useTypewriter'
import { useFileUpload } from '../hooks/useFileUpload'
import { useTestingTaskBoard, TestingWSMessage, PhaseId } from '../hooks/useTestingTaskBoard'
import '../styles/ChatPage.css'

// 导入拆分的类型
import {
  ToolSummaryInfo,
  DisplayMessage,
  ConversationSummary,
  ActiveToolInfo,
  ToolProgressStep,
} from '../types/chat'

// 导入拆分的工具函数
import {
  convertRawMessagesToDisplay,
  groupConversations,
} from '../utils/chatUtils'

// 导入拆分的组件
import {
  WelcomeScreen,
  MessageItem,
  ConversationSidebar,
  AgentSelectorHeader,
  TestingTaskPanel,
  ChatInputArea,
} from '../components/chat'

// ==========================================
// Constants
// ==========================================

const TESTING_PROJECT_NAME = 'yongcepingtaipro2.0'
const CONVERSATIONS_STORAGE_KEY = 'graph_chat_conversations_v1'

// ==========================================
// Main Page Component
// ==========================================

const ChatPage: React.FC = () => {
  // ========== 状态定义 ==========
  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isHistoryLoading, setIsHistoryLoading] = useState(false)
  const [isConversationsLoading, setIsConversationsLoading] = useState(true)
  const [threadId, setThreadId] = useState<string | null>(null)
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'chat' | 'voice' | 'imagine' | 'projects'>('chat')
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)
  
  // Agent 类型状态
  const [agentTypes, setAgentTypes] = useState<AgentType[]>([])
  const [currentAgentType, setCurrentAgentType] = useState<string>('knowledge_qa')
  const [isAgentDropdownOpen, setIsAgentDropdownOpen] = useState(false)
  
  // 日志查询配置
  const [businessLines, setBusinessLines] = useState<LogQueryOption[]>([])
  const [privateServers, setPrivateServers] = useState<LogQueryOption[]>([])
  const [businessLine, setBusinessLine] = useState<string>('')
  const [privateServer, setPrivateServer] = useState<string | null>(null)
  
  // 智能测试配置
  const [iterations, setIterations] = useState<IterationInfo[]>([])
  const [issues, setIssues] = useState<IssueInfo[]>([])
  const [selectedIteration, setSelectedIteration] = useState<IterationInfo | null>(null)
  const [selectedIssue, setSelectedIssue] = useState<IssueInfo | null>(null)
  const [iterationSearchText, setIterationSearchText] = useState('')
  const [issueSearchText, setIssueSearchText] = useState('')
  const [isIterationLoading, setIsIterationLoading] = useState(false)
  const [isIssueLoading, setIsIssueLoading] = useState(false)
  
  // 测试助手阶段管理
  const [testingSessionId, setTestingSessionId] = useState<string | null>(null)
  const [testingActivePhase, setTestingActivePhase] = useState<PhaseId>('analysis')
  const [testingSessionStatus, setTestingSessionStatus] = useState<TestingSessionStatus | null>(null)
  const [testingPhaseMessages, setTestingPhaseMessages] = useState<{
    analysis: DisplayMessage[]
    plan: DisplayMessage[]
    generate: DisplayMessage[]
  }>({ analysis: [], plan: [], generate: [] })
  
  // 下拉框展开状态
  const [isBusinessLineOpen, setIsBusinessLineOpen] = useState(false)
  const [isPrivateServerOpen, setIsPrivateServerOpen] = useState(false)
  const [isIterationOpen, setIsIterationOpen] = useState(false)
  const [isIssueOpen, setIsIssueOpen] = useState(false)
  const [isFileToolsOpen, setIsFileToolsOpen] = useState(false)
  const [showScrollToBottom, setShowScrollToBottom] = useState(false)
  
  // 智能测试任务看板 Hook
  const {
    tasks: testingTasks,
    phases: testingPhases,
    currentPhase: testingCurrentPhase,
    viewingPhase: testingViewingPhase,
    isRunning: isTestingRunning,
    handleMessage: handleTestingMessage,
    reset: resetTestingTaskBoard,
    restoreFromHistory: restoreTestingFromHistory,
    setViewingPhase: setTestingViewingPhase,
    setCurrentPhase: setTestingCurrentPhase,
    totalProgress: testingTotalProgress,
    currentPhaseInfo: testingCurrentPhaseInfo,
    viewingPhaseInfo: testingViewingPhaseInfo,
  } = useTestingTaskBoard()
  
  // 判断当前对话是否已有内容
  const hasConversationContent = useMemo(() => {
    if (currentAgentType === 'intelligent_testing') {
      return !!testingSessionId && !!testingSessionStatus
    }
    return !!threadId && messages.length > 0
  }, [currentAgentType, testingSessionId, testingSessionStatus, threadId, messages.length])
  
  // 实时状态
  const [currentTool, setCurrentTool] = useState<string | null>(null)
  const fullContentRef = useRef('') 
  const currentToolCallsRef = useRef<ToolCallInfo[]>([])
  const toolCallIdRef = useRef(0)
  const currentToolIdRef = useRef(0)
  const toolSummariesRef = useRef<Map<string, ToolSummaryInfo>>(new Map())
  const [toolSummariesVersion, setToolSummariesVersion] = useState(0)
  const toolSummaries = toolSummariesRef.current
  
  const activeToolsRef = useRef<Map<number, ActiveToolInfo>>(new Map())
  const [activeToolsVersion, setActiveToolsVersion] = useState(0)
  const activeTools = activeToolsRef.current
  
  // 工具内部进度步骤（key 为 toolId）
  const toolProgressRef = useRef<Map<number, ToolProgressStep[]>>(new Map())
  const [toolProgressVersion, setToolProgressVersion] = useState(0)
  const toolProgress = toolProgressRef.current
  
  const updateMessageRafRef = useRef<number | null>(null)
  const pendingContentRef = useRef<string>('')
  
  const chatClientRef = useRef<ChatClient | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messageListRef = useRef<HTMLDivElement>(null)
  const phaseMessagesRef = useRef<Map<PhaseId, DisplayMessage[]>>(new Map())
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

  // ========== 工具函数 ==========
  
  const scrollToBottom = useCallback((force = false) => {
    if (!force && userScrolledUpRef.current) return
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  const isNearBottom = useCallback(() => {
    const container = messageListRef.current
    if (!container) return true
    const threshold = 50
    return container.scrollHeight - container.scrollTop - container.clientHeight < threshold
  }, [])

  const handleScroll = useCallback(() => {
    const container = messageListRef.current
    if (!container) return
    
    const currentScrollTop = container.scrollTop
    const scrollingUp = currentScrollTop < lastScrollTopRef.current
    lastScrollTopRef.current = currentScrollTop
    
    // 显示/隐藏回到底部按钮（距离底部超过300px时显示）
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight
    setShowScrollToBottom(distanceFromBottom > 300)
    
    if (isLoading) {
      if (scrollingUp && !isNearBottom()) {
        userScrolledUpRef.current = true
      } else if (isNearBottom()) {
        userScrolledUpRef.current = false
      }
    }
  }, [isNearBottom, isLoading])

  // 打字机 Hook
  const { text: streamingContent, append: appendToTypewriter, finish: finishTypewriter, reset: resetTypewriter, isTyping, bufferLength } = useTypewriter({
    onTick: scrollToBottom,
  })
  
  const bufferLengthRef = useRef(0)
  useEffect(() => {
    bufferLengthRef.current = bufferLength
  }, [bufferLength])

  // ========== Effects ==========

  // 加载会话列表
  useEffect(() => {
    const loadConversations = async () => {
      setIsConversationsLoading(true)
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
      } finally {
        setIsConversationsLoading(false)
      }
    }
    loadConversations()
  }, [])
  
  // 加载 Agent 类型
  useEffect(() => {
    const loadAgentTypes = async () => {
      try {
        const types = await fetchAgentTypes()
        setAgentTypes(types)
        if (types.length > 0 && !types.find(t => t.agent_type === currentAgentType)) {
          setCurrentAgentType(types[0].agent_type)
        }
      } catch (e) {
        console.error('加载 Agent 类型失败', e)
      }
    }
    loadAgentTypes()
  }, [])
  
  // 加载日志查询配置
  useEffect(() => {
    if (currentAgentType !== 'log_troubleshoot') return
    if (businessLines.length > 0) return
    
    const loadLogQueryOptions = async () => {
      try {
        const options = await fetchLogQueryOptions()
        if (options?.businessLines) {
          setBusinessLines(options.businessLines)
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
  
  // 加载迭代列表
  useEffect(() => {
    if (currentAgentType !== 'intelligent_testing') return
    if (iterations.length > 0) return
    
    const loadIterations = async () => {
      setIsIterationLoading(true)
      try {
        const result = await fetchIterations(TESTING_PROJECT_NAME, 100, 0, '')
        if (result?.iterations) {
          setIterations(result.iterations)
        }
      } catch (e) {
        console.error('加载迭代列表失败', e)
      } finally {
        setIsIterationLoading(false)
      }
    }
    loadIterations()
  }, [currentAgentType])
  
  // 加载需求列表
  useEffect(() => {
    if (!selectedIteration) return
    
    const loadIssues = async () => {
      setIsIssueLoading(true)
      try {
        const result = await fetchIssues(TESTING_PROJECT_NAME, selectedIteration.code, 'REQUIREMENT', 100, 0, '')
        if (result?.issues) {
          setIssues(result.issues)
        }
      } catch (e) {
        console.error('加载需求列表失败', e)
      } finally {
        setIsIssueLoading(false)
      }
    }
    loadIssues()
  }, [selectedIteration])
  
  // 搜索迭代
  const handleSearchIterations = useCallback(async () => {
    setIsIterationLoading(true)
    try {
      const result = await fetchIterations(TESTING_PROJECT_NAME, 100, 0, iterationSearchText)
      if (result?.iterations) {
        setIterations(result.iterations)
      }
    } catch (e) {
      console.error('搜索迭代失败', e)
    } finally {
      setIsIterationLoading(false)
    }
  }, [iterationSearchText])
  
  // 搜索需求
  const handleSearchIssues = useCallback(async () => {
    if (!selectedIteration) return
    setIsIssueLoading(true)
    try {
      const result = await fetchIssues(TESTING_PROJECT_NAME, selectedIteration.code, 'REQUIREMENT', 100, 0, issueSearchText)
      if (result?.issues) {
        setIssues(result.issues)
      }
    } catch (e) {
      console.error('搜索需求失败', e)
    } finally {
      setIsIssueLoading(false)
    }
  }, [selectedIteration, issueSearchText])
  
  // 刷新测试任务状态
  const refreshTestingSessionStatus = useCallback(async () => {
    if (!testingSessionId) return
    try {
      const status = await fetchTestingSessionStatus(testingSessionId)
      setTestingSessionStatus(status)
    } catch (e) {
      console.error('刷新测试任务状态失败', e)
    }
  }, [testingSessionId])
  
  useEffect(() => {
    if (testingSessionId) {
      refreshTestingSessionStatus()
    }
  }, [testingSessionId, refreshTestingSessionStatus])
  
  // 重置测试阶段状态
  const resetTestingPhaseState = useCallback(() => {
    setTestingSessionId(null)
    setTestingActivePhase('analysis')
    setTestingSessionStatus(null)
    setTestingPhaseMessages({ analysis: [], plan: [], generate: [] })
  }, [])
  
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
      if (!target.closest('.testing-dropdown-wrapper')) {
        setIsIterationOpen(false)
        setIsIssueOpen(false)
      }
      if (!target.closest('.file-tools-wrapper')) {
        setIsFileToolsOpen(false)
      }
    }
    if (isAgentDropdownOpen || isBusinessLineOpen || isPrivateServerOpen || isIterationOpen || isIssueOpen || isFileToolsOpen) {
      document.addEventListener('click', handleClickOutside)
      return () => document.removeEventListener('click', handleClickOutside)
    }
  }, [isAgentDropdownOpen, isBusinessLineOpen, isPrivateServerOpen, isIterationOpen, isIssueOpen, isFileToolsOpen])

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

  // 监听流式内容变化
  useEffect(() => {
    if (messages.length === 0 || (!isLoading && !isTyping)) return
    
    pendingContentRef.current = streamingContent
    
    if (updateMessageRafRef.current !== null) return
    
    updateMessageRafRef.current = requestAnimationFrame(() => {
      updateMessageRafRef.current = null
      const content = pendingContentRef.current
      
      setMessages(prev => {
        const newPrev = [...prev]
        let updated = false
        
        for (let i = newPrev.length - 1; i >= 0; i--) {
          if (newPrev[i].role === 'assistant' && newPrev[i].isThinking) {
            newPrev[i] = { ...newPrev[i], content: content }
            updated = true
            break
          }
        }
        
        if (!updated && isLoading) {
          const lastIdx = newPrev.length - 1
          if (lastIdx >= 0 && newPrev[lastIdx].role === 'assistant') {
            newPrev[lastIdx] = { ...newPrev[lastIdx], content: content }
          }
        }
        
        return newPrev
      })
    })
    
    return () => {
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

  // ========== 核心回调函数 ==========

  // 发送消息
  const sendMessage = useCallback(async (content?: string) => {
    const question = (content || inputValue).trim()
    
    if (!question && uploadedFiles.length === 0) return
    if (isLoading) return

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
    
    const assistantMessageId = `assistant-${Date.now()}`
    const assistantMessage: DisplayMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      toolCalls: [],
      isThinking: true,
    }

    setMessages(prev => [...prev, userMessage, assistantMessage])
    setInputValue('')
    clearFiles()
    setIsLoading(true)
    resetTypewriter()
    fullContentRef.current = ''
    currentToolCallsRef.current = []
    toolCallIdRef.current = 0
    toolSummariesRef.current.clear()
    activeToolsRef.current.clear()
    toolProgressRef.current.clear()
    setToolSummariesVersion(v => v + 1)
    setActiveToolsVersion(v => v + 1)
    setToolProgressVersion(v => v + 1)
    setCurrentTool(null)
    userScrolledUpRef.current = false
    
    setTimeout(() => scrollToBottom(true), 50)

    const client = createChatClient()
    chatClientRef.current = client

    const requestPayload: any = {
      question: question || '请分析这些文件',
      thread_id: threadId || undefined,
      agent_type: currentAgentType,
    }
    
    if (uploadedFiles.length > 0) {
      requestPayload.attachments = uploadedFiles.map(file => ({
        file_id: file.id,
        url: file.url,
        type: file.type,
        filename: file.filename,
        content_type: file.contentType,
      }))
    }
    
    if (currentAgentType === 'log_troubleshoot') {
      requestPayload.log_query = {
        businessLine,
        privateServer: privateServer || null,
      }
    }
    
    if (currentAgentType === 'intelligent_testing') {
      if (testingSessionId && testingSessionStatus) {
        requestPayload.testing_context = {
          project_name: testingSessionStatus.project_name || TESTING_PROJECT_NAME,
          requirement_id: testingSessionStatus.requirement_id || '',
          requirement_name: testingSessionStatus.requirement_name || '',
          phase: testingActivePhase,
          session_id: testingSessionId,
        }
      } else if (selectedIssue) {
        requestPayload.testing_context = {
          project_name: TESTING_PROJECT_NAME,
          iteration_name: selectedIteration?.name || '',
          requirement_id: String(selectedIssue.code),
          requirement_name: selectedIssue.name,
          phase: testingActivePhase,
          session_id: undefined,
        }
      } else {
        setIsLoading(false)
        setMessages(prev => prev.slice(0, -2))
        showWarning('请先在顶部配置栏中选择迭代和需求')
        return
      }
      delete requestPayload.thread_id
    }
    
    client.start(
      requestPayload,
      {
        onStart: (_rid, newThreadId) => {
          setThreadId(newThreadId)
          setActiveConversationId(newThreadId)
          
          if (currentAgentType === 'intelligent_testing' && newThreadId) {
            let sessionId = newThreadId
            while (sessionId.match(/_(analysis|plan|generate)$/)) {
              sessionId = sessionId.replace(/_(analysis|plan|generate)$/, '')
            }
            if (!testingSessionId) {
              setTestingSessionId(sessionId)
            }
            handleTestingMessage({ type: 'start', session_id: sessionId, phase: testingActivePhase })
            
            if (!testingSessionId) {
              upsertConversation(sessionId, '新对话', new Date().toISOString(), currentAgentType)
            }
          } else {
            const isNewConversation = !threadId
            if (isNewConversation && newThreadId) {
              upsertConversation(newThreadId, '新对话', new Date().toISOString(), currentAgentType)
            }
          }
        },
        
        onStream: (chunk) => {
          fullContentRef.current += chunk
          appendToTypewriter(chunk)
          
          const isRealContent = !chunk.includes('<think>') && 
                               !chunk.includes('</think>') && 
                               !chunk.includes('<!--TOOL:')
          
          if (isRealContent && chunk.trim()) {
            setMessages(prev => {
               const newPrev = [...prev]
               const lastIdx = newPrev.length - 1
               if (lastIdx >= 0 && newPrev[lastIdx].id === assistantMessageId) {
                 newPrev[lastIdx].isThinking = false
               }
               return newPrev
            })
          }
        },
        
        onToolStart: (name, toolInput, toolId, batch) => {
          if (currentAgentType === 'intelligent_testing') {
            handleTestingMessage({
              type: 'tool_start',
              tool_name: name,
              tool_id: toolId,
              tool_input: toolInput,
              batch_id: batch?.batchId,
              batch_size: batch?.batchSize,
              batch_index: batch?.batchIndex,
            })
          }
          
          if (toolId) {
            currentToolIdRef.current = toolId
          } else {
            toolCallIdRef.current += 1
            currentToolIdRef.current = toolCallIdRef.current
          }
          
          if (toolId && batch) {
            const toolInfo = {
              toolId,
              batchId: batch.batchId,
              batchSize: batch.batchSize,
              batchIndex: batch.batchIndex,
            }
            activeToolsRef.current.set(toolId, toolInfo)
            setActiveToolsVersion(v => v + 1)
          }
          
          setCurrentTool(name)
          
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
        
        onToolProgress: (toolName, toolId, phase, detail) => {
          // 存储工具内部进度步骤
          const steps = toolProgressRef.current.get(toolId) || []
          steps.push({ phase, detail, timestamp: Date.now() })
          toolProgressRef.current.set(toolId, steps)
          setToolProgressVersion(v => v + 1)
        },
        
        onToolEnd: (name, inputSummary, outputSummary, elapsed, toolId, batch) => {
          const finalToolId = toolId ?? currentToolIdRef.current
          
          if (currentAgentType === 'intelligent_testing') {
            handleTestingMessage({
              type: 'tool_end',
              tool_name: name,
              tool_id: finalToolId,
              input_summary: inputSummary,
              output_summary: outputSummary,
              elapsed: elapsed,
              batch_id: batch?.batchId,
              batch_size: batch?.batchSize,
              batch_index: batch?.batchIndex,
            })
          }
          
          setCurrentTool(null)
          currentToolCallsRef.current.push({ name, output_length: 0 })
          
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
               newPrev[lastIdx].currentToolName = undefined
             }
             return newPrev
          })
        },
        
        onPhaseChanged: (phase) => {
          if (currentAgentType === 'intelligent_testing') {
            handleTestingMessage({ type: 'phase_changed', phase })
          }
        },
        
        onPhaseCompleted: (phase) => {
          if (currentAgentType === 'intelligent_testing') {
            handleTestingMessage({ type: 'phase_completed', phase })
          }
        },
        
        onTitleGenerated: (title, tid) => {
          if (currentAgentType === 'intelligent_testing' && tid) {
            upsertConversation(tid, title, new Date().toISOString(), currentAgentType)
          }
        },
        
        onResult: (content, resultThreadId, toolCalls) => {
          finishTypewriter()
          
          if (currentAgentType === 'intelligent_testing') {
            handleTestingMessage({ type: 'result', status: 'completed' })
            refreshTestingSessionStatus()
            setTestingPhaseMessages(prev => ({
              ...prev,
              [testingActivePhase]: messages,
            }))
          }
          
          const snapshotToolSummaries = new Map(toolSummariesRef.current)
          
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
          
          const ensureComplete = () => {
            const bufferLen = bufferLengthRef.current
            if (bufferLen > 0) {
              setTimeout(ensureComplete, 200)
              return
            }
            
            setMessages(prev => {
              const newPrev = [...prev]
              const lastIdx = newPrev.findIndex(m => m.id === assistantMessageId)
              if (lastIdx !== -1) {
                const finalContent = fullContentRef.current || content
                if (newPrev[lastIdx].content !== finalContent) {
                  newPrev[lastIdx] = { ...newPrev[lastIdx], content: finalContent }
                }
              }
              return newPrev
            })
          }
          setTimeout(ensureComplete, 500)
          
          if (currentAgentType !== 'intelligent_testing') {
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
          }
        },
        
        onError: (err) => {
          console.error(err)
          finishTypewriter()
          
          if (currentAgentType === 'intelligent_testing') {
            handleTestingMessage({ type: 'error', error: String(err) })
          }
          
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
  }, [inputValue, isLoading, threadId, currentAgentType, businessLine, privateServer, selectedIssue, upsertConversation, appendToTypewriter, finishTypewriter, resetTypewriter, scrollToBottom, handleTestingMessage, testingSessionId, testingSessionStatus, testingActivePhase, selectedIteration, uploadedFiles, clearFiles, refreshTestingSessionStatus, messages])

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
    resetTestingTaskBoard()
    resetTestingPhaseState()
    phaseMessagesRef.current.clear()
    toolSummariesRef.current.clear()
    toolProgressRef.current.clear()
  }

  // 重新生成
  const handleRegenerate = useCallback((userMsgIndex: number) => {
    if (isLoading || !threadId) return
    
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
    
    setMessages(prev => prev.map((msg, idx) => 
      idx === targetAssistantIdx 
        ? { ...msg, content: '', isThinking: true, toolCalls: [], currentToolName: undefined }
        : msg
    ))
    setIsLoading(true)
    resetTypewriter()
    fullContentRef.current = ''
    currentToolCallsRef.current = []
    toolCallIdRef.current = 0
    toolSummariesRef.current.clear()
    activeToolsRef.current.clear()
    toolProgressRef.current.clear()
    setToolSummariesVersion(v => v + 1)
    setActiveToolsVersion(v => v + 1)
    setToolProgressVersion(v => v + 1)
    
    const client = createRegenerateClient()
    
    client.start(
      { thread_id: threadId, user_msg_index: userMsgIndex, agent_type: currentAgentType },
      {
        onStream: (chunk) => {
          fullContentRef.current += chunk
          appendToTypewriter(chunk)
          
          const isRealContent = !chunk.includes('<think>') && 
                               !chunk.includes('</think>') && 
                               !chunk.includes('<!--TOOL:')
          
          if (isRealContent && chunk.trim()) {
            setMessages(prev => prev.map((msg, idx) => 
              idx === targetAssistantIdx 
                ? { ...msg, isThinking: false }
                : msg
            ))
          }
        },
        onToolStart: (name, _input, toolId) => {
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
          
          const toolKey = `${name}:${toolId}`
          toolSummariesRef.current.set(toolKey, { input: inputSummary, output: outputSummary })
          setToolSummariesVersion(v => v + 1)
          
          setMessages(prev => prev.map((msg, idx) => 
            idx === targetAssistantIdx 
              ? { ...msg, toolCalls: [...currentToolCallsRef.current], isThinking: true, currentToolName: undefined }
              : msg
          ))
        },
        onResult: (content, _threadId, toolCalls) => {
          finishTypewriter()
          
          const snapshotToolSummaries = new Map(toolSummariesRef.current)
          
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
  }, [messages, isLoading, threadId, appendToTypewriter, finishTypewriter, resetTypewriter, currentAgentType])

  // 回溯
  const handleRollback = useCallback(async (messageId: string) => {
    if (isLoading) return
    
    const idx = messages.findIndex(m => m.id === messageId)
    if (idx === -1 || messages[idx].role !== 'user') return
    
    const userMessage = messages[idx]
    const userContent = userMessage.content
    const userAttachments = userMessage.attachments
    
    let keepPairs = 0
    for (let i = 0; i < idx; i++) {
      if (messages[i].role === 'user') {
        keepPairs++
      }
    }
    
    if (threadId) {
      try {
        await truncateConversation(threadId, keepPairs)
      } catch (e) {
        console.error('截断对话历史失败', e)
      }
    }
    
    setMessages(prev => prev.slice(0, idx))
    setInputValue(userContent)
    if (userAttachments && userAttachments.length > 0) {
      const restoredFiles = userAttachments.map(att => ({
        id: att.file_id || `restored-${Date.now()}-${Math.random().toString(36).slice(2)}`,
        url: att.url,
        filename: att.filename,
        size: 0,
        type: att.type as 'image' | 'document' | 'audio' | 'video' | 'unknown',
        contentType: att.content_type,
      }))
      setFiles(restoredFiles)
    } else {
      clearFiles()
    }
    setTimeout(() => inputRef.current?.focus(), 50)
  }, [messages, isLoading, threadId, setFiles, clearFiles])

  // 选择会话
  const handleSelectConversation = useCallback(async (conv: ConversationSummary) => {
    if (!conv.threadId) return
    setActiveConversationId(conv.threadId)
    setThreadId(conv.threadId)
    if (conv.agentType) {
      setCurrentAgentType(conv.agentType)
    }
    setIsHistoryLoading(true)
    setMessages([])
    resetTypewriter()

    try {
      if (conv.agentType === 'intelligent_testing') {
        let sessionId = conv.threadId
        while (sessionId.match(/_(analysis|plan|generate)$/)) {
          sessionId = sessionId.replace(/_(analysis|plan|generate)$/, '')
        }
        setTestingSessionId(sessionId)
        
        try {
          const status = await fetchTestingSessionStatus(sessionId)
          setTestingSessionStatus(status)
          
          let initialPhase: PhaseId = 'analysis'
          if (status.phases.generate.has_summary) {
            initialPhase = 'generate'
          } else if (status.phases.plan.has_summary) {
            initialPhase = 'plan'
          } else if (status.phases.analysis.has_summary) {
            initialPhase = 'plan'
          }
          setTestingActivePhase(initialPhase)
          setTestingViewingPhase(initialPhase)
          
          const phases: PhaseId[] = ['analysis', 'plan', 'generate']
          toolSummariesRef.current.clear()
          toolProgressRef.current.clear()
          phaseMessagesRef.current.clear()
          
          for (const phase of phases) {
            try {
              const phaseThreadId = `${sessionId}_${phase}`
              const rawMessages = await fetchConversationHistory(phaseThreadId)
              if (rawMessages.length > 0) {
                const result = convertRawMessagesToDisplay(rawMessages, phaseThreadId)
                phaseMessagesRef.current.set(phase, result.messages)
                result.toolSummaries.forEach((value, key) => {
                  toolSummariesRef.current.set(key, value)
                })
              }
            } catch (e) {
              console.log(`阶段 ${phase} 加载失败:`, e)
            }
          }
          
          setToolSummariesVersion(v => v + 1)
          
          const initialMessages = phaseMessagesRef.current.get(initialPhase) || []
          setMessages(initialMessages)
          
          const testingResult = await fetchTestingHistory(sessionId)
          restoreTestingFromHistory(
            {
              analysis: { completed: status.phases.analysis.has_summary },
              plan: { completed: status.phases.plan.has_summary },
              generate: { completed: status.phases.generate.has_summary },
            },
            status.current_phase,
            status.status,
            testingResult.task_history
          )
        } catch (e) {
          console.error('加载测试任务状态失败', e)
          const testingResult = await fetchTestingHistory(sessionId)
          if (testingResult.phases) {
            restoreTestingFromHistory(
              testingResult.phases, 
              testingResult.current_phase, 
              testingResult.status,
              testingResult.task_history
            )
          }
          const result = convertRawMessagesToDisplay(testingResult.messages, sessionId)
          toolSummariesRef.current.clear()
          toolProgressRef.current.clear()
          result.toolSummaries.forEach((value, key) => {
            toolSummariesRef.current.set(key, value)
          })
          setToolSummariesVersion(v => v + 1)
          setMessages(result.messages)
        }
      } else {
        const rawMessages = await fetchConversationHistory(conv.threadId)
        const result = convertRawMessagesToDisplay(rawMessages, conv.threadId)
        
        toolSummariesRef.current.clear()
        toolProgressRef.current.clear()
        result.toolSummaries.forEach((value, key) => {
          toolSummariesRef.current.set(key, value)
        })
        setToolSummariesVersion(v => v + 1)
        setMessages(result.messages)
      }
      
      setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'instant' })
      }, 50)
    } catch (e) {
      console.error('加载会话历史失败', e)
    } finally {
      setIsHistoryLoading(false)
    }
  }, [resetTypewriter, restoreTestingFromHistory])

  // 删除会话
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

  // ========== 渲染 ==========

  return (
    <div className="chat-page-container">
      {/* 侧边栏 */}
      <ConversationSidebar
        isSidebarCollapsed={isSidebarCollapsed}
        setIsSidebarCollapsed={setIsSidebarCollapsed}
        isConversationsLoading={isConversationsLoading}
        conversations={conversations}
        groupedConversations={groupedConversations}
        activeConversationId={activeConversationId}
        isHistoryLoading={isHistoryLoading}
        onNewChat={() => {
          setActiveTab('chat')
          handleClear()
        }}
        onSelectConversation={handleSelectConversation}
        onDeleteConversation={handleDeleteConversation}
      />

      {/* 智能测试任务面板 */}
      {currentAgentType === 'intelligent_testing' && (
        <TestingTaskPanel
          testingSessionId={testingSessionId}
          testingActivePhase={testingActivePhase}
          setTestingActivePhase={setTestingActivePhase}
          testingPhases={testingPhases}
          testingCurrentPhase={testingCurrentPhase}
          testingViewingPhase={testingViewingPhase}
          setTestingViewingPhase={setTestingViewingPhase}
          testingTasks={testingTasks}
          isTestingRunning={isTestingRunning}
          testingViewingPhaseInfo={testingViewingPhaseInfo}
          isLoading={isLoading}
          messages={messages}
          setMessages={setMessages}
          setCurrentTool={setCurrentTool}
          phaseMessagesRef={phaseMessagesRef}
        />
      )}

      {/* 主聊天区域 */}
      <div className={`chat-main ${messages.length === 0 ? 'empty-chat' : ''} ${currentAgentType === 'intelligent_testing' ? 'with-task-panel' : ''}`}>
        {/* Agent 选择器头部 */}
        {agentTypes.length > 0 && (
          <AgentSelectorHeader
            agentTypes={agentTypes}
            currentAgentType={currentAgentType}
            setCurrentAgentType={setCurrentAgentType}
            isAgentDropdownOpen={isAgentDropdownOpen}
            setIsAgentDropdownOpen={setIsAgentDropdownOpen}
            hasConversationContent={hasConversationContent}
            businessLines={businessLines}
            privateServers={privateServers}
            businessLine={businessLine}
            setBusinessLine={setBusinessLine}
            privateServer={privateServer}
            setPrivateServer={setPrivateServer}
            isBusinessLineOpen={isBusinessLineOpen}
            setIsBusinessLineOpen={setIsBusinessLineOpen}
            isPrivateServerOpen={isPrivateServerOpen}
            setIsPrivateServerOpen={setIsPrivateServerOpen}
            iterations={iterations}
            issues={issues}
            selectedIteration={selectedIteration}
            setSelectedIteration={setSelectedIteration}
            selectedIssue={selectedIssue}
            setSelectedIssue={setSelectedIssue}
            iterationSearchText={iterationSearchText}
            setIterationSearchText={setIterationSearchText}
            issueSearchText={issueSearchText}
            setIssueSearchText={setIssueSearchText}
            isIterationLoading={isIterationLoading}
            isIssueLoading={isIssueLoading}
            isIterationOpen={isIterationOpen}
            setIsIterationOpen={setIsIterationOpen}
            isIssueOpen={isIssueOpen}
            setIsIssueOpen={setIsIssueOpen}
            onSearchIterations={handleSearchIterations}
            onSearchIssues={handleSearchIssues}
            testingSessionId={testingSessionId}
            testingSessionStatus={testingSessionStatus}
          />
        )}
        
        {/* 消息列表 */}
        <div className="chat-message-list" ref={messageListRef} onScroll={handleScroll}>
          <div className="chat-content-width">
            {isHistoryLoading ? (
              <div className="history-loading-container">
                <LoadingOutlined spin style={{ fontSize: 32, color: '#1890ff' }} />
                <span className="history-loading-text">正在加载对话...</span>
              </div>
            ) : messages.length === 0 ? (
              <WelcomeScreen 
                key={`${currentAgentType}-${businessLine || ''}-${privateServer || ''}-${testingActivePhase}`}
                onSuggestionClick={(q) => sendMessage(q)} 
                agentType={currentAgentType}
                businessLine={businessLine}
                privateServer={privateServer}
              />
            ) : (
              <>
                {messages.map((msg, idx) => {
                  // 阶段分隔符
                  if (msg.role === 'phase_divider') {
                    return (
                      <div key={msg.id} className="phase-divider">
                        <div className="phase-divider-line" />
                        <div className="phase-divider-badge">
                          <span className="phase-divider-icon">🚀</span>
                          <span className="phase-divider-text">
                            阶段 {msg.phaseIndex}: {msg.phaseName}
                          </span>
                        </div>
                        <div className="phase-divider-line" />
                      </div>
                    )
                  }
                  
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
                      toolProgress={toolProgress}
                    />
                  )
                })}
                
                {/* 测试助手：阶段完成后显示进入下一阶段按钮 */}
                {currentAgentType === 'intelligent_testing' && 
                 testingSessionId && 
                 testingActivePhase !== 'generate' && 
                 testingSessionStatus?.phases?.[testingActivePhase]?.has_summary && 
                 !isLoading && (
                  <div className="next-phase-message">
                    <div className="next-phase-content">
                      <CheckCircleOutlined className="next-phase-icon" />
                      <span className="next-phase-text">
                        {testingActivePhase === 'analysis' ? '需求分析' : '测试方案'}阶段已完成
                      </span>
                      <button
                        className="next-phase-btn"
                        onClick={() => {
                          const nextPhase = testingActivePhase === 'analysis' ? 'plan' : 'generate'
                          phaseMessagesRef.current.set(testingActivePhase, [...messages])
                          refreshTestingSessionStatus()
                          setTestingActivePhase(nextPhase as PhaseId)
                          setTestingViewingPhase(nextPhase as PhaseId)
                          setTestingCurrentPhase(nextPhase as PhaseId)
                          setMessages([])
                          setCurrentTool(null)
                        }}
                      >
                        进入下一阶段: {testingActivePhase === 'analysis' ? '测试方案' : '用例生成'} →
                      </button>
                    </div>
                  </div>
                )}
                
                <div ref={messagesEndRef} style={{ height: 1 }} />
              </>
            )}
          </div>
        </div>

        {/* 回到底部按钮 - 浮于输入框上方 */}
        {showScrollToBottom && (
          <button
            className="scroll-to-bottom-btn"
            onClick={() => scrollToBottom(true)}
            title="回到底部"
          >
            <ArrowDownOutlined />
          </button>
        )}

        {/* 输入区域 */}
        <ChatInputArea
          inputRef={inputRef}
          inputValue={inputValue}
          setInputValue={setInputValue}
          isLoading={isLoading}
          uploadedFiles={uploadedFiles}
          pendingFiles={pendingFiles}
          uploading={uploading}
          handleUpload={handleUpload}
          removeFile={removeFile}
          removePendingFile={removePendingFile}
          isFileToolsOpen={isFileToolsOpen}
          setIsFileToolsOpen={setIsFileToolsOpen}
          onSendMessage={sendMessage}
          onStop={handleStop}
          currentAgentType={currentAgentType}
          messagesLength={messages.length}
          testingActivePhase={testingActivePhase}
        />
      </div>
    </div>
  )
}

export default ChatPage

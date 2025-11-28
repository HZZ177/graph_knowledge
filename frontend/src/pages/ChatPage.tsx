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
} from '@ant-design/icons'
import { createChatClient, ChatClient, ToolCallInfo, fetchConversationHistory, generateConversationTitle, listConversations, deleteConversation, ChatMessage } from '../api/llm'
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

// 2. 工具调用过程展示
interface ToolProcessProps {
  toolCalls: ToolCallInfo[]
  isThinking: boolean
  currentToolName?: string
}

const ToolProcess: React.FC<ToolProcessProps> = ({ toolCalls, isThinking, currentToolName }) => {
  const [isExpanded, setIsExpanded] = useState(false)
  
  // 如果正在思考或有工具调用，显示
  if (!isThinking && (!toolCalls || toolCalls.length === 0)) return null

  // 格式化工具名称显示
  const formatToolNames = (tools: ToolCallInfo[]) => {
    if (tools.length === 0) return ''
    if (tools.length === 1) return tools[0].name
    if (tools.length <= 3) return tools.map(t => t.name).join('、')
    return tools.slice(0, 3).map(t => t.name).join('、') + ' 等工具'
  }

  // 获取摘要文本
  const getSummaryText = () => {
    if (isThinking && currentToolName) {
      return `正在调用 ${currentToolName} 工具`
    }
    if (isThinking) {
      return '正在思考...'
    }
    return `已调用 ${formatToolNames(toolCalls)}`
  }

  return (
    <div className={`tool-process-container ${isExpanded ? 'expanded' : ''}`}>
      <div 
        className={`tool-process-summary ${isExpanded ? 'active' : ''}`}
        onClick={() => toolCalls.length > 0 && setIsExpanded(!isExpanded)}
      >
        {isThinking ? (
          <span className="tool-icon"><SyncOutlined spin /></span>
        ) : (
          <span className="tool-icon"><CheckCircleOutlined style={{ color: '#10b981' }} /></span>
        )}
        <span className="tool-summary-text">{getSummaryText()}</span>
        {toolCalls.length > 0 && (
          <span className="tool-chevron">
            {isExpanded ? <DownOutlined /> : <RightOutlined />}
          </span>
        )}
      </div>
      
      {isExpanded && toolCalls.length > 0 && (
        <div className="tool-process-details">
          {toolCalls.map((tool, idx) => (
            <div key={idx} className="tool-item">
              <span className="tool-item-status"><ToolOutlined /></span>
              <span className="tool-item-text">
                <b>{tool.name}</b>
                {tool.output_length > 0 && <span className="tool-output-size">({tool.output_length} chars)</span>}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// 3. 消息气泡
const MessageItem: React.FC<{ message: DisplayMessage }> = ({ message }) => {
  const isUser = message.role === 'user'
  
  return (
    <div className={`message-item ${message.role}`}>
      {!isUser && (
        <div className="message-header">
          <div className="avatar assistant">
            <RobotOutlined />
          </div>
          <span className="role-name">Graph AI</span>
        </div>
      )}
      
      <div className="message-bubble">
        {/* 工具调用展示 (仅对 Assistant) */}
        {!isUser && (
          <ToolProcess 
            toolCalls={message.toolCalls || []} 
            isThinking={!!message.isThinking}
            currentToolName={message.currentToolName}
          />
        )}
        
        <div className="markdown-body">
           {isUser ? (
             message.content
           ) : (
             <>
               {message.content ? (
                 <MarkdownPreview 
                   source={message.content} 
                   style={{ background: 'transparent', fontSize: 16 }}
                   wrapperElement={{ "data-color-mode": "light" }}
                 />
               ) : (
                 !message.toolCalls?.length && !message.isThinking && <span className="thinking-dots">
                   <span className="thinking-dot"></span>
                   <span className="thinking-dot"></span>
                   <span className="thinking-dot"></span>
                 </span>
               )}
               {/* 光标效果已经在 useTypewriter 中处理，或者可以通过 CSS 添加在末尾 */}
             </>
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
    setCurrentTool(null)
    userScrolledUpRef.current = false // 发送新消息时重置滚动状态

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
        
        onToolStart: (name, _input) => {
          console.log('Tool Start:', name)
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
        
        onToolEnd: (name) => {
          console.log('Tool End:', name)
          setCurrentTool(null)
          // 记录工具调用
          currentToolCallsRef.current.push({ name, output_length: 0 })
          
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
          setMessages(prev => [
            ...prev,
            {
              id: `error-${Date.now()}`,
              role: 'assistant',
              content: `⚠️ 发生错误: ${err}`,
            }
          ])
          setIsLoading(false)
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

  const handleSelectConversation = useCallback(async (conv: ConversationSummary) => {
    if (!conv.threadId) return
    setActiveConversationId(conv.threadId)
    setThreadId(conv.threadId)
    setIsLoading(true)
    
    try {
      const msgs = await fetchConversationHistory(conv.threadId)
      
      const display: DisplayMessage[] = []
      let pendingToolCalls: ToolCallInfo[] = []
      
      msgs.forEach((m, i) => {
        if (m.role === 'user') {
          display.push({
            id: `user-${i}-${conv.threadId}`,
            role: 'user',
            content: m.content,
          })
        } else if (m.role === 'assistant') {
          if (m.tool_calls && m.tool_calls.length > 0) {
            // assistant 发起工具调用
            pendingToolCalls = m.tool_calls.map(tc => ({ name: tc.name, output_length: 0 }))
          } else if (m.content) {
            // assistant 内容
            display.push({
              id: `assistant-${i}-${conv.threadId}`,
              role: 'assistant',
              content: m.content,
              toolCalls: pendingToolCalls.length > 0 ? [...pendingToolCalls] : undefined,
            })
            pendingToolCalls = []
          }
        } else if (m.role === 'tool') {
          // tool 返回
          const toolIdx = pendingToolCalls.findIndex(tc => tc.name === m.tool_name)
          if (toolIdx !== -1) {
            pendingToolCalls[toolIdx].output_length = m.content.length
          }
        }
      })
      
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
            title="聊天"
          >
            <EditOutlined className="menu-icon" />
            {!isSidebarCollapsed && <span className="menu-text">聊天</span>}
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
                {messages.map(msg => (
                  <MessageItem key={msg.id} message={msg} />
                ))}
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
                <button className="stop-btn" onClick={handleStop}>
                  <StopOutlined style={{ fontSize: 16 }} />
                </button>
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

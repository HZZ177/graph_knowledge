/**
 * AI骨架生成弹窗组件
 * 
 * 功能：
 * 1. 输入业务描述、日志、抓包数据
 * 2. 时间轴展示Agent执行进度和流式输出
 * 3. 预览生成的画布结构
 * 4. 确认后创建流程
 */

import React, { useState, useCallback, useRef, useEffect } from 'react'
import {
  Modal,
  Form,
  Input,
  Button,
  Space,
  Alert,
  Typography,
  Select,
  Switch,
} from 'antd'
import ReactMarkdown from 'react-markdown'
import {
  RobotOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  ClockCircleOutlined,
  SendOutlined,
  ReloadOutlined,
  CheckOutlined,
  UpOutlined,
  DownOutlined,
} from '@ant-design/icons'
import { ReactFlow, Background, Controls, Handle, Position, MarkerType, type Node, type Edge } from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import {
  createSkeletonWebSocket,
  confirmSkeleton,
  type SkeletonGenerateRequest,
  type AgentStreamChunk,
  type CanvasData,
} from '../api/skeleton'
import { showError, showSuccess } from '../utils/message'
import { useMultiTypewriter } from '../hooks/useTypewriter'

const { TextArea } = Input
const { Text, Paragraph } = Typography

// ==================== 类型定义 ====================

type ModalStep = 'input' | 'generating' | 'preview'

interface AgentState {
  name: string
  description: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  content: string  // 流式累积内容（兼容旧逻辑）
  output: string   // 最终输出
  thought: string  // 思考过程（最终）
  finalAnswer: string  // 最终结果（最终）
  thoughtContent: string  // 思考过程流式内容
  answerContent: string   // 最终结果流式内容
  currentSection: 'unknown' | 'thought' | 'answer'  // 当前正在输出的区域
  durationMs?: number
  startTime?: number
}

interface SkeletonGenerateModalProps {
  open: boolean
  onClose: () => void
  onConfirm: (canvasData: CanvasData) => void
}

// ==================== 主组件 ====================

const SkeletonGenerateModal: React.FC<SkeletonGenerateModalProps> = ({
  open,
  onClose,
  onConfirm,
}) => {
  const [step, setStep] = useState<ModalStep>('input')
  const [form] = Form.useForm()
  const [error, setError] = useState<string | null>(null)
  const [canvasData, setCanvasData] = useState<CanvasData | null>(null)
  const [confirmLoading, setConfirmLoading] = useState(false)
  
  // Agent状态
  const defaultAgents: AgentState[] = [
    { name: '数据分析师', description: '分析原始技术数据', status: 'pending', content: '', output: '', thought: '', finalAnswer: '', thoughtContent: '', answerContent: '', currentSection: 'unknown' },
    { name: '流程设计师', description: '设计业务流程步骤', status: 'pending', content: '', output: '', thought: '', finalAnswer: '', thoughtContent: '', answerContent: '', currentSection: 'unknown' },
    { name: '技术架构师', description: '补充技术实现细节', status: 'pending', content: '', output: '', thought: '', finalAnswer: '', thoughtContent: '', answerContent: '', currentSection: 'unknown' },
  ]
  const [agents, setAgents] = useState<AgentState[]>(defaultAgents)
  
  const wsRef = useRef<WebSocket | null>(null)
  const scrollContainerRef = useRef<HTMLDivElement | null>(null)
  const contentRefs = useRef<(HTMLDivElement | null)[]>([])
  const autoScrollRef = useRef(true)
  const userScrollingRef = useRef(false)
  const lastScrollTopRef = useRef(0)
  
  // 滚动回调（供打字机使用）
  const handleTypewriterTick = useCallback(() => {
    if (autoScrollRef.current) {
      const container = scrollContainerRef.current
      if (container) {
        requestAnimationFrame(() => {
          container.scrollTop = container.scrollHeight
        })
      }
    }
  }, [])
  
  // 使用两个独立的多通道打字机：分别处理思考和结果内容
  const thoughtTypewriter = useMultiTypewriter(3, { onTick: handleTypewriterTick })
  const answerTypewriter = useMultiTypewriter(3, { onTick: handleTypewriterTick })
  
  // 将打字机的 texts 同步到 agents（用于渲染）
  const agentsWithContent = agents.map((agent, idx) => ({
    ...agent,
    thoughtContent: agent.status === 'completed' ? agent.thoughtContent : (thoughtTypewriter.texts[idx] || ''),
    answerContent: agent.status === 'completed' ? agent.answerContent : (answerTypewriter.texts[idx] || ''),
  }))
  
  // 重置状态（只依赖稳定的 reset 函数引用，避免无限循环）
  const resetState = useCallback(() => {
    thoughtTypewriter.reset()
    answerTypewriter.reset()
    setStep('input')
    setError(null)
    setCanvasData(null)
    setAgents(defaultAgents.map(a => ({ ...a })))
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [thoughtTypewriter.reset, answerTypewriter.reset])
  
  // 打开弹窗时重置状态（避免在关闭时操作已销毁的 Form）
  useEffect(() => {
    if (open) {
      resetState()
      form.resetFields()
      autoScrollRef.current = true
      userScrollingRef.current = false
    }
  }, [open, resetState, form])
  
  // 智能自动滚动：检测用户是否在手动滚动
  const handleContainerScroll = useCallback(() => {
    const container = scrollContainerRef.current
    if (!container) return
    
    const threshold = 50 // 距离底部阈值
    const currentScrollTop = container.scrollTop
    const isAtBottom = container.scrollHeight - currentScrollTop - container.clientHeight <= threshold
    
    // 检测用户是否向上滚动（手动查看历史）
    if (currentScrollTop < lastScrollTopRef.current - 5) {
      // 用户向上滚动，停止自动滚动
      userScrollingRef.current = true
      autoScrollRef.current = false
    }
    
    // 如果用户滚动到底部，恢复自动滚动
    if (isAtBottom) {
      userScrollingRef.current = false
      autoScrollRef.current = true
    }
    
    lastScrollTopRef.current = currentScrollTop
  }, [])
  
  // 执行滚动到底部
  const scrollToBottom = useCallback(() => {
    if (!autoScrollRef.current) return
    
    const container = scrollContainerRef.current
    if (container) {
      // 使用 requestAnimationFrame 确保在 DOM 更新后执行
      requestAnimationFrame(() => {
        container.scrollTo({
          top: container.scrollHeight,
          behavior: 'auto', // 使用 auto 避免动画延迟
        })
        lastScrollTopRef.current = container.scrollHeight
      })
    }
  }, [])
  
  // 处理WebSocket消息
  const handleChunk = useCallback((chunk: AgentStreamChunk) => {
    switch (chunk.type) {
      case 'agent_start':
        setAgents(prev => prev.map((agent, idx) => 
          idx === chunk.agent_index
            ? { 
                ...agent, 
                status: 'running', 
                content: '', 
                thoughtContent: '', 
                answerContent: '', 
                currentSection: 'unknown',
                startTime: Date.now() 
              }
            : agent
        ))
        break
        
      case 'stream':
        // 根据 section 字段将内容追加到对应的打字机缓冲区
        if (chunk.content && chunk.agent_index !== undefined) {
          const section = (chunk as any).section as string
          const agentIdx = chunk.agent_index
          
          // 更新当前区域状态，并累积原始内容（用于 agent_end 时的后备）
          setAgents(prev => prev.map((agent, idx) => {
            if (idx !== agentIdx) return agent
            if (section === 'thought') {
              return { 
                ...agent, 
                currentSection: 'thought',
                thoughtContent: agent.thoughtContent + chunk.content,
              }
            } else if (section === 'answer') {
              return { 
                ...agent, 
                currentSection: 'answer',
                answerContent: agent.answerContent + chunk.content,
              }
            }
            return agent
          }))
          
          // 将内容追加到对应的打字机缓冲区（实现丝滑逐字输出）
          if (section === 'thought') {
            thoughtTypewriter.append(agentIdx, chunk.content)
          } else if (section === 'answer') {
            answerTypewriter.append(agentIdx, chunk.content)
          }
        }
        break
        
      case 'agent_end':
        // 标记打字机完成，触发加速清空缓冲区
        if (chunk.agent_index !== undefined) {
          thoughtTypewriter.finish(chunk.agent_index)
          answerTypewriter.finish(chunk.agent_index)
        }
        // 标记完成，并保存最终内容
        setAgents(prev => prev.map((agent, idx) => 
          idx === chunk.agent_index
            ? {
                ...agent,
                status: 'completed',
                output: chunk.agent_output || '',
                thought: (chunk as any).thought || '',
                finalAnswer: (chunk as any).final_answer || '',
                // 将流式累积的内容保存为最终内容（如果后端没返回最终内容）
                thoughtContent: (chunk as any).thought || agent.thoughtContent,
                answerContent: (chunk as any).final_answer || agent.answerContent,
                durationMs: chunk.duration_ms,
              }
            : agent
        ))
        break
        
      case 'result':
        if (chunk.canvas_data) {
          setCanvasData(chunk.canvas_data)
        }
        break
        
      case 'error':
        setError(chunk.error || '生成失败')
        setAgents(prev => prev.map(agent => 
          agent.status === 'running'
            ? { ...agent, status: 'failed' }
            : agent
        ))
        break
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scrollToBottom, thoughtTypewriter.append, thoughtTypewriter.finish, answerTypewriter.append, answerTypewriter.finish])
  
  // 开始生成
  const handleGenerate = useCallback(async () => {
    try {
      const values = await form.validateFields()
      setError(null)
      setStep('generating')
      
      // 重置自动滚动状态和打字机
      autoScrollRef.current = true
      userScrollingRef.current = false
      lastScrollTopRef.current = 0
      thoughtTypewriter.reset()
      answerTypewriter.reset()
      
      // 重置Agent状态
      setAgents(defaultAgents.map(a => ({ ...a })))
      
      const request: SkeletonGenerateRequest = {
        business_name: values.business_name,
        business_description: values.business_description,
        channel: values.channel || undefined,
        structured_logs: values.structured_logs || undefined,
        api_captures: values.api_captures || undefined,
      }
      
      // 创建WebSocket连接
      wsRef.current = createSkeletonWebSocket(request, {
        onChunk: handleChunk,
        onError: (err) => {
          setError(err)
        },
        onClose: () => {
          wsRef.current = null
        },
      })
      
    } catch (e: any) {
      if (e?.errorFields) return
      setError('表单验证失败')
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form, handleChunk, thoughtTypewriter.reset, answerTypewriter.reset])
  
  // 确认创建
  const handleConfirm = useCallback(async () => {
    if (!canvasData) return
    
    setConfirmLoading(true)
    try {
      const result = await confirmSkeleton(canvasData)
      showSuccess('流程骨架已创建')
      onConfirm(result)
      onClose()
    } catch (e: any) {
      showError(e?.message || '创建失败')
    } finally {
      setConfirmLoading(false)
    }
  }, [canvasData, onConfirm, onClose])
  
  // 重新生成
  const handleRegenerate = useCallback(() => {
    setStep('input')
    setCanvasData(null)
    setError(null)
  }, [])
  
  // 渲染标题
  const renderTitle = () => {
    const titles: Record<ModalStep, string> = {
      input: 'AI 生成流程骨架',
      generating: '业务骨架预测',
      preview: '预览生成结果',
    }
    return (
      <Space>
        <RobotOutlined />
        {titles[step]}
      </Space>
    )
  }
  
  // 渲染固定底部按钮
  const renderFooter = () => {
    if (step === 'input') {
      return (
        <Button type="primary" icon={<SendOutlined />} onClick={handleGenerate} block size="large">
          开始生成
        </Button>
      )
    }
    if (step === 'generating') {
      const completed = agents.filter(a => a.status === 'completed').length
      return (
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
          <Button onClick={onClose}>取消</Button>
          <Button icon={<ReloadOutlined />} onClick={handleRegenerate}>重新生成</Button>
          <Button type="primary" icon={<CheckOutlined />} disabled={!canvasData || completed < agents.length} onClick={() => setStep('preview')}>
            预览画布
          </Button>
        </div>
      )
    }
    if (step === 'preview') {
      return (
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
          <Button icon={<ReloadOutlined />} onClick={handleRegenerate}>重新生成</Button>
          <Button type="primary" icon={<CheckOutlined />} onClick={handleConfirm} loading={confirmLoading}>
            确认创建
          </Button>
        </div>
      )
    }
    return null
  }
  
  // 苹果风格滚动条样式
  const scrollbarStyles = `
    .skeleton-modal-scroll::-webkit-scrollbar {
      width: 8px;
      height: 8px;
    }
    .skeleton-modal-scroll::-webkit-scrollbar-track {
      background: transparent;
    }
    .skeleton-modal-scroll::-webkit-scrollbar-thumb {
      background: rgba(0, 0, 0, 0.15);
      border-radius: 4px;
      border: 2px solid transparent;
      background-clip: padding-box;
    }
    .skeleton-modal-scroll::-webkit-scrollbar-thumb:hover {
      background: rgba(0, 0, 0, 0.25);
      border: 2px solid transparent;
      background-clip: padding-box;
    }
    .skeleton-modal-scroll {
      scrollbar-width: thin;
      scrollbar-color: rgba(0, 0, 0, 0.15) transparent;
    }
  `
  
  return (
    <Modal
      open={open}
      onCancel={onClose}
      title={renderTitle()}
      width={step === 'preview' ? 1100 : 900}
      footer={renderFooter()}
      maskClosable={false}
      destroyOnHidden
      styles={{ body: { padding: 0 } }}
    >
      <style>{scrollbarStyles}</style>
      <div
        ref={scrollContainerRef}
        onScroll={handleContainerScroll}
        className="skeleton-modal-scroll"
        style={{
          maxHeight: 'calc(80vh - 160px)',
          overflow: 'auto',
          padding: '20px 24px',
        }}
      >
      {step === 'input' && (
        <InputStep
          form={form}
          error={error}
          onGenerate={handleGenerate}
        />
      )}
      
      {step === 'generating' && (
        <GeneratingStep
          agents={agentsWithContent}
          contentRefs={contentRefs}
          error={error}
          onRetry={handleRegenerate}
        />
      )}
      
      {step === 'preview' && canvasData && (
        <PreviewStep
          canvasData={canvasData}
          confirmLoading={confirmLoading}
          onRegenerate={handleRegenerate}
          onConfirm={handleConfirm}
        />
      )}
      </div>
    </Modal>
  )
}

// ==================== 输入步骤组件 ====================

interface InputStepProps {
  form: any
  error: string | null
  onGenerate: () => void
}

const InputStep: React.FC<InputStepProps> = ({ form, error, onGenerate }) => {
  const [showAdvanced, setShowAdvanced] = React.useState(false)
  
  return (
    <div style={{ padding: '8px 0' }}>
      {/* 简洁引导文案 */}
      <div style={{
        marginBottom: 32,
        textAlign: 'center',
      }}>
        <div style={{
          fontSize: 13,
          color: '#86868b',
          letterSpacing: '0.02em',
          lineHeight: 1.5,
        }}>
          描述你的业务场景，自动生成流程骨架
        </div>
      </div>

      <Form
        form={form}
        layout="vertical"
        requiredMark={false}
      >
        {/* 业务名称 */}
        <Form.Item
          label={
            <span style={{
              fontSize: 13,
              fontWeight: 500,
              color: '#1d1d1f',
              letterSpacing: '-0.01em',
            }}>
              业务名称
            </span>
          }
          name="business_name"
          rules={[{ required: true, message: '请输入业务名称' }]}
          style={{ marginBottom: 24 }}
        >
          <Input
            placeholder="例如：用户开通月卡"
            style={{
              height: 48,
              borderRadius: 12,
              fontSize: 15,
              border: '1px solid #d2d2d7',
              boxShadow: 'none',
            }}
          />
        </Form.Item>
        
        {/* 业务描述 */}
        <Form.Item
          label={
            <span style={{
              fontSize: 13,
              fontWeight: 500,
              color: '#1d1d1f',
              letterSpacing: '-0.01em',
            }}>
              业务描述
            </span>
          }
          name="business_description"
          rules={[{ required: true, message: '请输入业务描述' }]}
          style={{ marginBottom: 8 }}
        >
          <TextArea
            rows={6}
            placeholder="描述业务流程的关键步骤..."
            style={{
              borderRadius: 12,
              fontSize: 15,
              lineHeight: 1.6,
              border: '1px solid #d2d2d7',
              padding: '14px 16px',
              resize: 'none',
            }}
          />
        </Form.Item>
        <div style={{
          fontSize: 12,
          color: '#86868b',
          marginBottom: 28,
          lineHeight: 1.5,
        }}>
          描述越详细，生成结果越准确
        </div>

        {/* 渠道 - 选择框 */}
        <Form.Item
          label={
            <span style={{
              fontSize: 13,
              fontWeight: 500,
              color: '#1d1d1f',
              letterSpacing: '-0.01em',
            }}>
              渠道
              <span style={{ fontWeight: 400, color: '#86868b', marginLeft: 6 }}>可选</span>
            </span>
          }
          name="channel"
          style={{ marginBottom: 24 }}
        >
          <Select
            placeholder="选择渠道"
            allowClear
            style={{ height: 48 }}
            options={[
              { value: 'mobile', label: '移动端' },
              { value: 'admin', label: '后台' },
            ]}
          />
        </Form.Item>
        
        {/* 高级选项 - 更明显的按钮 */}
        <div
          onClick={() => setShowAdvanced(!showAdvanced)}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '14px 16px',
            background: '#f5f5f7',
            borderRadius: 12,
            cursor: 'pointer',
            userSelect: 'none',
            marginBottom: 16,
            transition: 'background 0.2s ease',
          }}
          onMouseEnter={(e) => e.currentTarget.style.background = '#ebebed'}
          onMouseLeave={(e) => e.currentTarget.style.background = '#f5f5f7'}
        >
          <div>
            <div style={{ fontSize: 14, fontWeight: 500, color: '#1d1d1f' }}>
              补充技术数据
            </div>
            <div style={{ fontSize: 12, color: '#86868b', marginTop: 2 }}>
              提供日志或接口数据可提高准确度
            </div>
          </div>
          <span style={{
            display: 'inline-block',
            transition: 'transform 0.2s ease',
            transform: showAdvanced ? 'rotate(180deg)' : 'rotate(0deg)',
            fontSize: 12,
            color: '#86868b',
          }}>
            ▼
          </span>
        </div>
        
        {showAdvanced && (
          <div style={{
            background: '#f5f5f7',
            borderRadius: 12,
            padding: '20px',
            marginBottom: 16,
          }}>
            <Form.Item
              label={
                <span style={{ fontSize: 13, fontWeight: 500, color: '#1d1d1f' }}>
                  服务器日志
                </span>
              }
              name="structured_logs"
              style={{ marginBottom: 20 }}
            >
              <TextArea
                rows={3}
                placeholder="粘贴 JSON 格式的日志或 trace 数据"
                style={{
                  fontFamily: 'SF Mono, Monaco, monospace',
                  fontSize: 13,
                  borderRadius: 8,
                  border: '1px solid #d2d2d7',
                  background: '#fff',
                }}
              />
            </Form.Item>
            
            <Form.Item
              label={
                <span style={{ fontSize: 13, fontWeight: 500, color: '#1d1d1f' }}>
                  抓包接口
                </span>
              }
              name="api_captures"
              style={{ marginBottom: 0 }}
            >
              <TextArea
                rows={3}
                placeholder="粘贴 curl 命令或 HTTP 请求信息"
                style={{
                  fontFamily: 'SF Mono, Monaco, monospace',
                  fontSize: 13,
                  borderRadius: 8,
                  border: '1px solid #d2d2d7',
                  background: '#fff',
                }}
              />
            </Form.Item>
          </div>
        )}
      </Form>
      
      {error && (
        <Alert
          type="error"
          message={error}
          style={{ marginTop: 16, borderRadius: 12 }}
          showIcon
        />
      )}
    </div>
  )
}

// ==================== 生成进度组件 ====================

interface GeneratingStepProps {
  agents: AgentState[]
  contentRefs: React.MutableRefObject<(HTMLDivElement | null)[]>
  error: string | null
  onRetry: () => void
}

// Markdown 渲染样式 + 动画
const markdownStyles = `
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }
  .agent-markdown {
    font-size: 13px;
    line-height: 1.7;
    color: #1d1d1f;
  }
  .agent-markdown p {
    margin: 0 0 8px 0;
  }
  .agent-markdown p:last-child {
    margin-bottom: 0;
  }
  .agent-markdown ul, .agent-markdown ol {
    margin: 8px 0;
    padding-left: 20px;
  }
  .agent-markdown li {
    margin: 4px 0;
  }
  .agent-markdown code {
    background: #e8e8ed;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: SF Mono, Monaco, monospace;
    font-size: 12px;
    color: #1d1d1f;
  }
  .agent-markdown pre {
    background: #e8e8ed;
    padding: 12px 14px;
    border-radius: 8px;
    overflow-x: auto;
    margin: 8px 0;
    border: 1px solid #d2d2d7;
  }
  .agent-markdown pre code {
    background: none;
    padding: 0;
    color: #1d1d1f;
  }
  .agent-markdown strong {
    font-weight: 600;
  }
  .agent-markdown h1, .agent-markdown h2, .agent-markdown h3 {
    font-weight: 600;
    margin: 12px 0 8px 0;
    color: #1d1d1f;
  }
  .agent-markdown h1 { font-size: 16px; }
  .agent-markdown h2 { font-size: 15px; }
  .agent-markdown h3 { font-size: 14px; }
`

const GeneratingStep: React.FC<GeneratingStepProps> = ({
  agents,
  contentRefs,
  error,
  onRetry,
}) => {
  // 展开状态：默认展开正在运行的agent
  const [expandedIndexes, setExpandedIndexes] = React.useState<Set<number>>(new Set())
  // 思考区域折叠状态：key 是 agent index，默认展开
  const [thoughtCollapsed, setThoughtCollapsed] = React.useState<Set<number>>(new Set())
  // Markdown 渲染开关
  const [markdownEnabled, setMarkdownEnabled] = React.useState(true)
  
  // 当agent状态变化时，自动展开正在运行的agent
  React.useEffect(() => {
    agents.forEach((agent, index) => {
      if (agent.status === 'running') {
        setExpandedIndexes(prev => new Set(prev).add(index))
      }
    })
  }, [agents])
  
  // 切换思考区域折叠状态
  const toggleThoughtCollapsed = (index: number) => {
    setThoughtCollapsed(prev => {
      const newSet = new Set(prev)
      if (newSet.has(index)) {
        newSet.delete(index)
      } else {
        newSet.add(index)
      }
      return newSet
    })
  }
  
  const toggleExpand = (index: number) => {
    setExpandedIndexes(prev => {
      const newSet = new Set(prev)
      if (newSet.has(index)) {
        newSet.delete(index)
      } else {
        newSet.add(index)
      }
      return newSet
    })
  }
  
  // 获取状态样式
  const getStatusStyle = (status: AgentState['status']) => {
    switch (status) {
      case 'pending': return { bg: '#f5f5f7', color: '#86868b', icon: <ClockCircleOutlined /> }
      case 'running': return { bg: '#007aff', color: '#fff', icon: <LoadingOutlined spin /> }
      case 'completed': return { bg: '#34c759', color: '#fff', icon: <CheckCircleOutlined /> }
      case 'failed': return { bg: '#ff3b30', color: '#fff', icon: <CloseCircleOutlined /> }
    }
  }
  
  return (
    <div style={{ padding: '8px 0' }}>
      <style>{markdownStyles}</style>
      
      {/* Markdown 渲染开关 */}
      <div style={{
        display: 'flex',
        justifyContent: 'flex-end',
        alignItems: 'center',
        marginBottom: 8,
        fontSize: 12,
        color: '#86868b',
      }}>
        <span style={{ marginRight: 8 }}>Markdown 渲染</span>
        <Switch size="small" checked={markdownEnabled} onChange={setMarkdownEnabled} />
      </div>
      
      {/* 简洁进度指示 */}
      <div style={{
        textAlign: 'center',
        marginBottom: 32,
      }}>
        <div style={{ fontSize: 13, color: '#86868b', marginBottom: 16 }}>
          正在分析并生成流程骨架
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
          {agents.map((agent, index) => {
            const style = getStatusStyle(agent.status)
            return (
              <React.Fragment key={index}>
                <div style={{
                  width: 32,
                  height: 32,
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: style.bg,
                  color: style.color,
                  fontSize: 14,
                  transition: 'all 0.3s ease',
                }}>
                  {agent.status === 'pending' ? index + 1 : style.icon}
                </div>
                {index < agents.length - 1 && (
                  <div style={{
                    width: 40,
                    height: 2,
                    background: agent.status === 'completed' ? '#34c759' : '#e5e5ea',
                    borderRadius: 1,
                    transition: 'background 0.3s ease',
                  }} />
                )}
              </React.Fragment>
            )
          })}
        </div>
      </div>
      
      {/* Agent 卡片列表 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {agents.map((agent, index) => {
          const hasContent = agent.status === 'running' || agent.status === 'completed' || agent.status === 'failed'
          const isExpanded = hasContent && expandedIndexes.has(index)
          const isActive = agent.status === 'running'
          const style = getStatusStyle(agent.status)
          const text = agent.status === 'completed'
            ? (agent.output || agent.content || '已完成')
            : (agent.content || '处理中...')
          
          return (
            <div
              key={index}
              style={{
                background: '#fff',
                borderRadius: 12,
                border: isActive ? '1px solid #007aff' : '1px solid #e5e5ea',
                overflow: 'hidden',
                transition: 'border-color 0.2s ease',
              }}
            >
              {/* 卡片头部 */}
              <div 
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  padding: '14px 16px', 
                  gap: 12,
                  cursor: hasContent ? 'pointer' : 'default',
                }}
                onClick={() => hasContent && toggleExpand(index)}
              >
                <div style={{
                  width: 28,
                  height: 28,
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: style.bg,
                  color: style.color,
                  fontSize: 12,
                  flexShrink: 0,
                }}>
                  {agent.status === 'pending' ? index + 1 : style.icon}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ 
                    fontSize: 14,
                    fontWeight: 500, 
                    color: agent.status === 'pending' ? '#86868b' : '#1d1d1f',
                  }}>
                    {agent.name}
                  </div>
                  <div style={{ fontSize: 12, color: '#86868b', marginTop: 2 }}>
                    {agent.description}
                  </div>
                </div>
                {agent.durationMs && (
                  <span style={{ fontSize: 12, color: '#86868b' }}>
                    {(agent.durationMs / 1000).toFixed(1)}s
                  </span>
                )}
                {hasContent && (
                  <span style={{
                    color: '#86868b',
                    fontSize: 10,
                    transition: 'transform 0.2s ease',
                    transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                  }}>
                    ▼
                  </span>
                )}
              </div>
              
              {/* 内容区域 - 实时分区展示思考过程和最终结果 */}
              {hasContent && isExpanded && (
                <div
                  ref={(el) => { contentRefs.current[index] = el }}
                  style={{
                    padding: '0 16px 16px',
                  }}
                >
                  {/* 实时分区展示：运行中用 thoughtContent/answerContent，完成后用 thought/finalAnswer */}
                  {(() => {
                    const showThought = agent.status === 'completed' ? agent.thought : agent.thoughtContent
                    const showAnswer = agent.status === 'completed' ? agent.finalAnswer : agent.answerContent
                    const hasStructuredContent = showThought || showAnswer
                    
                    if (hasStructuredContent) {
                      return (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                          {/* 思考过程区域 - 可折叠 */}
                          {(showThought || agent.currentSection === 'thought') && (
                            <div>
                              <div 
                                onClick={() => showThought && toggleThoughtCollapsed(index)}
                                style={{
                                  fontSize: 11,
                                  fontWeight: 500,
                                  color: '#86868b',
                                  marginBottom: thoughtCollapsed.has(index) ? 0 : 8,
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: 6,
                                  textTransform: 'uppercase',
                                  letterSpacing: '0.5px',
                                  cursor: showThought ? 'pointer' : 'default',
                                  userSelect: 'none',
                                }}
                              >
                                <span style={{ 
                                  width: 6, 
                                  height: 6, 
                                  borderRadius: '50%', 
                                  background: agent.currentSection === 'thought' && agent.status === 'running' 
                                    ? '#f5a623' 
                                    : '#d2d2d7',
                                  animation: agent.currentSection === 'thought' && agent.status === 'running'
                                    ? 'pulse 1.5s ease-in-out infinite'
                                    : 'none',
                                }} />
                                思考
                                {showThought && (
                                  <span style={{
                                    fontSize: 10,
                                    color: '#c7c7cc',
                                    marginLeft: 2,
                                    transition: 'transform 0.2s ease',
                                    display: 'inline-block',
                                    transform: thoughtCollapsed.has(index) ? 'rotate(-90deg)' : 'rotate(0deg)',
                                  }}>
                                    ▼
                                  </span>
                                )}
                              </div>
                              {!thoughtCollapsed.has(index) && (
                                <div style={{
                                  fontSize: 13,
                                  lineHeight: 1.7,
                                  color: '#1d1d1f',
                                  paddingLeft: 12,
                                  borderLeft: '2px solid #e5e5ea',
                                }}>
                                  {showThought ? (
                                    markdownEnabled ? (
                                      <div className="agent-markdown">
                                        <ReactMarkdown>{showThought}</ReactMarkdown>
                                      </div>
                                    ) : (
                                      <div style={{ whiteSpace: 'pre-wrap' }}>
                                        {showThought}
                                      </div>
                                    )
                                  ) : (
                                    <span style={{ color: '#86868b', fontStyle: 'italic' }}>正在思考...</span>
                                  )}
                                </div>
                              )}
                            </div>
                          )}
                          {/* 最终结果区域 - 突出显示 */}
                          {(showAnswer || agent.currentSection === 'answer') && (
                            <div>
                              <div style={{
                                fontSize: 11,
                                fontWeight: 500,
                                color: '#86868b',
                                marginBottom: 8,
                                display: 'flex',
                                alignItems: 'center',
                                gap: 6,
                                textTransform: 'uppercase',
                                letterSpacing: '0.5px',
                              }}>
                                <span style={{ 
                                  width: 6, 
                                  height: 6, 
                                  borderRadius: '50%', 
                                  background: agent.currentSection === 'answer' && agent.status === 'running' 
                                    ? '#34c759' 
                                    : (agent.status === 'completed' ? '#34c759' : '#d2d2d7'),
                                  animation: agent.currentSection === 'answer' && agent.status === 'running'
                                    ? 'pulse 1.5s ease-in-out infinite'
                                    : 'none',
                                }} />
                                结果
                              </div>
                              <div style={{
                                background: '#f5f5f7',
                                borderRadius: 8,
                                padding: '12px 14px',
                                fontSize: 13,
                                lineHeight: 1.6,
                              }}>
                                {showAnswer ? (
                                  markdownEnabled ? (
                                    <div className="agent-markdown">
                                      <ReactMarkdown>{showAnswer}</ReactMarkdown>
                                    </div>
                                  ) : (
                                    <div style={{
                                      fontFamily: 'SF Mono, Monaco, monospace',
                                      fontSize: 12,
                                      whiteSpace: 'pre-wrap',
                                      color: '#1d1d1f',
                                    }}>
                                      {showAnswer}
                                    </div>
                                  )
                                ) : (
                                  <span style={{ color: '#86868b', fontStyle: 'italic' }}>正在生成...</span>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      )
                    } else {
                      // 没有结构化内容时，显示原始流式内容
                      return (
                        <div style={{
                          fontSize: 13,
                          lineHeight: 1.7,
                          color: '#1d1d1f',
                          paddingLeft: 12,
                          borderLeft: '2px solid #e5e5ea',
                        }}>
                          {markdownEnabled ? (
                            <div className="agent-markdown">
                              <ReactMarkdown>{text}</ReactMarkdown>
                            </div>
                          ) : (
                            <div style={{
                              whiteSpace: 'pre-wrap',
                            }}>
                              {text}
                            </div>
                          )}
                        </div>
                      )
                    }
                  })()}
                </div>
              )}
            </div>
          )
        })}
      </div>
      
      {error && (
        <Alert
          type="error"
          message="生成失败"
          description={error}
          showIcon
          style={{ marginTop: 16, borderRadius: 12 }}
          action={<Button size="small" onClick={onRetry}>重试</Button>}
        />
      )}
    </div>
  )
}

// ==================== 预览步骤组件 ====================

interface PreviewStepProps {
  canvasData: CanvasData
  confirmLoading: boolean
  onRegenerate: () => void
  onConfirm: () => void
}

/**
 * 根据源节点和目标节点的位置，计算最佳的连接 Handle
 */
const computeOptimalHandles = (
  sourcePos: { x: number; y: number; width: number },
  targetPos: { x: number; y: number; width: number }
): { sourceHandle: string; targetHandle: string } => {
  const dx = targetPos.x - sourcePos.x
  const dy = targetPos.y - sourcePos.y
  
  const sourceCenterX = sourcePos.x + sourcePos.width / 2
  const targetCenterX = targetPos.x + targetPos.width / 2
  const horizontalDist = Math.abs(targetCenterX - sourceCenterX)
  const verticalDist = Math.abs(dy)
  
  if (verticalDist > 50 && verticalDist > horizontalDist * 0.5) {
    if (dy > 0) {
      return { sourceHandle: 'b-out', targetHandle: 't-in' }
    } else {
      return { sourceHandle: 't-out', targetHandle: 'b-in' }
    }
  } else {
    if (dx > 0) {
      return { sourceHandle: 'r-out', targetHandle: 'l-in' }
    } else {
      return { sourceHandle: 'l-out', targetHandle: 'r-in' }
    }
  }
}

/**
 * 三层布局算法：步骤(上) -> 实现(中) -> 数据资源(下)
 * 步骤之间水平排列，实现和数据资源根据关联关系定位
 */
function layoutCanvasNodes(canvasData: CanvasData) {
  const stepHeight = 50
  const implHeight = 70
  const baseGap = 60
  const verticalGap = 100
  
  const positions: Map<string, { x: number; y: number; width: number }> = new Map()
  
  // 1. 计算每个步骤节点的宽度（基于名称长度）
  const stepWidths: number[] = canvasData.steps.map((step) => {
    const nameLen = step.name?.length || 10
    return Math.min(280, Math.max(150, 150 + nameLen * 8))
  })
  
  // 2. 布局步骤节点（第一行，动态间距）
  const stepY = 0
  let currentX = 0
  canvasData.steps.forEach((step, index) => {
    const stepWidth = stepWidths[index]
    positions.set(step.step_id, {
      x: currentX,
      y: stepY,
      width: stepWidth,
    })
    // 动态间距：基于当前和下一个节点宽度
    const nextWidth = stepWidths[index + 1] || stepWidth
    const dynamicGap = baseGap + Math.max(stepWidth, nextWidth) * 0.2
    currentX += stepWidth + dynamicGap
  })
  
  // 3. 为每个步骤找到关联的实现
  const stepToImpls: Map<string, string[]> = new Map()
  canvasData.step_impl_links.forEach(link => {
    const impls = stepToImpls.get(link.step_id) || []
    impls.push(link.impl_id)
    stepToImpls.set(link.step_id, impls)
  })
  
  // 4. 计算实现节点宽度
  const implWidthMap = new Map<string, number>()
  canvasData.implementations.forEach((impl) => {
    const nameLen = impl.name?.length || 10
    implWidthMap.set(impl.impl_id, Math.min(280, Math.max(150, 150 + nameLen * 8)))
  })
  
  // 5. 布局实现节点（第二行，居中对齐到步骤）
  const implY = stepHeight + verticalGap
  let implX = 0
  const placedImpls = new Set<string>()
  const implGap = 30
  let implOccupiedRanges: Array<{ start: number; end: number }> = []

  const findNonOverlappingImplX = (preferredX: number, width: number): number => {
    let x = preferredX
    let attempts = 0
    const maxAttempts = 100

    while (attempts < maxAttempts) {
      const hasOverlap = implOccupiedRanges.some(range =>
        !(x + width + implGap < range.start || x > range.end + implGap)
      )
      if (!hasOverlap) break
      x += 50
      attempts++
    }
    return x
  }

  canvasData.steps.forEach((step) => {
    const stepPos = positions.get(step.step_id)
    const implIds = stepToImpls.get(step.step_id) || []
    
    if (stepPos && implIds.length > 0) {
      // 计算该步骤下所有实现的总宽度
      const totalImplWidth = implIds.reduce((sum, id) => sum + (implWidthMap.get(id) || 150), 0)
      const totalWidth = totalImplWidth + (implIds.length - 1) * implGap
      // 居中对齐到步骤节点
      let startX = stepPos.x + stepPos.width / 2 - totalWidth / 2
      
      implIds.forEach((implId) => {
        if (!placedImpls.has(implId)) {
          const implWidth = implWidthMap.get(implId) || 150
          const finalX = findNonOverlappingImplX(startX, implWidth)
          positions.set(implId, {
            x: finalX,
            y: implY,
            width: implWidth,
          })
          placedImpls.add(implId)
          implOccupiedRanges.push({ start: finalX, end: finalX + implWidth })
          startX = finalX + implWidth + implGap
        }
      })
    }
  })
  
  // 放置未关联的实现
  canvasData.implementations.forEach(impl => {
    if (!placedImpls.has(impl.impl_id)) {
      const implWidth = implWidthMap.get(impl.impl_id) || 150
      const finalX = findNonOverlappingImplX(implX, implWidth)
      positions.set(impl.impl_id, { x: finalX, y: implY, width: implWidth })
      implOccupiedRanges.push({ start: finalX, end: finalX + implWidth })
      implX = finalX + implWidth + 40
    }
  })
  
  // 6. 为每个实现找到关联的数据资源
  const implToResources: Map<string, string[]> = new Map()
  canvasData.impl_data_links.forEach(link => {
    const resources = implToResources.get(link.impl_id) || []
    resources.push(link.resource_id)
    implToResources.set(link.impl_id, resources)
  })
  
  // 7. 计算数据资源宽度
  const resWidthMap = new Map<string, number>()
  canvasData.data_resources.forEach((res) => {
    const nameLen = res.name?.length || 10
    resWidthMap.set(res.resource_id, Math.min(250, Math.max(140, 140 + nameLen * 7)))
  })
  
  // 8. 布局数据资源节点（防止重叠的改进算法）
  const resY = implY + implHeight + verticalGap
  const placedResources = new Map<string, { x: number; width: number }>()
  const resGap = 30
  
  // 追踪已占用的X区间，用于防止重叠
  let occupiedRanges: Array<{ start: number; end: number }> = []
  
  // 检查并找到不重叠的位置
  const findNonOverlappingX = (preferredX: number, width: number): number => {
    let x = preferredX
    let attempts = 0
    const maxAttempts = 100
    
    while (attempts < maxAttempts) {
      const hasOverlap = occupiedRanges.some(range => 
        !(x + width + resGap < range.start || x > range.end + resGap)
      )
      if (!hasOverlap) break
      // 尝试向右移动
      x += 50
      attempts++
    }
    return x
  }
  
  // 按实现节点的X位置排序处理
  const sortedImpls = [...canvasData.implementations].sort((a, b) => {
    const posA = positions.get(a.impl_id)
    const posB = positions.get(b.impl_id)
    return (posA?.x || 0) - (posB?.x || 0)
  })
  
  sortedImpls.forEach((impl) => {
    const implPos = positions.get(impl.impl_id)
    const resourceIds = implToResources.get(impl.impl_id) || []
    
    if (implPos && resourceIds.length > 0) {
      // 过滤已放置的资源
      const unplacedResources = resourceIds.filter(id => !placedResources.has(id))
      if (unplacedResources.length === 0) return
      
      const totalResWidth = unplacedResources.reduce((sum, id) => sum + (resWidthMap.get(id) || 140), 0)
      const totalWidth = totalResWidth + (unplacedResources.length - 1) * resGap
      // 期望居中对齐到实现节点
      let preferredStartX = implPos.x + (implPos.width || 150) / 2 - totalWidth / 2
      
      unplacedResources.forEach((resId) => {
        const resWidth = resWidthMap.get(resId) || 140
        const finalX = findNonOverlappingX(preferredStartX, resWidth)
        
        positions.set(resId, {
          x: finalX,
          y: resY,
          width: resWidth,
        })
        placedResources.set(resId, { x: finalX, width: resWidth })
        occupiedRanges.push({ start: finalX, end: finalX + resWidth })
        preferredStartX = finalX + resWidth + resGap
      })
    }
  })
  
  // 放置未关联的数据资源
  let resX = occupiedRanges.length > 0 
    ? Math.max(...occupiedRanges.map(r => r.end)) + resGap 
    : 0
  canvasData.data_resources.forEach(res => {
    if (!placedResources.has(res.resource_id)) {
      const resWidth = resWidthMap.get(res.resource_id) || 140
      positions.set(res.resource_id, { x: resX, y: resY, width: resWidth })
      resX += resWidth + resGap
    }
  })
  
  return positions
}

/**
 * 预览画布自定义节点组件（简化版，不含交互功能）
 * 与实际画布 AllSidesNode 保持一致的样式和 Handle
 */
const PreviewNode = React.memo(({ data }: any) => {
  const baseHandleStyle = {
    width: 6,
    height: 6,
    background: '#bfbfbf',
    border: '1px solid #d9d9d9',
    borderRadius: '50%',
  } as const

  const nodeType = data?.nodeType as 'step' | 'implementation' | 'data' | undefined
  let headerBg = '#f5f5f5'
  let headerColor = '#595959'

  if (nodeType === 'step') {
    headerBg = '#e6f4ff'
    headerColor = '#0958d9'
  } else if (nodeType === 'implementation') {
    headerBg = '#f6ffed'
    headerColor = '#237804'
  } else if (nodeType === 'data') {
    headerBg = '#fff7e6'
    headerColor = '#ad6800'
  }

  return (
    <>
      {/* 8个Handle：上下左右各2个（in/out） */}
      <Handle type="target" position={Position.Top} id="t-in" style={{ ...baseHandleStyle, top: -4 }} />
      <Handle type="source" position={Position.Top} id="t-out" style={{ ...baseHandleStyle, top: -4 }} />
      <Handle type="target" position={Position.Bottom} id="b-in" style={{ ...baseHandleStyle, bottom: -4 }} />
      <Handle type="source" position={Position.Bottom} id="b-out" style={{ ...baseHandleStyle, bottom: -4 }} />
      <Handle type="target" position={Position.Left} id="l-in" style={{ ...baseHandleStyle, left: -4 }} />
      <Handle type="source" position={Position.Left} id="l-out" style={{ ...baseHandleStyle, left: -4 }} />
      <Handle type="target" position={Position.Right} id="r-in" style={{ ...baseHandleStyle, right: -4 }} />
      <Handle type="source" position={Position.Right} id="r-out" style={{ ...baseHandleStyle, right: -4 }} />
      
      <div style={{
        borderRadius: 12,
        background: '#ffffff',
        overflow: 'hidden',
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
      }}>
        {data?.typeLabel && (
          <div style={{
            padding: '4px 8px',
            background: headerBg,
            color: headerColor,
            borderBottom: '1px solid #f0f0f0',
            fontWeight: 500,
            fontSize: 11,
            borderTopLeftRadius: 10,
            borderTopRightRadius: 10,
          }}>
            {data.typeLabel}
          </div>
        )}
        <div style={{
          padding: 10,
          fontSize: 12,
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
          justifyContent: 'center',
        }}>
          <div style={{ fontWeight: 500, fontSize: 13, color: '#262626', lineHeight: '18px' }}>
            {data?.label}
          </div>
          
          {/* 步骤：显示描述 */}
          {nodeType === 'step' && data?.description && (
            <div style={{ fontSize: 11, color: '#8c8c8c', lineHeight: '16px' }}>
              <span style={{ color: '#bfbfbf', marginRight: 4 }}>描述:</span>
              <span style={{
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
              }}>
                {data.description}
              </span>
            </div>
          )}
          
          {/* 实现：显示类型和系统 */}
          {nodeType === 'implementation' && (
            <>
              {data?.type && (
                <div style={{ fontSize: 11, lineHeight: '16px' }}>
                  <span style={{ color: '#bfbfbf', marginRight: 4 }}>类型:</span>
                  <span style={{ color: '#52c41a' }}>{data.type}</span>
                </div>
              )}
              {data?.system && (
                <div style={{ fontSize: 11, color: '#8c8c8c', lineHeight: '16px' }}>
                  <span style={{ color: '#bfbfbf', marginRight: 4 }}>系统:</span>
                  {data.system}
                </div>
              )}
            </>
          )}
          
          {/* 数据资源：显示类型和描述 */}
          {nodeType === 'data' && (
            <>
              {data?.resourceType && (
                <div style={{ fontSize: 11, lineHeight: '16px' }}>
                  <span style={{ color: '#bfbfbf', marginRight: 4 }}>类型:</span>
                  <span style={{ color: '#faad14' }}>{data.resourceType}</span>
                </div>
              )}
              {data?.description && (
                <div style={{ fontSize: 11, color: '#8c8c8c', lineHeight: '16px' }}>
                  <span style={{ color: '#bfbfbf', marginRight: 4 }}>描述:</span>
                  <span style={{
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden',
                  }}>
                    {data.description}
                  </span>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </>
  )
})

// 预览画布节点类型注册
const previewNodeTypes = {
  preview: PreviewNode,
}

// 苹果风格色彩
const appleColors = {
  step: { bg: '#f5f5f7', color: '#1d1d1f', accent: '#007aff' },
  impl: { bg: '#f5f5f7', color: '#1d1d1f', accent: '#34c759' },
  data: { bg: '#f5f5f7', color: '#1d1d1f', accent: '#ff9500' },
}

const PreviewStep: React.FC<PreviewStepProps> = ({
  canvasData,
  confirmLoading,
  onRegenerate,
  onConfirm,
}) => {
  // 转换为ReactFlow节点和边（与实际画布样式一致）
  const { nodes, edges } = React.useMemo(() => {
    const positions = layoutCanvasNodes(canvasData)
    const nodes: Node[] = []
    const edges: Edge[] = []
    
    // 1. 步骤节点
    canvasData.steps.forEach((step) => {
      const pos = positions.get(step.step_id) || { x: 0, y: 0, width: 150 }
      nodes.push({
        id: step.step_id,
        type: 'preview',
        position: { x: pos.x, y: pos.y },
        data: { 
          nodeType: 'step',
          typeLabel: '步骤',
          label: step.name,
          description: step.description,
        },
        style: { 
          width: pos.width || 150,
          background: 'transparent', 
          border: 'none', 
          padding: 0,
        },
      })
    })
    
    // 2. 实现节点
    canvasData.implementations.forEach((impl) => {
      const pos = positions.get(impl.impl_id) || { x: 0, y: 150, width: 150 }
      nodes.push({
        id: impl.impl_id,
        type: 'preview',
        position: { x: pos.x, y: pos.y },
        data: { 
          nodeType: 'implementation',
          typeLabel: '实现',
          label: impl.name,
          type: impl.type,
          system: impl.system,
        },
        style: { 
          width: pos.width || 150,
          background: 'transparent', 
          border: 'none', 
          padding: 0,
        },
      })
    })
    
    // 3. 数据资源节点
    canvasData.data_resources.forEach((res) => {
      const pos = positions.get(res.resource_id) || { x: 0, y: 300, width: 140 }
      nodes.push({
        id: res.resource_id,
        type: 'preview',
        position: { x: pos.x, y: pos.y },
        data: { 
          nodeType: 'data',
          typeLabel: '数据资源',
          label: res.name,
          resourceType: res.type,
          description: res.description,
        },
        style: { 
          width: pos.width || 140,
          background: 'transparent', 
          border: 'none', 
          padding: 0,
        },
      })
    })
    
    // 辅助函数：获取智能连接点
    const getHandles = (sourceId: string, targetId: string) => {
      const sourcePos = positions.get(sourceId)
      const targetPos = positions.get(targetId)
      if (sourcePos && targetPos) {
        return computeOptimalHandles(sourcePos, targetPos)
      }
      return { sourceHandle: 'r-out', targetHandle: 'l-in' }
    }
    
    // 4. 步骤之间的边（不再在连线上展示文字）
    canvasData.edges.forEach((edge, index) => {
      const handles = getHandles(edge.from_step_id, edge.to_step_id)
      edges.push({
        id: `step-edge-${index}`,
        source: edge.from_step_id,
        target: edge.to_step_id,
        sourceHandle: handles.sourceHandle,
        targetHandle: handles.targetHandle,
        type: 'simplebezier',
        markerEnd: { type: MarkerType.ArrowClosed },
        style: { stroke: '#1677ff', strokeWidth: 2 },
      })
    })
    
    // 5. 步骤-实现关联边
    canvasData.step_impl_links.forEach((link, index) => {
      const handles = getHandles(link.step_id, link.impl_id)
      edges.push({
        id: `step-impl-${index}`,
        source: link.step_id,
        target: link.impl_id,
        sourceHandle: handles.sourceHandle,
        targetHandle: handles.targetHandle,
        type: 'simplebezier',
        markerEnd: { type: MarkerType.ArrowClosed },
        style: { stroke: '#52c41a' },
      })
    })
    
    // 6. 实现-数据资源关联边
    canvasData.impl_data_links.forEach((link, index) => {
      const handles = getHandles(link.impl_id, link.resource_id)
      edges.push({
        id: `impl-data-${index}`,
        source: link.impl_id,
        target: link.resource_id,
        sourceHandle: handles.sourceHandle,
        targetHandle: handles.targetHandle,
        type: 'simplebezier',
        markerEnd: { type: MarkerType.ArrowClosed },
        style: { stroke: '#faad14' },
      })
    })
    
    return { nodes, edges }
  }, [canvasData])
  
  return (
    <div style={{ padding: '4px 0' }}>
      {/* 简洁顶部信息栏 */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 12,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 15, fontWeight: 500, color: '#1d1d1f' }}>
            {canvasData.process.name}
          </span>
          {canvasData.process.channel && (
            <span style={{
              padding: '2px 8px',
              background: '#f5f5f7',
              borderRadius: 4,
              fontSize: 11,
              color: '#86868b',
            }}>
              {canvasData.process.channel === 'mobile' ? '移动端' : canvasData.process.channel === 'admin' ? '后台' : canvasData.process.channel}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 16, fontSize: 12, color: '#86868b' }}>
          <span><span style={{ color: '#007aff', fontWeight: 500 }}>{canvasData.steps.length}</span> 步骤</span>
          <span><span style={{ color: '#34c759', fontWeight: 500 }}>{canvasData.implementations.length}</span> 实现</span>
          <span><span style={{ color: '#ff9500', fontWeight: 500 }}>{canvasData.data_resources.length}</span> 资源</span>
        </div>
      </div>
      
      {/* 流程图预览 */}
      <div
        style={{
          height: 'calc(55vh - 100px)',
          minHeight: 350,
          maxHeight: 480,
          border: '1px solid #e5e5ea',
          borderRadius: 12,
          marginBottom: 20,
          background: '#f5f5f7',
          overflow: 'hidden',
        }}
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={previewNodeTypes}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          minZoom={0.3}
          maxZoom={1.5}
        >
          <Background color="#e5e5ea" gap={20} />
          <Controls showInteractive={false} position="bottom-right" />
        </ReactFlow>
      </div>
      
      {/* 节点概览 - 三列等宽布局 */}
      <div style={{ 
        background: '#f5f5f7', 
        borderRadius: 10, 
        padding: '14px 16px',
        display: 'grid',
        gridTemplateColumns: '1fr 1fr 1fr',
        gap: 16,
      }}>
        {/* 步骤列表 */}
        <div style={{ minWidth: 0 }}>
          <div style={{
            fontSize: 11,
            fontWeight: 500,
            color: '#86868b',
            marginBottom: 6,
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
            display: 'flex',
            alignItems: 'center',
            gap: 4,
          }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#007aff' }} />
            步骤
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {canvasData.steps.map((step) => (
              <div 
                key={step.step_id} 
                style={{ 
                  fontSize: 12,
                  color: '#1d1d1f',
                  lineHeight: 1.5,
                  wordBreak: 'break-word',
                }}
              >
                {step.name}
              </div>
            ))}
          </div>
        </div>

        {/* 实现列表 */}
        <div style={{ minWidth: 0 }}>
          <div style={{
            fontSize: 11,
            fontWeight: 500,
            color: '#86868b',
            marginBottom: 6,
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
            display: 'flex',
            alignItems: 'center',
            gap: 4,
          }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#34c759' }} />
            实现
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {canvasData.implementations.map((impl) => (
              <div 
                key={impl.impl_id} 
                style={{ 
                  fontSize: 12,
                  color: '#1d1d1f',
                  lineHeight: 1.5,
                  wordBreak: 'break-word',
                }}
              >
                <span>{impl.name}</span>
                {impl.system && (
                  <span style={{ 
                    fontSize: 10, 
                    color: '#86868b',
                    background: '#e5e5ea',
                    padding: '1px 5px',
                    borderRadius: 3,
                    marginLeft: 4,
                  }}>{impl.system}</span>
                )}
              </div>
            ))}
            {canvasData.implementations.length === 0 && (
              <div style={{ fontSize: 12, color: '#86868b', fontStyle: 'italic' }}>无</div>
            )}
          </div>
        </div>
        
        {/* 数据资源列表 */}
        <div style={{ minWidth: 0 }}>
          <div style={{
            fontSize: 11,
            fontWeight: 500,
            color: '#86868b',
            marginBottom: 6,
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
            display: 'flex',
            alignItems: 'center',
            gap: 4,
          }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#ff9500' }} />
            数据
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {canvasData.data_resources.map((res) => (
              <div 
                key={res.resource_id} 
                style={{ 
                  fontSize: 12,
                  color: '#1d1d1f',
                  lineHeight: 1.5,
                  wordBreak: 'break-word',
                }}
              >
                <span>{res.name}</span>
                {res.type && (
                  <span style={{ 
                    fontSize: 10, 
                    color: '#86868b',
                    background: '#e5e5ea',
                    padding: '1px 5px',
                    borderRadius: 3,
                    marginLeft: 4,
                  }}>{res.type}</span>
                )}
              </div>
            ))}
            {canvasData.data_resources.length === 0 && (
              <div style={{ fontSize: 12, color: '#86868b', fontStyle: 'italic' }}>无</div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default SkeletonGenerateModal

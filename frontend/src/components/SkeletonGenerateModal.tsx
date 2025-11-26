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
  Collapse,
  Alert,
  Typography,
  Divider,
} from 'antd'
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
import { ReactFlow, Background, Controls, type Node, type Edge } from '@xyflow/react'
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
  content: string  // 流式累积内容
  output: string   // 最终输出
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
  const [agents, setAgents] = useState<AgentState[]>([
    { name: '数据分析师', description: '分析原始技术数据', status: 'pending', content: '', output: '' },
    { name: '流程设计师', description: '设计业务流程步骤', status: 'pending', content: '', output: '' },
    { name: '技术架构师', description: '补充技术实现细节', status: 'pending', content: '', output: '' },
  ])
  
  const wsRef = useRef<WebSocket | null>(null)
  const scrollContainerRef = useRef<HTMLDivElement | null>(null)
  const contentRefs = useRef<(HTMLDivElement | null)[]>([])
  const autoScrollRef = useRef(true)
  const userScrollingRef = useRef(false)
  const lastScrollTopRef = useRef(0)
  
  // 使用通用的多通道打字机 hook
  const typewriter = useMultiTypewriter(3, {
    onTick: () => {
      // 打字机每次显示字符时触发滚动
      if (autoScrollRef.current) {
        const container = scrollContainerRef.current
        if (container) {
          requestAnimationFrame(() => {
            container.scrollTop = container.scrollHeight
          })
        }
      }
    },
  })
  
  // 将打字机的 texts 同步到 agents 的 content（用于渲染）
  const agentsWithContent = agents.map((agent, idx) => ({
    ...agent,
    content: typewriter.texts[idx] || '',
  }))
  
  // 重置状态
  const resetState = useCallback(() => {
    typewriter.reset()
    setStep('input')
    setError(null)
    setCanvasData(null)
    setAgents([
      { name: '数据分析师', description: '分析原始技术数据', status: 'pending', content: '', output: '' },
      { name: '流程设计师', description: '设计业务流程步骤', status: 'pending', content: '', output: '' },
      { name: '技术架构师', description: '补充技术实现细节', status: 'pending', content: '', output: '' },
    ])
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [typewriter])
  
  // 关闭弹窗时重置
  useEffect(() => {
    if (!open) {
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
            ? { ...agent, status: 'running', content: '', startTime: Date.now() }
            : agent
        ))
        break
        
      case 'stream':
        // 追加到打字机缓冲区
        if (chunk.content && chunk.agent_index !== undefined) {
          typewriter.append(chunk.agent_index, chunk.content)
        }
        break
        
      case 'agent_end':
        // 标记完成，触发加速显示剩余内容
        typewriter.finish(chunk.agent_index)
        setAgents(prev => prev.map((agent, idx) => 
          idx === chunk.agent_index
            ? {
                ...agent,
                status: 'completed',
                output: chunk.agent_output || '',
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
        typewriter.reset()
        setError(chunk.error || '生成失败')
        setAgents(prev => prev.map(agent => 
          agent.status === 'running'
            ? { ...agent, status: 'failed' }
            : agent
        ))
        break
    }
  }, [typewriter])
  
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
      typewriter.reset()
      
      // 重置Agent状态
      setAgents([
        { name: '数据分析师', description: '分析原始技术数据', status: 'pending', content: '', output: '' },
        { name: '流程设计师', description: '设计业务流程步骤', status: 'pending', content: '', output: '' },
        { name: '技术架构师', description: '补充技术实现细节', status: 'pending', content: '', output: '' },
      ])
      
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
  }, [form, handleChunk, typewriter])
  
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
  
  return (
    <Modal
      open={open}
      onCancel={onClose}
      title={renderTitle()}
      width={900}
      footer={renderFooter()}
      maskClosable={false}
      destroyOnClose
      styles={{ body: { padding: 0 } }}
    >
      <div
        ref={scrollContainerRef}
        onScroll={handleContainerScroll}
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
  return (
    <Form form={form} layout="vertical">
      <Form.Item
        label="业务名称"
        name="business_name"
        rules={[{ required: true, message: '请输入业务名称' }]}
      >
        <Input placeholder="如：C端用户开通月卡" />
      </Form.Item>
      
      <Form.Item
        label="业务描述"
        name="business_description"
        rules={[{ required: true, message: '请输入业务描述' }]}
        extra={<span style={{ color: '#8c8c8c', fontSize: 12 }}>详细描述业务流程，AI将根据描述生成步骤、实现和数据资源</span>}
      >
        <TextArea
          rows={5}
          placeholder="描述业务流程的步骤和涉及的系统，例如：&#10;用户在App点击开通月卡 → 系统校验用户资格 → 展示套餐列表 → 用户选择并支付 → 开通成功"
        />
      </Form.Item>
      
      <Form.Item label="渠道" name="channel">
        <Input placeholder="app / web / mini_program（可选）" />
      </Form.Item>
      
      <Collapse
        size="small"
        ghost
        items={[
          {
            key: 'advanced',
            label: <Text type="secondary">补充技术数据（可选，提高生成准确度）</Text>,
            children: (
              <Space direction="vertical" style={{ width: '100%' }} size={12}>
                <Form.Item label="结构化日志" name="structured_logs" style={{ marginBottom: 0 }}>
                  <TextArea
                    rows={3}
                    placeholder="粘贴JSON格式的日志或trace数据"
                    style={{ fontFamily: 'monospace', fontSize: 12 }}
                  />
                </Form.Item>
                <Form.Item label="抓包接口" name="api_captures" style={{ marginBottom: 0 }}>
                  <TextArea
                    rows={3}
                    placeholder="粘贴curl命令或HTTP请求信息"
                    style={{ fontFamily: 'monospace', fontSize: 12 }}
                  />
                </Form.Item>
              </Space>
            ),
          },
        ]}
      />
      
      {error && (
        <Alert type="error" message={error} style={{ marginTop: 16 }} showIcon />
      )}
    </Form>
  )
}

// ==================== 生成进度组件 ====================

interface GeneratingStepProps {
  agents: AgentState[]
  contentRefs: React.MutableRefObject<(HTMLDivElement | null)[]>
  error: string | null
  onRetry: () => void
}

const GeneratingStep: React.FC<GeneratingStepProps> = ({
  agents,
  contentRefs,
  error,
  onRetry,
}) => {
  // 展开状态：默认展开正在运行的agent
  const [expandedIndexes, setExpandedIndexes] = React.useState<Set<number>>(new Set())
  
  // 当agent状态变化时，自动展开正在运行的agent
  React.useEffect(() => {
    agents.forEach((agent, index) => {
      if (agent.status === 'running') {
        setExpandedIndexes(prev => new Set(prev).add(index))
      }
    })
  }, [agents])
  
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
  
  const getStatusIcon = (status: AgentState['status']) => {
    switch (status) {
      case 'pending': return <ClockCircleOutlined style={{ color: '#bfbfbf' }} />
      case 'running': return <LoadingOutlined style={{ color: '#1677ff' }} spin />
      case 'completed': return <CheckCircleOutlined style={{ color: '#52c41a' }} />
      case 'failed': return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
    }
  }
  
  return (
    <div>
      {/* 进度条 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
        {agents.map((agent, index) => {
          const isCompleted = agent.status === 'completed'
          const isActive = agent.status === 'running'
          return (
            <React.Fragment key={index}>
              <div style={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: isCompleted ? '#52c41a' : isActive ? '#1677ff' : '#f0f0f0',
                color: isCompleted || isActive ? '#fff' : '#8c8c8c',
                fontSize: 12,
                fontWeight: 500,
              }}>
                {isCompleted ? <CheckCircleOutlined /> : index + 1}
              </div>
              {index < agents.length - 1 && (
                <div style={{
                  flex: 1,
                  height: 2,
                  background: isCompleted ? '#52c41a' : '#f0f0f0',
                }} />
              )}
            </React.Fragment>
          )
        })}
      </div>
      
      {/* Agent 列表 */}
      <Space direction="vertical" style={{ width: '100%' }} size={12}>
        {agents.map((agent, index) => {
          const hasContent = agent.status === 'running' || agent.status === 'completed' || agent.status === 'failed'
          const isExpanded = hasContent && expandedIndexes.has(index)
          return (
            <div
              key={index}
              style={{
                border: `1px solid ${agent.status === 'running' ? '#1677ff' : '#f0f0f0'}`,
                borderRadius: 8,
                background: agent.status === 'pending' ? '#fafafa' : '#fff',
              }}
            >
              <div 
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  padding: '10px 12px', 
                  gap: 10,
                  cursor: hasContent ? 'pointer' : 'default',
                }}
                onClick={() => hasContent && toggleExpand(index)}
              >
                {getStatusIcon(agent.status)}
                <div style={{ flex: 1 }}>
                  <div style={{ 
                    fontWeight: 500, 
                    color: agent.status === 'pending' ? '#8c8c8c' : '#262626',
                  }}>
                    {agent.name}
                  </div>
                  <div style={{ fontSize: 12, color: '#8c8c8c' }}>{agent.description}</div>
                </div>
                {agent.durationMs && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {(agent.durationMs / 1000).toFixed(1)}s
                  </Text>
                )}
                {hasContent && (
                  <span style={{ color: '#8c8c8c', fontSize: 12 }}>
                    {isExpanded ? <UpOutlined /> : <DownOutlined />}
                  </span>
                )}
              </div>
              
              {hasContent && (
                <div
                  style={{
                    // 不再设置高度上限，依靠整体 Modal 滚动展示完整内容
                    display: isExpanded ? 'block' : 'none',
                  }}
                >
                  <div
                    ref={(el) => { contentRefs.current[index] = el }}
                    style={{ padding: '0 12px 12px' }}
                  >
                    <div style={{
                      background: '#f5f5f5',
                      borderRadius: 6,
                      padding: 10,
                      fontSize: 12,
                      lineHeight: 1.6,
                      color: '#595959',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}>
                      {agent.status === 'completed' ? (agent.output || agent.content || '已完成') : (agent.content || '处理中...')}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </Space>
      
      {error && (
        <Alert
          type="error"
          message="生成失败"
          description={error}
          showIcon
          style={{ marginTop: 16 }}
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
 * 三层布局算法：步骤(上) -> 实现(中) -> 数据资源(下)
 * 步骤之间水平排列，实现和数据资源根据关联关系定位
 */
function layoutCanvasNodes(canvasData: CanvasData) {
  const stepWidth = 160
  const stepHeight = 50
  const implWidth = 180
  const implHeight = 70
  const resWidth = 160
  const resHeight = 60
  const horizontalGap = 40
  const verticalGap = 80
  
  const positions: Map<string, { x: number; y: number }> = new Map()
  
  // 1. 布局步骤节点（第一行，水平排列）
  const stepY = 0
  canvasData.steps.forEach((step, index) => {
    positions.set(step.step_id, {
      x: index * (stepWidth + horizontalGap),
      y: stepY,
    })
  })
  
  // 2. 为每个步骤找到关联的实现
  const stepToImpls: Map<string, string[]> = new Map()
  canvasData.step_impl_links.forEach(link => {
    const impls = stepToImpls.get(link.step_id) || []
    impls.push(link.impl_id)
    stepToImpls.set(link.step_id, impls)
  })
  
  // 3. 布局实现节点（第二行，根据关联的步骤定位）
  const implY = stepHeight + verticalGap
  let implX = 0
  const placedImpls = new Set<string>()
  
  canvasData.steps.forEach((step) => {
    const stepPos = positions.get(step.step_id)
    const implIds = stepToImpls.get(step.step_id) || []
    
    implIds.forEach((implId, idx) => {
      if (!placedImpls.has(implId)) {
        positions.set(implId, {
          x: stepPos ? stepPos.x + idx * 50 : implX,
          y: implY,
        })
        placedImpls.add(implId)
        implX += implWidth + horizontalGap / 2
      }
    })
  })
  
  // 放置未关联的实现
  canvasData.implementations.forEach(impl => {
    if (!placedImpls.has(impl.impl_id)) {
      positions.set(impl.impl_id, { x: implX, y: implY })
      implX += implWidth + horizontalGap / 2
    }
  })
  
  // 4. 为每个实现找到关联的数据资源
  const implToResources: Map<string, string[]> = new Map()
  canvasData.impl_data_links.forEach(link => {
    const resources = implToResources.get(link.impl_id) || []
    resources.push(link.resource_id)
    implToResources.set(link.impl_id, resources)
  })
  
  // 5. 布局数据资源节点（第三行）
  const resY = implY + implHeight + verticalGap
  let resX = 0
  const placedResources = new Set<string>()
  
  canvasData.implementations.forEach((impl) => {
    const implPos = positions.get(impl.impl_id)
    const resourceIds = implToResources.get(impl.impl_id) || []
    
    resourceIds.forEach((resId, idx) => {
      if (!placedResources.has(resId)) {
        positions.set(resId, {
          x: implPos ? implPos.x + idx * 40 : resX,
          y: resY,
        })
        placedResources.add(resId)
        resX += resWidth + horizontalGap / 2
      }
    })
  })
  
  // 放置未关联的数据资源
  canvasData.data_resources.forEach(res => {
    if (!placedResources.has(res.resource_id)) {
      positions.set(res.resource_id, { x: resX, y: resY })
      resX += resWidth + horizontalGap / 2
    }
  })
  
  return positions
}

// 与实际画布完全一致的节点样式
const previewNodeStyles = {
  step: { headerBg: '#e6f4ff', headerColor: '#0958d9', typeLabel: '步骤' },
  impl: { headerBg: '#f6ffed', headerColor: '#237804', typeLabel: '实现' },
  data: { headerBg: '#fff7e6', headerColor: '#ad6800', typeLabel: '数据资源' },
}

// 创建与实际画布一致的节点卡片
const createNodeCard = (
  typeLabel: string,
  headerBg: string,
  headerColor: string,
  content: React.ReactNode
) => (
  <div style={{
    borderRadius: 14,
    background: '#ffffff',
    overflow: 'hidden',
    minWidth: 150,
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
  }}>
    <div style={{
      padding: '4px 8px',
      background: headerBg,
      color: headerColor,
      borderBottom: '1px solid #f0f0f0',
      fontWeight: 500,
      fontSize: 11,
    }}>
      {typeLabel}
    </div>
    <div style={{ padding: 10, fontSize: 12 }}>
      {content}
    </div>
  </div>
)

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
      const pos = positions.get(step.step_id) || { x: 0, y: 0 }
      const style = previewNodeStyles.step
      
      nodes.push({
        id: step.step_id,
        type: 'default',
        position: pos,
        data: { 
          label: createNodeCard(style.typeLabel, style.headerBg, style.headerColor, (
            <>
              <div style={{ fontWeight: 500, fontSize: 13, color: '#262626', lineHeight: '18px' }}>
                {step.name}
              </div>
              {step.description && (
                <div style={{ fontSize: 11, color: '#8c8c8c', lineHeight: '16px', marginTop: 4 }}>
                  <span style={{ color: '#bfbfbf', marginRight: 4 }}>描述:</span>
                  {step.description}
                </div>
              )}
            </>
          ))
        },
        style: { background: 'transparent', border: 'none', padding: 0 },
      })
    })
    
    // 2. 实现节点
    canvasData.implementations.forEach((impl) => {
      const pos = positions.get(impl.impl_id) || { x: 0, y: 150 }
      const style = previewNodeStyles.impl
      
      nodes.push({
        id: impl.impl_id,
        type: 'default',
        position: pos,
        data: { 
          label: createNodeCard(style.typeLabel, style.headerBg, style.headerColor, (
            <>
              <div style={{ fontWeight: 500, fontSize: 13, color: '#262626', lineHeight: '18px' }}>
                {impl.name}
              </div>
              {impl.type && (
                <div style={{ fontSize: 11, lineHeight: '16px', marginTop: 4 }}>
                  <span style={{ color: '#bfbfbf', marginRight: 4 }}>类型:</span>
                  <span style={{ color: '#52c41a' }}>{impl.type}</span>
                </div>
              )}
              {impl.system && (
                <div style={{ fontSize: 11, color: '#8c8c8c', lineHeight: '16px' }}>
                  <span style={{ color: '#bfbfbf', marginRight: 4 }}>系统:</span>
                  {impl.system}
                </div>
              )}
            </>
          ))
        },
        style: { background: 'transparent', border: 'none', padding: 0 },
      })
    })
    
    // 3. 数据资源节点
    canvasData.data_resources.forEach((res) => {
      const pos = positions.get(res.resource_id) || { x: 0, y: 300 }
      const style = previewNodeStyles.data
      
      nodes.push({
        id: res.resource_id,
        type: 'default',
        position: pos,
        data: { 
          label: createNodeCard(style.typeLabel, style.headerBg, style.headerColor, (
            <>
              <div style={{ fontWeight: 500, fontSize: 13, color: '#262626', lineHeight: '18px' }}>
                {res.name}
              </div>
              {res.type && (
                <div style={{ fontSize: 11, lineHeight: '16px', marginTop: 4 }}>
                  <span style={{ color: '#bfbfbf', marginRight: 4 }}>类型:</span>
                  <span style={{ color: '#faad14' }}>{res.type}</span>
                </div>
              )}
              {res.description && (
                <div style={{ fontSize: 11, color: '#8c8c8c', lineHeight: '16px' }}>
                  <span style={{ color: '#bfbfbf', marginRight: 4 }}>描述:</span>
                  {res.description}
                </div>
              )}
            </>
          ))
        },
        style: { background: 'transparent', border: 'none', padding: 0 },
      })
    })
    
    // 4. 步骤之间的边
    canvasData.edges.forEach((edge, index) => {
      edges.push({
        id: `step-edge-${index}`,
        source: edge.from_step_id,
        target: edge.to_step_id,
        label: edge.label || edge.condition,
        type: 'smoothstep',
        style: { stroke: '#91d5ff', strokeWidth: 2 },
      })
    })
    
    // 5. 步骤-实现关联边（虚线）
    canvasData.step_impl_links.forEach((link, index) => {
      edges.push({
        id: `step-impl-${index}`,
        source: link.step_id,
        target: link.impl_id,
        type: 'smoothstep',
        style: { stroke: '#b7eb8f', strokeWidth: 1, strokeDasharray: '4 2' },
      })
    })
    
    // 6. 实现-数据资源关联边（虚线）
    canvasData.impl_data_links.forEach((link, index) => {
      edges.push({
        id: `impl-data-${index}`,
        source: link.impl_id,
        target: link.resource_id,
        type: 'smoothstep',
        style: { stroke: '#ffd591', strokeWidth: 1, strokeDasharray: '4 2' },
      })
    })
    
    return { nodes, edges }
  }, [canvasData])
  
  return (
    <div>
      {/* 流程预览标题 */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 12,
      }}>
        <div>
          <Text strong style={{ fontSize: 16 }}>{canvasData.process.name}</Text>
          {canvasData.process.channel && (
            <span style={{
              marginLeft: 8,
              padding: '2px 8px',
              background: '#f0f0f0',
              borderRadius: 4,
              fontSize: 12,
              color: '#666',
            }}>
              {canvasData.process.channel}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 16, fontSize: 13, color: '#8c8c8c' }}>
          <span><Text strong>{canvasData.steps.length}</Text> 步骤</span>
          <span><Text strong>{canvasData.implementations.length}</Text> 实现</span>
          <span><Text strong>{canvasData.data_resources.length}</Text> 数据资源</span>
        </div>
      </div>
      
      {/* 流程图预览 */}
      <div
        style={{
          height: 320,
          border: '1px solid #e8e8e8',
          borderRadius: 12,
          marginBottom: 16,
          background: '#fafafa',
          overflow: 'hidden',
        }}
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          minZoom={0.3}
          maxZoom={1.5}
        >
          <Background color="#e8e8e8" gap={16} />
          <Controls showInteractive={false} position="bottom-right" />
        </ReactFlow>
      </div>
      
      {/* 详细列表 - 使用更紧凑的布局 */}
      <Collapse
        ghost
        size="small"
        items={[
          {
            key: 'steps',
            label: (
              <span style={{ fontSize: 13 }}>
                📋 步骤详情 ({canvasData.steps.length})
              </span>
            ),
            children: (
              <div style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(2, 1fr)', 
                gap: 8,
                padding: '4px 0',
              }}>
                {canvasData.steps.map((step, i) => (
                  <div 
                    key={step.step_id} 
                    style={{ 
                      padding: '6px 10px',
                      background: previewNodeStyles.step.headerBg,
                      borderRadius: 6,
                      fontSize: 12,
                    }}
                  >
                    <div style={{ fontWeight: 500, color: previewNodeStyles.step.headerColor }}>{i + 1}. {step.name}</div>
                    <div style={{ color: '#8c8c8c', fontSize: 11 }}>{step.step_type}</div>
                  </div>
                ))}
              </div>
            ),
          },
          {
            key: 'implementations',
            label: (
              <span style={{ fontSize: 13 }}>
                ⚙️ 实现列表 ({canvasData.implementations.length})
              </span>
            ),
            children: (
              <div style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(2, 1fr)', 
                gap: 8,
                padding: '4px 0',
              }}>
                {canvasData.implementations.map((impl) => (
                  <div 
                    key={impl.impl_id} 
                    style={{ 
                      padding: '6px 10px',
                      background: previewNodeStyles.impl.headerBg,
                      borderRadius: 6,
                      fontSize: 12,
                    }}
                  >
                    <div style={{ fontWeight: 500, color: previewNodeStyles.impl.headerColor }}>{impl.name}</div>
                    <div style={{ color: '#8c8c8c', fontSize: 11 }}>
                      {impl.system} · {impl.type}
                    </div>
                  </div>
                ))}
              </div>
            ),
          },
          {
            key: 'resources',
            label: (
              <span style={{ fontSize: 13 }}>
                🗃️ 数据资源 ({canvasData.data_resources.length})
              </span>
            ),
            children: (
              <div style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(2, 1fr)', 
                gap: 8,
                padding: '4px 0',
              }}>
                {canvasData.data_resources.map((res) => (
                  <div 
                    key={res.resource_id} 
                    style={{ 
                      padding: '6px 10px',
                      background: previewNodeStyles.data.headerBg,
                      borderRadius: 6,
                      fontSize: 12,
                    }}
                  >
                    <div style={{ fontWeight: 500, color: previewNodeStyles.data.headerColor }}>{res.name}</div>
                    <div style={{ color: '#8c8c8c', fontSize: 11 }}>
                      {res.system} · {res.type}
                    </div>
                  </div>
                ))}
              </div>
            ),
          },
        ]}
      />
    </div>
  )
}

export default SkeletonGenerateModal

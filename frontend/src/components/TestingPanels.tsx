/**
 * 测试助手面板组件
 * 
 * 包含：
 * - LeftTaskPanel: 左侧任务看板
 * - RightTimelinePanel: 右侧时间线
 */

import React, { useState } from 'react'
import { Progress, Button, Tooltip, Modal } from 'antd'
import {
  CheckCircleOutlined,
  SyncOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  ForwardOutlined,
  PauseCircleOutlined,
  FileTextOutlined,
} from '@ant-design/icons'
import MarkdownPreview from '@uiw/react-markdown-preview'
import type { Task, Phase, PhaseId, TaskStatus, PhaseStatus } from '../hooks/useTestingTaskBoard'

// ==================== 样式 ====================

const panelStyles = {
  leftPanel: {
    width: 260,
    backgroundColor: '#fafafa',
    borderRight: '1px solid #f0f0f0',
    display: 'flex',
    flexDirection: 'column' as const,
    height: '100%',
  },
  rightPanel: {
    width: 280,
    backgroundColor: '#fafafa',
    borderLeft: '1px solid #f0f0f0',
    display: 'flex',
    flexDirection: 'column' as const,
    height: '100%',
  },
  panelHeader: {
    padding: '16px',
    borderBottom: '1px solid #f0f0f0',
    fontWeight: 600,
    fontSize: 14,
  },
  panelContent: {
    flex: 1,
    overflowY: 'auto' as const,
    padding: '12px',
  },
  panelFooter: {
    padding: '12px 16px',
    borderTop: '1px solid #f0f0f0',
    backgroundColor: '#fff',
  },
  taskItem: {
    padding: '10px 12px',
    marginBottom: 8,
    backgroundColor: '#fff',
    borderRadius: 8,
    border: '1px solid #f0f0f0',
  },
  taskTitle: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    fontSize: 13,
  },
  taskResult: {
    marginTop: 4,
    marginLeft: 22,
    fontSize: 12,
    color: '#8c8c8c',
  },
  phaseCard: {
    padding: '12px',
    marginBottom: 12,
    backgroundColor: '#fff',
    borderRadius: 8,
    border: '1px solid #f0f0f0',
  },
  phaseHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  phaseName: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    fontWeight: 500,
    fontSize: 14,
  },
  phaseStatus: {
    fontSize: 12,
    color: '#8c8c8c',
  },
  connector: {
    display: 'flex',
    justifyContent: 'center',
    padding: '4px 0',
  },
  connectorLine: {
    width: 2,
    height: 20,
    backgroundColor: '#d9d9d9',
  },
}

// ==================== 工具函数 ====================

/** 获取任务状态图标 */
const getTaskStatusIcon = (status: TaskStatus) => {
  switch (status) {
    case 'completed':
      return <CheckCircleOutlined style={{ color: '#52c41a' }} />
    case 'in_progress':
      return <SyncOutlined spin style={{ color: '#1890ff' }} />
    case 'failed':
      return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
    case 'skipped':
      return <ForwardOutlined style={{ color: '#8c8c8c' }} />
    default:
      return <ClockCircleOutlined style={{ color: '#d9d9d9' }} />
  }
}

/** 获取阶段状态图标 */
const getPhaseStatusIcon = (status: PhaseStatus) => {
  switch (status) {
    case 'completed':
      return <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 18 }} />
    case 'in_progress':
      return <SyncOutlined spin style={{ color: '#1890ff', fontSize: 18 }} />
    case 'failed':
      return <CloseCircleOutlined style={{ color: '#ff4d4f', fontSize: 18 }} />
    default:
      return <PauseCircleOutlined style={{ color: '#d9d9d9', fontSize: 18 }} />
  }
}

/** 获取阶段状态文本 */
const getPhaseStatusText = (status: PhaseStatus, progress: number, tasksCompleted: number, tasksTotal: number) => {
  switch (status) {
    case 'completed':
      return '已完成'
    case 'in_progress':
      return tasksTotal > 0 ? `${tasksCompleted}/${tasksTotal} 任务` : `${progress}%`
    case 'failed':
      return '失败'
    default:
      return '待执行'
  }
}

/** 获取阶段序号 */
const getPhaseNumber = (phaseId: PhaseId) => {
  switch (phaseId) {
    case 'analysis': return '①'
    case 'plan': return '②'
    case 'generate': return '③'
  }
}

// ==================== 组件定义 ====================

interface LeftTaskPanelProps {
  tasks: Task[]
  currentPhase: PhaseId
  currentPhaseInfo?: Phase
  phaseSummary?: string  // 当前阶段的摘要内容
  onPause?: () => void
  onSkip?: () => void
}

/** 左侧任务看板 */
export const LeftTaskPanel: React.FC<LeftTaskPanelProps> = ({
  tasks,
  currentPhase,
  currentPhaseInfo,
  phaseSummary,
  onPause,
  onSkip,
}) => {
  const [summaryModalVisible, setSummaryModalVisible] = useState(false)
  
  const phaseName = currentPhaseInfo?.name || '需求分析'
  const phaseIndex = currentPhase === 'analysis' ? 1 : currentPhase === 'plan' ? 2 : 3
  const completedCount = tasks.filter(t => t.status === 'completed').length
  const totalCount = tasks.length
  
  // 格式化摘要内容显示
  const formatSummaryContent = (content: string) => {
    try {
      const parsed = JSON.parse(content)
      return '```json\n' + JSON.stringify(parsed, null, 2) + '\n```'
    } catch {
      return content
    }
  }

  return (
    <div style={panelStyles.leftPanel}>
      {/* 头部 */}
      <div style={panelStyles.panelHeader}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>📋</span>
          <span>任务追踪看板</span>
        </div>
        <div style={{ fontSize: 12, color: '#8c8c8c', marginTop: 4 }}>
          阶段: {phaseName} ({phaseIndex}/3)
        </div>
      </div>

      {/* 任务列表 */}
      <div style={panelStyles.panelContent}>
        {tasks.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#8c8c8c', padding: 20 }}>
            等待任务创建...
          </div>
        ) : (
          tasks.map((task, index) => (
            <div key={task.id} style={panelStyles.taskItem}>
              <div style={panelStyles.taskTitle}>
                {getTaskStatusIcon(task.status)}
                <span>{index + 1}. {task.title}</span>
              </div>
              {task.status === 'in_progress' && task.progress > 0 && (
                <div style={{ marginTop: 8, marginLeft: 22 }}>
                  <Progress 
                    percent={task.progress} 
                    size="small" 
                    strokeColor="#1890ff"
                    showInfo={false}
                  />
                </div>
              )}
              {task.status === 'completed' && task.result && (
                <div style={panelStyles.taskResult}>
                  └─ {task.result}
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* 底部 */}
      <div style={panelStyles.panelFooter}>
        <div style={{ marginBottom: 8, fontSize: 12, color: '#8c8c8c' }}>
          进度: {completedCount}/{totalCount} 完成
        </div>
        <Progress 
          percent={totalCount > 0 ? Math.round(completedCount / totalCount * 100) : 0} 
          size="small"
          strokeColor="#1890ff"
        />
        {/* 查看阶段总结按钮 */}
        {phaseSummary && (
          <Button 
            block
            type="default"
            icon={<FileTextOutlined />}
            onClick={() => setSummaryModalVisible(true)}
            style={{ marginTop: 12 }}
          >
            查看阶段总结
          </Button>
        )}
        {(onPause || onSkip) && (
          <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
            {onPause && (
              <Button size="small" onClick={onPause}>暂停</Button>
            )}
            {onSkip && (
              <Button size="small" onClick={onSkip}>跳过当前</Button>
            )}
          </div>
        )}
      </div>
      
      {/* 阶段总结弹窗 */}
      <Modal
        title={`${phaseName}总结`}
        open={summaryModalVisible}
        onCancel={() => setSummaryModalVisible(false)}
        footer={null}
        width={700}
        styles={{ body: { maxHeight: '60vh', overflowY: 'auto' } }}
      >
        {phaseSummary && (
          <MarkdownPreview
            source={formatSummaryContent(phaseSummary)}
            style={{ background: 'transparent', fontSize: 14 }}
            wrapperElement={{ "data-color-mode": "light" }}
          />
        )}
      </Modal>
    </div>
  )
}

interface RightTimelinePanelProps {
  phases: Phase[]
  currentPhase: PhaseId
  totalProgress: number
  onPauseWorkflow?: () => void
}

/** 右侧时间线面板 */
export const RightTimelinePanel: React.FC<RightTimelinePanelProps> = ({
  phases,
  currentPhase,
  totalProgress,
  onPauseWorkflow,
}) => {
  return (
    <div style={panelStyles.rightPanel}>
      {/* 头部 */}
      <div style={panelStyles.panelHeader}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>🕐</span>
          <span>工作流时间线</span>
        </div>
      </div>

      {/* 时间线 */}
      <div style={panelStyles.panelContent}>
        {phases.map((phase, index) => (
          <React.Fragment key={phase.id}>
            <div 
              style={{
                ...panelStyles.phaseCard,
                borderColor: phase.id === currentPhase ? '#1890ff' : '#f0f0f0',
                borderWidth: phase.id === currentPhase ? 2 : 1,
              }}
            >
              <div style={panelStyles.phaseHeader}>
                <div style={panelStyles.phaseName}>
                  {getPhaseNumber(phase.id)}
                  <span>{phase.name}</span>
                </div>
                {getPhaseStatusIcon(phase.status)}
              </div>
              
              <div style={panelStyles.phaseStatus}>
                {getPhaseStatusText(phase.status, phase.progress, phase.tasksCompleted, phase.tasksTotal)}
              </div>
              
              {phase.status === 'in_progress' && (
                <Progress 
                  percent={phase.progress} 
                  size="small" 
                  strokeColor="#1890ff"
                  style={{ marginTop: 8 }}
                />
              )}
            </div>
            
            {/* 连接线 */}
            {index < phases.length - 1 && (
              <div style={panelStyles.connector}>
                <div style={{
                  ...panelStyles.connectorLine,
                  backgroundColor: phase.status === 'completed' ? '#52c41a' : '#d9d9d9',
                }} />
              </div>
            )}
          </React.Fragment>
        ))}
      </div>

      {/* 底部 */}
      <div style={panelStyles.panelFooter}>
        <div style={{ marginBottom: 8, fontSize: 12 }}>
          <span style={{ color: '#8c8c8c' }}>总进度: </span>
          <span style={{ fontWeight: 500 }}>{phases.filter(p => p.status === 'completed').length}/3 阶段</span>
        </div>
        <Progress 
          percent={Math.round(totalProgress)} 
          strokeColor={{
            '0%': '#1890ff',
            '100%': '#52c41a',
          }}
        />
        {onPauseWorkflow && (
          <Button 
            block 
            style={{ marginTop: 12 }} 
            onClick={onPauseWorkflow}
          >
            暂停工作流
          </Button>
        )}
      </div>
    </div>
  )
}

// ==================== 默认导出 ====================

export default {
  LeftTaskPanel,
  RightTimelinePanel,
}

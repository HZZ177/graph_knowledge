/**
 * 测试助手阶段 Tab 组件
 * 
 * 提供三个阶段的 Tab 导航，每个阶段独立管理对话和任务面板。
 */

import React, { useState, useEffect, useCallback } from 'react'
import { Tabs, Badge, Tooltip, Modal, message } from 'antd'
import { 
  FileSearchOutlined, 
  FileTextOutlined, 
  CheckSquareOutlined,
  LockOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons'
import { 
  fetchTestingSessionStatus, 
  clearSubsequentPhases,
  TestingSessionStatus,
  TestingPhaseStatus 
} from '../api/llm'

export type PhaseId = 'analysis' | 'plan' | 'generate'

export interface PhaseConfig {
  id: PhaseId
  name: string
  icon: React.ReactNode
  description: string
}

export const PHASE_CONFIGS: PhaseConfig[] = [
  {
    id: 'analysis',
    name: '需求分析',
    icon: <FileSearchOutlined />,
    description: '分析需求文档，提取测试要点',
  },
  {
    id: 'plan',
    name: '测试方案',
    icon: <FileTextOutlined />,
    description: '制定测试策略和场景',
  },
  {
    id: 'generate',
    name: '用例生成',
    icon: <CheckSquareOutlined />,
    description: '生成详细的测试用例',
  },
]

export interface TestingPhaseTabsProps {
  /** 任务 session_id */
  sessionId: string
  /** 当前选中的阶段 */
  activePhase: PhaseId
  /** 阶段切换回调 */
  onPhaseChange: (phase: PhaseId) => void
  /** 阶段状态（从外部传入，避免重复请求） */
  phaseStatuses?: TestingSessionStatus['phases']
  /** 刷新状态回调 */
  onRefreshStatus?: () => void
}

export const TestingPhaseTabs: React.FC<TestingPhaseTabsProps> = ({
  sessionId,
  activePhase,
  onPhaseChange,
  phaseStatuses,
  onRefreshStatus,
}) => {
  // 检查阶段是否锁定（analysis 永远不锁定）
  const isPhaseUnlocked = useCallback((phaseId: PhaseId) => {
    if (phaseId === 'analysis') return true  // 第一阶段永远解锁
    if (!phaseStatuses) return true  // 没有状态信息时允许切换
    const status = phaseStatuses[phaseId]
    return !status || status.unlocked  // 没有状态或已解锁
  }, [phaseStatuses])
  
  const handleTabChange = useCallback(async (key: string) => {
    const targetPhase = key as PhaseId
    
    // 检查目标阶段是否已解锁
    if (!isPhaseUnlocked(targetPhase)) {
      message.warning('请先完成前序阶段（保存分析摘要后解锁）')
      return
    }
    
    // 检查是否需要警告用户
    const currentIndex = PHASE_CONFIGS.findIndex(p => p.id === activePhase)
    const targetIndex = PHASE_CONFIGS.findIndex(p => p.id === targetPhase)
    
    // 如果切换到前序阶段，且后续阶段有内容，显示警告
    if (targetIndex < currentIndex && phaseStatuses) {
      const hasSubsequentContent = PHASE_CONFIGS.slice(targetIndex + 1).some(
        p => phaseStatuses[p.id]?.has_summary
      )
      
      if (hasSubsequentContent) {
        Modal.confirm({
          title: '修改前序阶段',
          content: '修改此阶段可能需要重新生成后续阶段的内容。确定要切换吗？',
          okText: '切换',
          cancelText: '取消',
          onOk: () => {
            onPhaseChange(targetPhase)
          },
        })
        return
      }
    }
    
    onPhaseChange(targetPhase)
  }, [activePhase, phaseStatuses, onPhaseChange, isPhaseUnlocked])

  const renderTabLabel = useCallback((config: PhaseConfig) => {
    const isLocked = !isPhaseUnlocked(config.id)
    const hasContent = phaseStatuses?.[config.id]?.has_summary
    
    return (
      <Tooltip title={isLocked ? '请先完成前序阶段' : config.description}>
        <span className="testing-phase-tab">
          {isLocked ? <LockOutlined /> : config.icon}
          <span style={{ marginLeft: 8 }}>{config.name}</span>
          {hasContent && (
            <CheckCircleOutlined 
              style={{ marginLeft: 8, color: '#52c41a' }} 
            />
          )}
        </span>
      </Tooltip>
    )
  }, [phaseStatuses, isPhaseUnlocked])

  const items = PHASE_CONFIGS.map(config => {
    const isLocked = !isPhaseUnlocked(config.id)
    
    return {
      key: config.id,
      label: renderTabLabel(config),
      disabled: isLocked,
    }
  })

  return (
    <div className="testing-phase-tabs">
      <Tabs
        activeKey={activePhase}
        onChange={handleTabChange}
        items={items}
        size="small"
        tabBarStyle={{ 
          marginBottom: 0,
          borderBottom: '1px solid #f0f0f0',
          padding: '0 16px',
        }}
      />
    </div>
  )
}

export default TestingPhaseTabs

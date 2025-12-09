/**
 * 智能测试任务面板组件
 */

import React, { useState } from 'react'
import { Modal } from 'antd'
import MarkdownPreview from '@uiw/react-markdown-preview'
import {
  CheckCircleOutlined,
  LoadingOutlined,
  FileTextOutlined,
} from '@ant-design/icons'
import { PhaseId, Task, Phase } from '../../hooks/useTestingTaskBoard'
import { getTestingResults, TestingResults } from '../../api/testing'
import { showWarning } from '../../utils/message'
import { DisplayMessage } from '../../types/chat'
import { fetchConversationHistory } from '../../api/llm'
import { convertRawMessagesToDisplay } from '../../utils/chatUtils'

interface TestingTaskPanelProps {
  testingSessionId: string | null
  testingActivePhase: PhaseId
  setTestingActivePhase: (phase: PhaseId) => void
  testingPhases: Phase[]
  testingCurrentPhase: PhaseId
  testingViewingPhase: PhaseId
  setTestingViewingPhase: (phase: PhaseId) => void
  testingTasks: Task[]
  isTestingRunning: boolean
  testingViewingPhaseInfo: Phase | undefined
  isLoading: boolean
  messages: DisplayMessage[]
  setMessages: (messages: DisplayMessage[]) => void
  setCurrentTool: (tool: string | null) => void
  phaseMessagesRef: React.MutableRefObject<Map<PhaseId, DisplayMessage[]>>
}

export const TestingTaskPanel: React.FC<TestingTaskPanelProps> = ({
  testingSessionId,
  testingActivePhase,
  setTestingActivePhase,
  testingPhases,
  testingCurrentPhase,
  testingViewingPhase,
  setTestingViewingPhase,
  testingTasks,
  isTestingRunning,
  testingViewingPhaseInfo,
  isLoading,
  messages,
  setMessages,
  setCurrentTool,
  phaseMessagesRef,
}) => {
  // 阶段总结弹窗状态
  const [summaryModalVisible, setSummaryModalVisible] = useState(false)
  const [summaryContent, setSummaryContent] = useState<string>('')
  const [summaryLoading, setSummaryLoading] = useState(false)

  return (
    <div className="testing-task-panel">
      <div className="testing-panel-header">
        <span className="testing-panel-header-icon">📋</span>
        任务追踪看板
      </div>
      
      {/* 阶段选择器 - 点击切换阶段和对话 */}
      <div className="testing-phase-tabs">
        {testingPhases.map((phase) => {
          const isActive = testingActivePhase === phase.id
          const isCurrent = testingCurrentPhase === phase.id
          const isCompleted = phase.status === 'completed'
          return (
            <div 
              key={phase.id}
              className={`testing-phase-tab ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''} ${isCurrent && isTestingRunning ? 'running' : ''}`}
              onClick={async () => {
                // 如果正在生成中，禁止切换阶段
                if (isLoading) {
                  showWarning('AI 正在生成中，请等待完成后再切换阶段')
                  return
                }
                
                // 保存当前阶段的消息到缓存
                phaseMessagesRef.current.set(testingActivePhase, [...messages])
                
                // 切换活跃阶段
                setTestingActivePhase(phase.id as PhaseId)
                setTestingViewingPhase(phase.id)
                setCurrentTool(null)
                
                // 尝试从缓存加载目标阶段的消息
                const cachedMessages = phaseMessagesRef.current.get(phase.id as PhaseId)
                console.log('[Testing] 切换阶段:', phase.id, '缓存消息数:', cachedMessages?.length || 0)
                if (cachedMessages && cachedMessages.length > 0) {
                  setMessages(cachedMessages)
                } else if (testingSessionId) {
                  // 缓存为空时，从服务器加载历史
                  setMessages([])
                  try {
                    const phaseThreadId = `${testingSessionId}_${phase.id}`
                    const rawMessages = await fetchConversationHistory(phaseThreadId)
                    if (rawMessages.length > 0) {
                      const result = convertRawMessagesToDisplay(rawMessages, phaseThreadId)
                      setMessages(result.messages)
                      phaseMessagesRef.current.set(phase.id as PhaseId, result.messages)
                    }
                  } catch (e) {
                    console.log('该阶段暂无历史消息')
                  }
                } else {
                  setMessages([])
                }
              }}
              title={`切换到${phase.name}`}
            >
              {isCompleted && <CheckCircleOutlined className="phase-tab-icon" style={{ color: '#52c41a' }} />}
              {isCurrent && isTestingRunning && <LoadingOutlined spin className="phase-tab-icon" />}
              <span className="phase-tab-name">{phase.name}</span>
            </div>
          )
        })}
      </div>
      
      {/* 当前查看阶段的任务列表 */}
      <div className="testing-panel-content">
        {testingTasks.length === 0 ? (
          <div className="testing-empty-state">
            {isTestingRunning && testingViewingPhase === testingCurrentPhase 
              ? '等待任务创建...' 
              : testingViewingPhase !== testingCurrentPhase
                ? '该阶段暂无任务记录'
                : '选择需求后发送消息开始'}
          </div>
        ) : (
          testingTasks.map((task, index) => (
            <div 
              key={task.id} 
              className={`testing-task-card ${task.status === 'in_progress' ? 'active' : ''} ${task.status === 'completed' ? 'completed' : ''}`}
            >
              <div className="testing-task-title">
                <span className="task-icon">
                  {task.status === 'completed' ? (
                    <CheckCircleOutlined style={{ color: '#52c41a' }} />
                  ) : task.status === 'in_progress' ? (
                    <LoadingOutlined spin />
                  ) : '○'}
                </span>
                <span>{index + 1}. {task.title}</span>
              </div>
              {task.status === 'in_progress' && task.progress > 0 && (
                <div className="testing-task-progress">
                  <div className="testing-task-progress-bar">
                    <div className="testing-task-progress-fill" style={{ width: `${task.progress}%` }} />
                  </div>
                </div>
              )}
              {task.status === 'completed' && task.result && (
                <div className="testing-task-result">{task.result}</div>
              )}
            </div>
          ))
        )}
      </div>
      
      <div className="testing-panel-footer">
        <div className="testing-progress-summary">
          <span className="label">{testingViewingPhaseInfo?.name || '进度'}: </span>
          <span className="value">{testingTasks.filter(t => t.status === 'completed').length}/{testingTasks.length} 完成</span>
        </div>
        <div style={{ height: 6, background: '#f0f0f0', borderRadius: 3 }}>
          <div style={{ 
            height: '100%', 
            width: `${testingTasks.length > 0 ? Math.round(testingTasks.filter(t => t.status === 'completed').length / testingTasks.length * 100) : 0}%`, 
            background: '#1890ff', 
            borderRadius: 3, 
            transition: 'width 0.3s' 
          }} />
        </div>
        {/* 查看阶段总结按钮 - 当阶段完成时显示 */}
        {testingViewingPhaseInfo?.status === 'completed' && testingSessionId && (
          <button 
            className="testing-summary-btn"
            disabled={summaryLoading}
            onClick={async () => {
              try {
                setSummaryLoading(true)
                const results = await getTestingResults(testingSessionId!)
                // 根据当前查看的阶段获取对应摘要
                const summaryMap: Record<PhaseId, keyof TestingResults> = {
                  analysis: 'requirement_summary',
                  plan: 'test_plan',
                  generate: 'test_cases',
                }
                const summaryKey = summaryMap[testingViewingPhase]
                const content = results[summaryKey]
                if (content) {
                  setSummaryContent(JSON.stringify(content, null, 2))
                  setSummaryModalVisible(true)
                } else {
                  showWarning('暂无该阶段的总结数据')
                }
              } catch (error) {
                console.error('获取阶段总结失败:', error)
                showWarning('获取阶段总结失败')
              } finally {
                setSummaryLoading(false)
              }
            }}
          >
            {summaryLoading ? <LoadingOutlined /> : <FileTextOutlined />} 查看阶段总结
          </button>
        )}
      </div>
      
      {/* 阶段总结弹窗 */}
      <Modal
        title={`${testingViewingPhaseInfo?.name || '阶段'}总结`}
        open={summaryModalVisible}
        onCancel={() => setSummaryModalVisible(false)}
        footer={null}
        width={700}
        styles={{ body: { maxHeight: '60vh', overflowY: 'auto' } }}
      >
        {summaryContent && (
          <MarkdownPreview
            source={'```json\n' + summaryContent + '\n```'}
            style={{ background: 'transparent', fontSize: 14 }}
            wrapperElement={{ "data-color-mode": "light" }}
          />
        )}
      </Modal>
    </div>
  )
}

export default TestingTaskPanel

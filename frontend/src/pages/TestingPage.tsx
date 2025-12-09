/**
 * 智能测试助手页面
 * 
 * 独立的测试用例生成页面，包含：
 * - 需求配置区域（项目/迭代/需求选择）
 * - 左侧任务看板
 * - 中间聊天区域
 * - 右侧时间线
 */

import React, { useState, useEffect, useRef, useCallback } from 'react'
import { 
  Progress, 
  Button, 
  message as antMessage,
  Select,
  Spin,
} from 'antd'
import {
  CheckCircleOutlined,
  SyncOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
  DownloadOutlined,
  LeftOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import MarkdownPreview from '@uiw/react-markdown-preview'
import { fetchProjects, fetchIterations, fetchIssues, ProjectInfo, IterationInfo, IssueInfo } from '../api/coding'
import { createTestingSession, createTestingWSClient, TestingWSConfig, getTestingResults } from '../api/testing'
import { useTestingTaskBoard, Task, Phase, PhaseId, TaskStatus, PhaseStatus } from '../hooks/useTestingTaskBoard'
import '../styles/testing.css'
import '../styles/ChatPage.css'

// ==================== 类型定义 ====================

interface StreamMessage {
  role: 'assistant'
  content: string
  isStreaming: boolean
}

// ==================== 工具函数 ====================

const getTaskStatusIcon = (status: TaskStatus) => {
  switch (status) {
    case 'completed':
      return <CheckCircleOutlined style={{ color: '#52c41a' }} />
    case 'in_progress':
      return <SyncOutlined spin style={{ color: '#1890ff' }} />
    case 'failed':
      return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
    default:
      return <ClockCircleOutlined style={{ color: '#d9d9d9' }} />
  }
}

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

const getPhaseNumber = (phaseId: PhaseId, status: PhaseStatus) => {
  const num = phaseId === 'analysis' ? '1' : phaseId === 'plan' ? '2' : '3'
  let className = 'testing-phase-number'
  if (status === 'completed') className += ' completed'
  else if (status === 'pending') className += ' pending'
  return <span className={className}>{num}</span>
}

// ==================== 组件 ====================

const TestingPage: React.FC = () => {
  const navigate = useNavigate()
  
  // ===== 需求配置状态 =====
  const [projects, setProjects] = useState<ProjectInfo[]>([])
  const [iterations, setIterations] = useState<IterationInfo[]>([])
  const [issues, setIssues] = useState<IssueInfo[]>([])
  const [selectedProject, setSelectedProject] = useState<ProjectInfo | null>(null)
  const [selectedIteration, setSelectedIteration] = useState<IterationInfo | null>(null)
  const [selectedIssue, setSelectedIssue] = useState<IssueInfo | null>(null)
  const [isProjectLoading, setIsProjectLoading] = useState(false)
  const [isIterationLoading, setIsIterationLoading] = useState(false)
  const [isIssueLoading, setIsIssueLoading] = useState(false)
  
  // ===== 工作流状态 =====
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [streamContent, setStreamContent] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const wsClientRef = useRef<{ close: () => void } | null>(null)
  
  // ===== 任务看板 Hook =====
  const {
    tasks,
    phases,
    currentPhase,
    isRunning,
    handleMessage,
    reset,
    totalProgress,
    currentPhaseInfo,
  } = useTestingTaskBoard()
  
  // ===== 消息区域引用 =====
  const messageEndRef = useRef<HTMLDivElement>(null)
  
  // ===== 初始化加载项目列表 =====
  useEffect(() => {
    loadProjects()
  }, [])
  
  // ===== 自动滚动 =====
  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [streamContent])
  
  // ===== 数据加载函数 =====
  const loadProjects = async () => {
    setIsProjectLoading(true)
    try {
      const res = await fetchProjects(1, 50)
      setProjects(res.project_list || [])
    } catch (e) {
      antMessage.error('加载项目列表失败')
    } finally {
      setIsProjectLoading(false)
    }
  }
  
  const loadIterations = async (projectName: string) => {
    setIsIterationLoading(true)
    setIterations([])
    setSelectedIteration(null)
    setIssues([])
    setSelectedIssue(null)
    try {
      const res = await fetchIterations(projectName, 50, 0)
      setIterations(res.iterations || [])
    } catch (e) {
      antMessage.error('加载迭代列表失败')
    } finally {
      setIsIterationLoading(false)
    }
  }
  
  const loadIssues = async (projectName: string, iterationCode: number) => {
    setIsIssueLoading(true)
    setIssues([])
    setSelectedIssue(null)
    try {
      const res = await fetchIssues(projectName, iterationCode, 'REQUIREMENT', 50, 0)
      setIssues(res.issues || [])
    } catch (e) {
      antMessage.error('加载需求列表失败')
    } finally {
      setIsIssueLoading(false)
    }
  }
  
  // ===== 选择处理 =====
  const handleProjectChange = (projectName: string) => {
    const project = projects.find(p => p.name === projectName)
    setSelectedProject(project || null)
    if (project) {
      loadIterations(project.name)
    }
  }
  
  const handleIterationChange = (iterationCode: number) => {
    const iteration = iterations.find(i => i.code === iterationCode)
    setSelectedIteration(iteration || null)
    if (iteration && selectedProject) {
      loadIssues(selectedProject.name, iteration.code)
    }
  }
  
  const handleIssueChange = (issueCode: number) => {
    const issue = issues.find(i => i.code === issueCode)
    setSelectedIssue(issue || null)
  }
  
  // ===== 开始生成 =====
  const handleStart = async () => {
    if (!selectedProject || !selectedIssue) {
      antMessage.warning('请先选择项目和需求')
      return
    }
    
    setIsGenerating(true)
    setStreamContent('')
    reset()
    
    try {
      // 1. 创建会话
      const res = await createTestingSession({
        project_name: selectedProject.name,
        requirement_id: String(selectedIssue.code),
        requirement_name: selectedIssue.name,
      })
      
      const newSessionId = res.session_id
      setSessionId(newSessionId)
      
      // 2. 建立 WebSocket 连接
      const config: TestingWSConfig = {
        session_id: newSessionId,
        requirement_id: String(selectedIssue.code),
        project_name: selectedProject.name,
        requirement_name: selectedIssue.name,
      }
      
      const client = createTestingWSClient(config, {
        onStart: () => {
          handleMessage({ type: 'start' })
        },
        onStream: (content) => {
          setStreamContent(prev => prev + content)
        },
        onToolStart: (msg) => {
          handleMessage({ type: 'tool_start', ...msg } as any)
        },
        onToolEnd: (msg) => {
          handleMessage({ type: 'tool_end', ...msg } as any)
        },
        onPhaseChanged: (phase) => {
          handleMessage({ type: 'phase_changed', phase })
          // 阶段切换时清空流式内容，显示新阶段的输出
          setStreamContent('')
        },
        onResult: () => {
          handleMessage({ type: 'result' })
          setIsGenerating(false)
          antMessage.success('测试用例生成完成！')
        },
        onError: (error) => {
          handleMessage({ type: 'error', error })
          setIsGenerating(false)
          antMessage.error(`生成失败: ${error}`)
        },
        onClose: () => {
          setIsGenerating(false)
        },
      })
      
      wsClientRef.current = client
      client.connect()
      
    } catch (e: any) {
      setIsGenerating(false)
      antMessage.error(`启动失败: ${e.message}`)
    }
  }
  
  // ===== 停止生成 =====
  const handleStop = () => {
    if (wsClientRef.current) {
      wsClientRef.current.close()
      wsClientRef.current = null
    }
    setIsGenerating(false)
    antMessage.info('已停止生成')
  }
  
  // ===== 导出结果 =====
  const handleExport = async () => {
    if (!sessionId) return
    
    try {
      const results = await getTestingResults(sessionId)
      const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `test_cases_${sessionId.slice(0, 8)}.json`
      a.click()
      URL.revokeObjectURL(url)
      antMessage.success('导出成功')
    } catch (e) {
      antMessage.error('导出失败')
    }
  }
  
  // ===== 渲染 =====
  return (
    <div className="testing-layout">
      {/* 左侧任务看板 */}
      <div className="testing-left-panel">
        <div className="testing-panel-header">
          <span className="testing-panel-header-icon">📋</span>
          任务追踪看板
          <div className="testing-panel-subtitle">
            阶段: {currentPhaseInfo?.name || '待开始'} ({currentPhase === 'analysis' ? 1 : currentPhase === 'plan' ? 2 : 3}/3)
          </div>
        </div>
        
        <div className="testing-panel-content">
          {tasks.length === 0 ? (
            <div className="testing-empty-state">
              {isRunning ? '等待任务创建...' : '选择需求后点击开始'}
            </div>
          ) : (
            tasks.map((task, index) => (
              <div 
                key={task.id} 
                className={`testing-task-card ${task.status === 'in_progress' ? 'active' : ''} ${task.status === 'completed' ? 'completed' : ''}`}
              >
                <div className="testing-task-title">
                  {getTaskStatusIcon(task.status)}
                  <span>{index + 1}. {task.title}</span>
                </div>
                {task.status === 'in_progress' && task.progress > 0 && (
                  <div style={{ marginTop: 8, marginLeft: 22 }}>
                    <Progress percent={task.progress} size="small" strokeColor="#1890ff" showInfo={false} />
                  </div>
                )}
                {task.status === 'completed' && task.result && (
                  <div className="testing-task-result">└─ {task.result}</div>
                )}
              </div>
            ))
          )}
        </div>
        
        <div className="testing-panel-footer">
          <div className="testing-progress-summary">
            <span className="label">进度: </span>
            <span className="value">{tasks.filter(t => t.status === 'completed').length}/{tasks.length} 完成</span>
          </div>
          <Progress 
            percent={tasks.length > 0 ? Math.round(tasks.filter(t => t.status === 'completed').length / tasks.length * 100) : 0}
            size="small"
            strokeColor="#1890ff"
          />
        </div>
      </div>
      
      {/* 中间主区域 */}
      <div className="testing-main-area">
        {/* 顶部配置区 */}
        <div className="testing-config-area">
          <div className="testing-config-title">
            <Button 
              type="text" 
              icon={<LeftOutlined />} 
              onClick={() => navigate('/')}
              style={{ marginRight: 8 }}
            >
              返回
            </Button>
            🧪 智能测试助手
          </div>
          
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {/* 项目选择 */}
            <Select
              style={{ width: 200 }}
              placeholder="选择项目"
              loading={isProjectLoading}
              value={selectedProject?.name}
              onChange={handleProjectChange}
              disabled={isGenerating}
            >
              {projects.map(p => (
                <Select.Option key={p.name} value={p.name}>
                  {p.display_name}
                </Select.Option>
              ))}
            </Select>
            
            {/* 迭代选择 */}
            <Select
              style={{ width: 200 }}
              placeholder="选择迭代"
              loading={isIterationLoading}
              value={selectedIteration?.code}
              onChange={handleIterationChange}
              disabled={!selectedProject || isGenerating}
            >
              {iterations.map(i => (
                <Select.Option key={i.code} value={i.code}>
                  {i.name}
                </Select.Option>
              ))}
            </Select>
            
            {/* 需求选择 */}
            <Select
              style={{ width: 300 }}
              placeholder="选择需求"
              loading={isIssueLoading}
              value={selectedIssue?.code}
              onChange={handleIssueChange}
              disabled={!selectedIteration || isGenerating}
              showSearch
              filterOption={(input, option) =>
                (option?.children as unknown as string)?.toLowerCase().includes(input.toLowerCase())
              }
            >
              {issues.map(i => (
                <Select.Option key={i.code} value={i.code}>
                  #{i.code} {i.name}
                </Select.Option>
              ))}
            </Select>
            
            {/* 开始/停止按钮 */}
            {isGenerating ? (
              <Button 
                danger 
                icon={<PauseCircleOutlined />}
                onClick={handleStop}
              >
                停止
              </Button>
            ) : (
              <Button 
                type="primary" 
                icon={<PlayCircleOutlined />}
                onClick={handleStart}
                disabled={!selectedIssue}
              >
                开始生成
              </Button>
            )}
            
            {/* 导出按钮 */}
            {sessionId && !isGenerating && phases.some(p => p.status === 'completed') && (
              <Button 
                icon={<DownloadOutlined />}
                onClick={handleExport}
              >
                导出结果
              </Button>
            )}
          </div>
        </div>
        
        {/* 消息区域 */}
        <div className="chat-message-list" style={{ flex: 1 }}>
          <div className="chat-content-width">
            {!streamContent && !isGenerating ? (
              <div style={{ 
                textAlign: 'center', 
                padding: '60px 20px',
                color: '#8c8c8c',
              }}>
                <div style={{ fontSize: 48, marginBottom: 16 }}>🧪</div>
                <h2 style={{ color: '#333', marginBottom: 8 }}>智能测试助手</h2>
                <p>选择需求后点击「开始生成」，AI 将自动分析需求并生成测试用例</p>
                <div style={{ marginTop: 24, fontSize: 13 }}>
                  <div>1️⃣ 需求分析：深度理解需求文档和代码实现</div>
                  <div>2️⃣ 方案生成：制定测试范围和策略</div>
                  <div>3️⃣ 用例生成：生成结构化测试用例</div>
                </div>
              </div>
            ) : (
              <div className="message-item assistant" style={{ marginTop: 20 }}>
                <div className="message-content">
                  <div className="markdown-body">
                    <MarkdownPreview 
                      source={streamContent || '正在分析...'} 
                      style={{ background: 'transparent' }}
                    />
                    {isGenerating && (
                      <span className="typing-cursor" style={{ 
                        display: 'inline-block',
                        width: 8,
                        height: 18,
                        background: '#1890ff',
                        marginLeft: 2,
                        animation: 'blink 1s infinite',
                      }} />
                    )}
                  </div>
                </div>
              </div>
            )}
            <div ref={messageEndRef} />
          </div>
        </div>
      </div>
      
      {/* 右侧时间线 */}
      <div className="testing-right-panel">
        <div className="testing-panel-header">
          <span className="testing-panel-header-icon">🕐</span>
          工作流时间线
        </div>
        
        <div className="testing-panel-content">
          {phases.map((phase, index) => (
            <React.Fragment key={phase.id}>
              <div className={`testing-phase-card ${phase.id === currentPhase && isRunning ? 'active' : ''} ${phase.status === 'completed' ? 'completed' : ''}`}>
                <div className="testing-phase-header">
                  <div className="testing-phase-name">
                    {getPhaseNumber(phase.id, phase.status)}
                    <span>{phase.name}</span>
                  </div>
                  {getPhaseStatusIcon(phase.status)}
                </div>
                
                <div className="testing-phase-status">
                  {phase.status === 'completed' 
                    ? '已完成' 
                    : phase.status === 'in_progress'
                    ? (phase.tasksTotal > 0 ? `${phase.tasksCompleted}/${phase.tasksTotal} 任务` : `${phase.progress}%`)
                    : phase.status === 'failed'
                    ? '失败'
                    : '待执行'}
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
              
              {index < phases.length - 1 && (
                <div className="testing-connector">
                  <div className={`testing-connector-line ${phase.status === 'completed' ? 'completed' : ''}`} />
                </div>
              )}
            </React.Fragment>
          ))}
        </div>
        
        <div className="testing-panel-footer">
          <div className="testing-progress-summary">
            <span className="label">总进度: </span>
            <span className="value">{phases.filter(p => p.status === 'completed').length}/3 阶段</span>
          </div>
          <Progress 
            percent={Math.round(totalProgress)} 
            strokeColor={{
              '0%': '#1890ff',
              '100%': '#52c41a',
            }}
          />
        </div>
      </div>
    </div>
  )
}

export default TestingPage

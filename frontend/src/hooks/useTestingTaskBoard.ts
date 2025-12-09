/**
 * 测试助手任务看板 Hook
 * 
 * 管理测试助手的任务状态、阶段进度和时间线
 */

import { useState, useCallback } from 'react'

// ==================== 类型定义 ====================

/** 任务状态 */
export type TaskStatus = 'pending' | 'in_progress' | 'completed' | 'failed' | 'skipped'

/** 阶段状态 */
export type PhaseStatus = 'pending' | 'in_progress' | 'completed' | 'failed'

/** 阶段标识 */
export type PhaseId = 'analysis' | 'plan' | 'generate'

/** 阶段状态标识（包含 completed） */
export type PhaseStateId = PhaseId | 'completed'

/** 单个任务 */
export interface Task {
  id: string
  title: string
  scope?: string
  status: TaskStatus
  progress: number
  result?: string
}

/** 阶段信息 */
export interface Phase {
  id: PhaseId
  name: string
  status: PhaseStatus
  progress: number
  tasksCompleted: number
  tasksTotal: number
}

/** WebSocket 消息类型 */
export interface TestingWSMessage {
  type: 'tool_start' | 'tool_end' | 'phase_changed' | 'phase_completed' | 'stream' | 'result' | 'error' | 'start'
  tool_name?: string
  tool_id?: number
  tool_input?: Record<string, unknown>
  input_summary?: string
  output_summary?: string
  elapsed?: number
  batch_id?: number
  batch_size?: number
  batch_index?: number
  phase?: string
  content?: string
  session_id?: string
  status?: string
  error?: string
  summary_content?: string  // 阶段摘要内容（phase_completed 消息携带）
}

/** 阶段任务历史 */
export type PhaseTaskHistory = Record<PhaseId, Task[]>

/** 阶段摘要数据 */
export type PhaseSummaries = Record<PhaseId, string>

/** 阶段历史恢复数据 */
export interface PhasesHistoryData {
  analysis: { completed: boolean }
  plan: { completed: boolean }
  generate: { completed: boolean }
}

/** 任务历史数据（从后端返回） */
export interface TaskHistoryData {
  analysis: Task[]
  plan: Task[]
  generate: Task[]
}

/** Hook 返回值 */
export interface UseTestingTaskBoardReturn {
  // 状态
  tasks: Task[]                    // 当前查看阶段的任务
  phases: Phase[]
  currentPhase: PhaseId            // 当前执行中的阶段
  viewingPhase: PhaseId            // 当前查看的阶段
  isRunning: boolean
  taskHistory: PhaseTaskHistory    // 所有阶段的任务历史
  phaseSummaries: PhaseSummaries   // 各阶段摘要数据
  
  // 方法
  handleMessage: (msg: TestingWSMessage) => void
  reset: () => void
  restoreFromHistory: (phasesData: PhasesHistoryData, currentPhase: string | null, status: string | null, taskHistory?: TaskHistoryData, summaries?: PhaseSummaries) => void
  setViewingPhase: (phase: PhaseId) => void  // 切换查看的阶段
  setCurrentPhase: (phase: PhaseId) => void  // 设置当前执行阶段
  
  // 计算属性
  totalProgress: number
  currentPhaseInfo: Phase | undefined
  viewingPhaseInfo: Phase | undefined
}

// ==================== 初始状态 ====================

const initialPhases: Phase[] = [
  { id: 'analysis', name: '需求分析', status: 'pending', progress: 0, tasksCompleted: 0, tasksTotal: 0 },
  { id: 'plan', name: '方案生成', status: 'pending', progress: 0, tasksCompleted: 0, tasksTotal: 0 },
  { id: 'generate', name: '用例生成', status: 'pending', progress: 0, tasksCompleted: 0, tasksTotal: 0 },
]

// 需要特殊处理的测试工具名称
// NOTE: transition_phase 已删除，阶段切换由后端编排器控制，通过 phase_changed 消息通知
const TESTING_TOOLS = [
  'create_task_board',
  'update_task_status',
  'save_phase_summary',
  'get_phase_summary',
]

// ==================== Hook 实现 ====================

const initialTaskHistory: PhaseTaskHistory = {
  analysis: [],
  plan: [],
  generate: [],
}

const initialPhaseSummaries: PhaseSummaries = {
  analysis: '',
  plan: '',
  generate: '',
}

export function useTestingTaskBoard(): UseTestingTaskBoardReturn {
  const [taskHistory, setTaskHistory] = useState<PhaseTaskHistory>(initialTaskHistory)
  const [phases, setPhases] = useState<Phase[]>(initialPhases)
  const [currentPhase, setCurrentPhase] = useState<PhaseId>('analysis')
  const [viewingPhase, setViewingPhase] = useState<PhaseId>('analysis')
  const [isRunning, setIsRunning] = useState(false)
  const [phaseSummaries, setPhaseSummaries] = useState<PhaseSummaries>(initialPhaseSummaries)
  
  // 当前查看阶段的任务
  const tasks = taskHistory[viewingPhase]

  /**
   * 处理 WebSocket 消息
   */
  const handleMessage = useCallback((msg: TestingWSMessage) => {
    // 开始消息
    if (msg.type === 'start') {
      setIsRunning(true)
      // 使用消息中的 phase，或当前 viewingPhase，或默认 analysis
      const startPhase = (msg.phase as PhaseId) || viewingPhase || 'analysis'
      setCurrentPhase(startPhase)
      setPhases(prev => prev.map(p => 
        p.id === startPhase 
          ? { ...p, status: 'in_progress' as PhaseStatus }
          : p
      ))
      return
    }

    // 完成消息
    if (msg.type === 'result') {
      setIsRunning(false)
      return
    }

    // 错误消息
    if (msg.type === 'error') {
      setIsRunning(false)
      setPhases(prev => prev.map(p => 
        p.id === currentPhase 
          ? { ...p, status: 'failed' as PhaseStatus }
          : p
      ))
      return
    }

    // 阶段完成消息（由编排器发送，不依赖 AI 调用工具）
    if (msg.type === 'phase_completed' && msg.phase) {
      const completedPhase = msg.phase as PhaseId
      setPhases(prev => prev.map(p =>
        p.id === completedPhase
          ? { ...p, status: 'completed' as PhaseStatus, progress: 100 }
          : p
      ))
      // 保存阶段摘要内容
      if (msg.summary_content) {
        setPhaseSummaries(prev => ({
          ...prev,
          [completedPhase]: msg.summary_content!,
        }))
      }
      return
    }

    // 阶段切换消息（只负责设置新阶段为进行中）
    if (msg.type === 'phase_changed' && msg.phase) {
      const newPhase = msg.phase as PhaseStateId
      
      // 只有当新阶段不是 completed 时才更新为进行中
      if (newPhase !== 'completed') {
        setPhases(prev => prev.map(p =>
          p.id === newPhase
            ? { ...p, status: 'in_progress' as PhaseStatus }
            : p
        ))
      }
      
      // 只有当新阶段是有效的 PhaseId 时才切换
      if (newPhase === 'analysis' || newPhase === 'plan' || newPhase === 'generate') {
        setCurrentPhase(newPhase)
        setViewingPhase(newPhase) // 自动切换查看到新阶段
      }
      return
    }

    // 工具开始事件
    if (msg.type === 'tool_start' && msg.tool_name && TESTING_TOOLS.includes(msg.tool_name)) {
      const { tool_name, tool_input } = msg
      
      // 创建任务看板
      if (tool_name === 'create_task_board' && tool_input) {
        const phase = tool_input.phase as PhaseId
        const newTasks = (tool_input.tasks as Array<{ id: string; title: string; scope?: string }>) || []
        
        const formattedTasks: Task[] = newTasks.map(t => ({
          ...t,
          status: 'pending' as TaskStatus,
          progress: 0,
        }))
        
        setCurrentPhase(phase)
        setViewingPhase(phase) // 自动切换查看到当前阶段
        setTaskHistory(prev => ({
          ...prev,
          [phase]: formattedTasks,
        }))
        
        // 更新阶段任务数
        setPhases(prev => prev.map(p => 
          p.id === phase 
            ? { ...p, status: 'in_progress' as PhaseStatus, tasksTotal: newTasks.length }
            : p
        ))
      }
      
      // 更新任务状态（支持同时完成一个任务并开始另一个任务）
      // 新参数格式: { completed_task_id, started_task_id, result }
      if (tool_name === 'update_task_status' && tool_input) {
        const { completed_task_id, started_task_id, result } = tool_input as { 
          completed_task_id?: string
          started_task_id?: string
          result?: string
        }
        
        setTaskHistory(prev => {
          const newHistory = { ...prev }
          
          // 辅助函数：在所有阶段中查找并更新任务
          const updateTask = (taskId: string, updates: Partial<Task>) => {
            for (const phaseId of ['analysis', 'plan', 'generate'] as PhaseId[]) {
              const tasks = newHistory[phaseId]
              const taskIndex = tasks.findIndex((t: Task) => t.id === taskId)
              if (taskIndex !== -1) {
                newHistory[phaseId] = tasks.map((task: Task) =>
                  task.id === taskId ? { ...task, ...updates } : task
                )
                break
              }
            }
          }
          
          // 更新完成的任务
          if (completed_task_id) {
            updateTask(completed_task_id, { 
              status: 'completed' as TaskStatus, 
              progress: 100, 
              result: result || undefined 
            })
          }
          
          // 更新开始的任务
          if (started_task_id) {
            updateTask(started_task_id, { 
              status: 'in_progress' as TaskStatus, 
              progress: 0 
            })
          }
          
          return newHistory
        })
      }
    }

    // 工具结束事件
    if (msg.type === 'tool_end' && msg.tool_name && TESTING_TOOLS.includes(msg.tool_name)) {
      const { tool_name, tool_input } = msg
      
      // 任务状态更新完成 - 重新计算所有阶段进度
      if (tool_name === 'update_task_status') {
        setTaskHistory(prev => {
          // 重新计算所有阶段的进度
          setPhases(phases => phases.map(p => {
            const phaseTasks = prev[p.id as PhaseId] || []
            const completed = phaseTasks.filter((t: Task) => t.status === 'completed').length
            const total = phaseTasks.length
            return {
              ...p,
              tasksCompleted: completed,
              progress: total > 0 ? Math.round(completed / total * 100) : 0,
            }
          }))
          
          return prev
        })
      }
      
      // NOTE: 阶段完成现在由编排器发送 phase_completed 消息控制
      // 不再依赖 save_phase_summary 工具来标记阶段完成
    }
  }, [currentPhase, viewingPhase])

  /**
   * 重置状态
   */
  const reset = useCallback(() => {
    setTaskHistory(initialTaskHistory)
    setPhases(initialPhases)
    setCurrentPhase('analysis')
    setViewingPhase('analysis')
    setIsRunning(false)
    setPhaseSummaries(initialPhaseSummaries)
  }, [])

  /**
   * 从历史恢复状态（用于加载历史对话）
   */
  const restoreFromHistory = useCallback((phasesData: {
    analysis: { completed: boolean }
    plan: { completed: boolean }
    generate: { completed: boolean }
  }, currentPhaseValue: string | null, status: string | null, taskHistoryData?: TaskHistoryData, summaries?: PhaseSummaries) => {
    // 1. 恢复任务历史
    if (taskHistoryData) {
      setTaskHistory({
        analysis: taskHistoryData.analysis || [],
        plan: taskHistoryData.plan || [],
        generate: taskHistoryData.generate || [],
      })
    }
    
    // 2. 恢复阶段状态（基于摘要完成情况）
    setPhases(prev => prev.map(p => {
      const phaseData = phasesData[p.id as PhaseId]
      const phaseTasks = taskHistoryData?.[p.id as PhaseId] || []
      const tasksCompleted = phaseTasks.filter(t => t.status === 'completed').length
      const tasksTotal = phaseTasks.length
      
      if (phaseData?.completed) {
        // 阶段已完成（有摘要）
        return { 
          ...p, 
          status: 'completed' as PhaseStatus, 
          progress: 100,
          tasksCompleted,
          tasksTotal,
        }
      }
      // 阶段未完成，保持 pending 状态
      return { 
        ...p, 
        status: 'pending' as PhaseStatus,
        tasksCompleted,
        tasksTotal,
        progress: tasksTotal > 0 ? Math.round(tasksCompleted / tasksTotal * 100) : 0,
      }
    }))
    
    // 3. 设置当前查看阶段（优先显示最后一个有任务的阶段）
    let viewPhase: PhaseId = 'analysis'
    if (taskHistoryData?.generate?.length) {
      viewPhase = 'generate'
    } else if (taskHistoryData?.plan?.length) {
      viewPhase = 'plan'
    } else if (taskHistoryData?.analysis?.length) {
      viewPhase = 'analysis'
    }
    
    if (currentPhaseValue && ['analysis', 'plan', 'generate'].includes(currentPhaseValue)) {
      setCurrentPhase(currentPhaseValue as PhaseId)
    }
    setViewingPhase(viewPhase)
    
    // 4. 历史恢复时不设置 isRunning，避免显示 loading 状态
    setIsRunning(false)
    
    // 5. 恢复摘要数据
    if (summaries) {
      setPhaseSummaries(summaries)
    }
  }, [])

  // 计算总进度
  const totalProgress = phases.reduce((acc, p) => {
    const phaseWeight = 100 / phases.length
    return acc + (p.progress / 100) * phaseWeight
  }, 0)

  // 当前阶段信息
  const currentPhaseInfo = phases.find(p => p.id === currentPhase)
  
  // 当前查看阶段信息
  const viewingPhaseInfo = phases.find(p => p.id === viewingPhase)

  return {
    tasks,
    phases,
    currentPhase,
    viewingPhase,
    isRunning,
    taskHistory,
    phaseSummaries,
    handleMessage,
    setViewingPhase,
    setCurrentPhase,
    reset,
    restoreFromHistory,
    totalProgress,
    currentPhaseInfo,
    viewingPhaseInfo,
  }
}

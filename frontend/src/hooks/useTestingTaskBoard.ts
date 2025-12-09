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
  type: 'tool_start' | 'tool_end' | 'phase_changed' | 'stream' | 'result' | 'error' | 'start'
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
}

/** 阶段任务历史 */
export type PhaseTaskHistory = Record<PhaseId, Task[]>

/** Hook 返回值 */
export interface UseTestingTaskBoardReturn {
  // 状态
  tasks: Task[]                    // 当前查看阶段的任务
  phases: Phase[]
  currentPhase: PhaseId            // 当前执行中的阶段
  viewingPhase: PhaseId            // 当前查看的阶段
  isRunning: boolean
  taskHistory: PhaseTaskHistory    // 所有阶段的任务历史
  
  // 方法
  handleMessage: (msg: TestingWSMessage) => void
  reset: () => void
  setViewingPhase: (phase: PhaseId) => void  // 切换查看的阶段
  
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
const TESTING_TOOLS = [
  'create_task_board',
  'update_task_status',
  'transition_phase',
  'save_phase_summary',
  'get_phase_summary',
]

// ==================== Hook 实现 ====================

const initialTaskHistory: PhaseTaskHistory = {
  analysis: [],
  plan: [],
  generate: [],
}

export function useTestingTaskBoard(): UseTestingTaskBoardReturn {
  const [taskHistory, setTaskHistory] = useState<PhaseTaskHistory>(initialTaskHistory)
  const [phases, setPhases] = useState<Phase[]>(initialPhases)
  const [currentPhase, setCurrentPhase] = useState<PhaseId>('analysis')
  const [viewingPhase, setViewingPhase] = useState<PhaseId>('analysis')
  const [isRunning, setIsRunning] = useState(false)
  
  // 当前查看阶段的任务
  const tasks = taskHistory[viewingPhase]

  /**
   * 处理 WebSocket 消息
   */
  const handleMessage = useCallback((msg: TestingWSMessage) => {
    // 开始消息
    if (msg.type === 'start') {
      setIsRunning(true)
      setCurrentPhase('analysis')
      setPhases(prev => prev.map(p => 
        p.id === 'analysis' 
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

    // 阶段切换消息
    if (msg.type === 'phase_changed' && msg.phase) {
      const newPhase = msg.phase as PhaseStateId
      
      // 更新阶段状态
      setPhases(prev => prev.map(p => {
        if (p.id === currentPhase) {
          return { ...p, status: 'completed' as PhaseStatus, progress: 100 }
        }
        // 只有当新阶段不是 completed 且匹配当前阶段时才更新为进行中
        if (newPhase !== 'completed' && p.id === newPhase) {
          return { ...p, status: 'in_progress' as PhaseStatus }
        }
        return p
      }))
      
      // 只有当新阶段是有效的 PhaseId 时才切换
      if (newPhase === 'analysis' || newPhase === 'plan' || newPhase === 'generate') {
        setCurrentPhase(newPhase)
        setViewingPhase(newPhase) // 自动切换查看到新阶段
        // 注意：不再清空任务，历史会保留在 taskHistory 中
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
      
      // 更新任务状态（开始）
      if (tool_name === 'update_task_status' && tool_input) {
        const { task_id, status, progress } = tool_input as { 
          task_id: string
          status: TaskStatus
          progress?: number 
        }
        
        setTaskHistory(prev => ({
          ...prev,
          [currentPhase]: prev[currentPhase].map((task: Task) =>
            task.id === task_id
              ? { ...task, status, progress: progress || 0 }
              : task
          ),
        }))
      }
    }

    // 工具结束事件
    if (msg.type === 'tool_end' && msg.tool_name && TESTING_TOOLS.includes(msg.tool_name)) {
      const { tool_name } = msg
      
      // 任务状态更新完成 - 重新计算阶段进度
      if (tool_name === 'update_task_status') {
        setTaskHistory(prev => {
          const phaseTasks = prev[currentPhase]
          const completed = phaseTasks.filter((t: Task) => t.status === 'completed').length
          const total = phaseTasks.length
          
          setPhases(phases => phases.map(p =>
            p.id === currentPhase
              ? { 
                  ...p, 
                  tasksCompleted: completed, 
                  progress: total > 0 ? Math.round(completed / total * 100) : 0 
                }
              : p
          ))
          
          return prev
        })
      }
      
      // 阶段摘要保存完成 = 阶段结束
      if (tool_name === 'save_phase_summary') {
        setPhases(prev => prev.map(p =>
          p.id === currentPhase
            ? { ...p, status: 'completed' as PhaseStatus, progress: 100 }
            : p
        ))
      }
    }
  }, [currentPhase])

  /**
   * 重置状态
   */
  const reset = useCallback(() => {
    setTaskHistory(initialTaskHistory)
    setPhases(initialPhases)
    setCurrentPhase('analysis')
    setViewingPhase('analysis')
    setIsRunning(false)
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
    handleMessage,
    setViewingPhase,
    reset,
    totalProgress,
    currentPhaseInfo,
    viewingPhaseInfo,
  }
}

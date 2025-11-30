import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react'
import { listLLMModels, activateLLMModel, activateTaskModel, type AIModelOut } from '../api/llmModels'
import { showError, showSuccess } from '../utils/message'

interface ModelContextValue {
  models: AIModelOut[]
  activeModelId: number | null
  taskModelId: number | null
  loading: boolean
  activating: boolean
  activatingTask: boolean
  refreshModels: () => Promise<void>
  setActiveModel: (id: number) => Promise<void>
  setTaskModel: (id: number) => Promise<void>
}

const ModelContext = createContext<ModelContextValue | null>(null)

export const useModelContext = () => {
  const ctx = useContext(ModelContext)
  if (!ctx) {
    throw new Error('useModelContext must be used within ModelProvider')
  }
  return ctx
}

interface ModelProviderProps {
  children: ReactNode
}

export const ModelProvider: React.FC<ModelProviderProps> = ({ children }) => {
  const [models, setModels] = useState<AIModelOut[]>([])
  const [activeModelId, setActiveModelId] = useState<number | null>(null)
  const [taskModelId, setTaskModelId] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [activating, setActivating] = useState(false)
  const [activatingTask, setActivatingTask] = useState(false)

  const refreshModels = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listLLMModels()
      setModels(data)
      const active = data.find((m) => m.is_active)
      const taskActive = data.find((m) => m.is_task_active)
      setActiveModelId(active ? active.id : null)
      setTaskModelId(taskActive ? taskActive.id : null)
    } catch (e) {
      showError('加载模型列表失败')
    } finally {
      setLoading(false)
    }
  }, [])

  const setActiveModel = useCallback(async (id: number) => {
    try {
      setActivating(true)
      await activateLLMModel(id)
      showSuccess('已设置为主力模型')
      await refreshModels()
    } catch (e) {
      showError('激活模型失败')
    } finally {
      setActivating(false)
    }
  }, [refreshModels])

  const setTaskModel = useCallback(async (id: number) => {
    try {
      setActivatingTask(true)
      await activateTaskModel(id)
      showSuccess('已设置为快速模型')
      await refreshModels()
    } catch (e) {
      showError('激活模型失败')
    } finally {
      setActivatingTask(false)
    }
  }, [refreshModels])

  // 初始加载
  useEffect(() => {
    refreshModels()
  }, [refreshModels])

  return (
    <ModelContext.Provider
      value={{
        models,
        activeModelId,
        taskModelId,
        loading,
        activating,
        activatingTask,
        refreshModels,
        setActiveModel,
        setTaskModel,
      }}
    >
      {children}
    </ModelContext.Provider>
  )
}

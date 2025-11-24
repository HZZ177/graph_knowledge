import http from './http'

export interface AIModelBase {
  name: string
  provider?: string | null
  model_name: string
  base_url?: string | null
  temperature?: number
  max_tokens?: number | null
}

export interface AIModelCreate extends AIModelBase {
  api_key: string
}

export interface AIModelUpdate extends Partial<AIModelBase> {
  api_key?: string | null
}

export interface AIModelOut extends AIModelBase {
  id: number
  is_active: boolean
  updated_at: string
}

export interface TestLLMResult {
  ok: boolean
  result?: string
}

export async function listLLMModels(): Promise<AIModelOut[]> {
  const res = await http.get<AIModelOut[]>('/llm-models/list')
  return res.data
}

export async function createLLMModel(payload: AIModelCreate): Promise<AIModelOut> {
  const res = await http.post<AIModelOut>('/llm-models/create', payload)
  return res.data
}

export async function updateLLMModel(modelId: number, payload: AIModelUpdate): Promise<AIModelOut> {
  const res = await http.post<AIModelOut>('/llm-models/update', payload, {
    params: { model_id: modelId },
  })
  return res.data
}

export async function deleteLLMModel(modelId: number): Promise<void> {
  await http.post('/llm-models/delete', { model_id: modelId })
}

export async function activateLLMModel(modelId: number): Promise<void> {
  await http.post('/llm-models/activate', { id: modelId })
}

export async function testLLMModel(payload: AIModelCreate): Promise<TestLLMResult> {
  const res = await http.post<TestLLMResult>('/llm-models/test', payload)
  return res.data
}

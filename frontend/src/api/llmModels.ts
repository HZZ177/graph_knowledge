import http from './http'

export type ProviderType = 'litellm' | 'custom_gateway'

export interface AIModelBase {
  name: string
  provider_type: ProviderType
  provider?: string | null        // LiteLLM 模式下的提供商标识
  model_name: string
  base_url?: string | null        // LiteLLM 模式下的可选代理地址（一般不用）
  gateway_endpoint?: string | null // 自定义网关模式下的完整端点 URL
  temperature?: number
  max_tokens?: number | null
  timeout?: number
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

// 预设的 LiteLLM 支持的提供商列表
export const LITELLM_PROVIDERS = [
  { value: 'openrouter', label: 'OpenRouter' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'google', label: 'Google (Gemini)' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'mistral', label: 'Mistral' },
  { value: 'groq', label: 'Groq' },
  { value: 'cohere', label: 'Cohere' },
  { value: 'ollama', label: 'Ollama (本地)' },
] as const

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

export async function testSavedLLMModel(modelId: number): Promise<TestLLMResult> {
  const res = await http.post<TestLLMResult>('/llm-models/test-by-id', { model_id: modelId })
  return res.data
}

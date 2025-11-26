import http from './http'

export interface ChatRequest {
  question: string
  process_id?: string | null
}

export interface ChatResponse {
  answer: string
  process_id?: string | null
}

export async function askChat(payload: ChatRequest): Promise<ChatResponse> {
  const res = await http.post<ChatResponse>('/llm/chat/ask', payload)
  return res.data
}

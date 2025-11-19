import http from './http'

export interface ProcessItem {
  process_id: string
  name: string
}

export async function listProcesses(): Promise<ProcessItem[]> {
  const res = await http.get<ProcessItem[]>('/processes')
  return res.data
}

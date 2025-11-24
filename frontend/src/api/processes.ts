import http from './http'

export interface ProcessItem {
  process_id: string
  name: string
  channel?: string
  description?: string
  entrypoints?: string[]
}

export interface ProcessDetail extends ProcessItem {}

export interface ProcessStep {
  step_id: number
  process_id: string
  order_no: number
  name?: string
  capability_id?: string
}

export interface ProcessEdge {
  id: number
  from_step_id: string
  to_step_id: string
  edge_type?: string
  condition?: string
  label?: string
}

export async function listProcesses(): Promise<ProcessItem[]> {
  const res = await http.get<ProcessItem[]>('/processes/list_processes')
  return res.data
}

export async function getProcess(processId: string): Promise<ProcessDetail> {
  const res = await http.get<ProcessDetail>('/processes/get_process', {
    params: { process_id: processId },
  })
  return res.data
}

export async function createProcess(payload: ProcessDetail): Promise<ProcessDetail> {
  const res = await http.post<ProcessDetail>('/processes/create_process', payload)
  return res.data
}

export async function updateProcess(processId: string, payload: Partial<ProcessDetail>): Promise<ProcessDetail> {
  const res = await http.post<ProcessDetail>('/processes/update_process', {
    process_id: processId,
    ...payload,
  })
  return res.data
}

export async function deleteProcess(processId: string): Promise<void> {
  await http.post('/processes/delete_process', { process_id: processId })
}

export async function getProcessSteps(processId: string): Promise<ProcessStep[]> {
  const res = await http.get<ProcessStep[]>(`/processes/get_process_steps`, {
    params: { process_id: processId },
  })
  return res.data
}

export async function saveProcessSteps(processId: string, steps: ProcessStep[]): Promise<ProcessStep[]> {
  const res = await http.post<ProcessStep[]>(`/processes/save_process_steps`, {
    process_id: processId,
    steps,
  })
  return res.data
}

export async function deleteProcessStep(processId: string, stepId: number): Promise<void> {
  await http.post('/processes/delete_process_step', {
    process_id: processId,
    step_id: stepId,
  })
}

export async function listProcessEdges(processId: string): Promise<ProcessEdge[]> {
  const res = await http.get<ProcessEdge[]>('/processes/list_process_edges', {
    params: { process_id: processId },
  })
  return res.data
}

export async function createProcessEdge(
  processId: string,
  payload: Omit<ProcessEdge, 'id'>,
): Promise<ProcessEdge> {
  const res = await http.post<ProcessEdge>('/processes/create_process_edge', {
    process_id: processId,
    ...payload,
  })
  return res.data
}

export async function updateProcessEdge(
  processId: string,
  edgeId: number,
  payload: Partial<Omit<ProcessEdge, 'id'>>,
): Promise<ProcessEdge> {
  const res = await http.post<ProcessEdge>('/processes/update_process_edge', {
    process_id: processId,
    edge_id: edgeId,
    ...payload,
  })
  return res.data
}

export async function deleteProcessEdge(processId: string, edgeId: number): Promise<void> {
  await http.post('/processes/delete_process_edge', {
    process_id: processId,
    edge_id: edgeId,
  })
}

export interface PublishResult {
  success: boolean
  message: string
  synced_at?: string
  error_type?: string
  stats?: {
    steps: number
    implementations: number
    data_resources: number
  }
}

export async function publishProcess(processId: string): Promise<PublishResult> {
  const res = await http.post<PublishResult>('/processes/publish_process', {
    process_id: processId,
  })
  return res.data
}

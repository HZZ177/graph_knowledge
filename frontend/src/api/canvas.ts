import http from './http'

export interface CanvasProcess {
  process_id: string
  name: string
  channel?: string | null
  description?: string | null
  entrypoints?: string | null
}

export interface CanvasStep {
  step_id: string
  name?: string | null
  description?: string | null
  step_type?: string | null
}

export interface CanvasEdge {
  id?: number
  from_step_id: string
  to_step_id: string
  edge_type?: string | null
  condition?: string | null
  label?: string | null
  from_handle?: string | null
  to_handle?: string | null
}

export interface CanvasImplementation {
  impl_id: string
  name?: string | null
  type?: string | null
  system?: string | null
  description?: string | null
  code_ref?: string | null
}

export interface CanvasStepImplLink {
  id?: number
  step_id: string
  impl_id: string
  step_handle?: string | null
  impl_handle?: string | null
}

export interface CanvasDataResource {
  resource_id: string
  name?: string | null
  type?: string | null
  system?: string | null
  location?: string | null
  description?: string | null
}

export interface CanvasImplDataLink {
  id?: number
  impl_id: string
  resource_id: string
  impl_handle?: string | null
  resource_handle?: string | null
  access_type?: string | null
  access_pattern?: string | null
}

export interface CanvasImplLink {
  id?: number
  from_impl_id: string
  to_impl_id: string
  from_handle?: string | null
  to_handle?: string | null
  edge_type?: string | null
  condition?: string | null
  label?: string | null
}

export interface ProcessCanvas {
  process: CanvasProcess
  steps: CanvasStep[]
  edges: CanvasEdge[]
  implementations: CanvasImplementation[]
  step_impl_links: CanvasStepImplLink[]
  data_resources: CanvasDataResource[]
  impl_data_links: CanvasImplDataLink[]
  impl_links: CanvasImplLink[]
}

export async function getProcessCanvas(processId: string): Promise<ProcessCanvas> {
  const { data } = await http.get<ProcessCanvas>(`/canvas/${processId}`)
  return data
}

export async function saveProcessCanvas(
  processId: string,
  payload: ProcessCanvas,
): Promise<ProcessCanvas> {
  const { data } = await http.put<ProcessCanvas>(`/canvas/${processId}`, payload)
  return data
}

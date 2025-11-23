import http from './http'

export interface GraphStepEntry {
  step: {
    order_no?: number
    step_id: string
    name: string
    description?: string
    step_type?: string
  }
  implementations: any[]
  data_resources: any[]
}

export interface GraphProcessContext {
  process: any
  steps: GraphStepEntry[]
  step_impl_links?: {
    id: number
    step_id: string
    impl_id: string
  }[]
  impl_data_links?: {
    id: number
    impl_id: string
    resource_id: string
    access_type?: string
    access_pattern?: string
  }[]
}

export async function getProcessContext(processId: string): Promise<GraphProcessContext> {
  const res = await http.get<GraphProcessContext>(`/graph/get_process_context/${processId}`)
  return res.data
}

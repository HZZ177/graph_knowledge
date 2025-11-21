import http from './http'

export interface PaginatedResult<T> {
  page: number
  page_size: number
  total: number
  items: T[]
}

export interface BusinessNode {
  process_id: string
  name: string
  channel?: string | null
  description?: string | null
  entrypoints?: string | null
}

export type BusinessCreatePayload = Omit<BusinessNode, 'process_id'>

export interface StepNode {
  step_id: string
  name: string
  description?: string | null
  step_type?: string | null
}

export type StepCreatePayload = Omit<StepNode, 'step_id'>

export interface ImplementationNode {
  impl_id: string
  name: string
  type?: string | null
  system?: string | null
  description?: string | null
  code_ref?: string | null
}

export type ImplementationCreatePayload = Omit<ImplementationNode, 'impl_id'>

export interface StepImplementationLink {
  id: number
  step_id: string
  impl_id: string
}

export async function listBusinessesPaged(q: string, page: number, pageSize: number) {
  const { data } = await http.get<PaginatedResult<BusinessNode>>('/resource-nodes/businesses', {
    params: { q: q || undefined, page, page_size: pageSize },
  })
  return data
}

export async function createBusiness(payload: BusinessCreatePayload) {
  const { data } = await http.post<BusinessNode>('/resource-nodes/businesses', payload)
  return data
}

export async function updateBusiness(processId: string, payload: Partial<BusinessNode>) {
  const { data } = await http.put<BusinessNode>(`/resource-nodes/businesses/${processId}`, payload)
  return data
}

export async function deleteBusiness(processId: string) {
  await http.delete(`/resource-nodes/businesses/${processId}`)
}

export async function listStepsPaged(q: string, page: number, pageSize: number) {
  const { data } = await http.get<PaginatedResult<StepNode>>('/resource-nodes/steps', {
    params: { q: q || undefined, page, page_size: pageSize },
  })
  return data
}

export async function createStep(payload: StepCreatePayload) {
  const { data } = await http.post<StepNode>('/resource-nodes/steps', payload)
  return data
}

export async function updateStep(stepId: string, payload: Partial<StepNode>) {
  const { data } = await http.put<StepNode>(`/resource-nodes/steps/${stepId}`, payload)
  return data
}

export async function deleteStep(stepId: string) {
  await http.delete(`/resource-nodes/steps/${stepId}`)
}

export async function listImplementationsPaged(q: string, page: number, pageSize: number) {
  const { data } = await http.get<PaginatedResult<ImplementationNode>>('/resource-nodes/implementations', {
    params: { q: q || undefined, page, page_size: pageSize },
  })
  return data
}

export async function createImplementation(payload: ImplementationCreatePayload) {
  const { data } = await http.post<ImplementationNode>('/resource-nodes/implementations', payload)
  return data
}

export async function updateImplementation(implId: string, payload: Partial<ImplementationNode>) {
  const { data } = await http.put<ImplementationNode>(`/resource-nodes/implementations/${implId}`, payload)
  return data
}

export async function deleteImplementation(implId: string) {
  await http.delete(`/resource-nodes/implementations/${implId}`)
}

export async function createStepImplementationLink(
  stepId: string,
  implId: string,
): Promise<StepImplementationLink> {
  const { data } = await http.post<StepImplementationLink>(
    '/resource-nodes/step-implementations',
    { step_id: stepId, impl_id: implId },
  )
  return data
}

export async function deleteStepImplementationLink(linkId: number): Promise<void> {
  await http.delete(`/resource-nodes/step-implementations/${linkId}`)
}

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
  const { data } = await http.get<PaginatedResult<BusinessNode>>('/resource-nodes/list_businesses', {
    params: { q: q || undefined, page, page_size: pageSize },
  })
  return data
}

export async function createBusiness(payload: BusinessCreatePayload) {
  const { data } = await http.post<BusinessNode>('/resource-nodes/create_business', payload)
  return data
}

export async function updateBusiness(processId: string, payload: Partial<BusinessNode>) {
  const { data } = await http.post<BusinessNode>('/resource-nodes/update_business', {
    process_id: processId,
    ...payload,
  })
  return data
}

export async function deleteBusiness(processId: string) {
  await http.post('/resource-nodes/delete_business', { process_id: processId })
}

export async function listStepsPaged(q: string, page: number, pageSize: number) {
  const { data } = await http.get<PaginatedResult<StepNode>>('/resource-nodes/list_steps', {
    params: { q: q || undefined, page, page_size: pageSize },
  })
  return data
}

export async function createStep(payload: StepCreatePayload) {
  const { data } = await http.post<StepNode>('/resource-nodes/create_step', payload)
  return data
}

export async function updateStep(stepId: string, payload: Partial<StepNode>) {
  const { data } = await http.post<StepNode>('/resource-nodes/update_step', {
    step_id: stepId,
    ...payload,
  })
  return data
}

export async function deleteStep(stepId: string) {
  await http.post('/resource-nodes/delete_step', { step_id: stepId })
}

export async function listImplementationsPaged(q: string, page: number, pageSize: number) {
  const { data } = await http.get<PaginatedResult<ImplementationNode>>('/resource-nodes/list_implementations', {
    params: { q: q || undefined, page, page_size: pageSize },
  })
  return data
}

export async function createImplementation(payload: ImplementationCreatePayload) {
  const { data } = await http.post<ImplementationNode>('/resource-nodes/create_implementation', payload)
  return data
}

export async function updateImplementation(implId: string, payload: Partial<ImplementationNode>) {
  const { data } = await http.post<ImplementationNode>('/resource-nodes/update_implementation', {
    impl_id: implId,
    ...payload,
  })
  return data
}

export async function deleteImplementation(implId: string) {
  await http.post('/resource-nodes/delete_implementation', { impl_id: implId })
}

export async function createStepImplementationLink(
  stepId: string,
  implId: string,
): Promise<StepImplementationLink> {
  const { data } = await http.post<StepImplementationLink>(
    '/resource-nodes/create_step_implementation_link',
    { step_id: stepId, impl_id: implId },
  )
  return data
}

export async function deleteStepImplementationLink(linkId: number): Promise<void> {
  await http.post('/resource-nodes/delete_step_implementation_link', { link_id: linkId })
}

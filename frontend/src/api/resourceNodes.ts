import http from './http'

export interface PaginatedResult<T> {
  page: number
  page_size: number
  total: number
  items: T[]
}

// 分组统计类型
export interface GroupCount {
  value: string | null
  count: number
}

export interface BusinessGroupStats {
  by_channel: GroupCount[]
  total: number
}

export interface StepGroupStats {
  by_step_type: GroupCount[]
  total: number
}

export interface ImplementationGroupStats {
  by_system: GroupCount[]
  by_type: GroupCount[]
  total: number
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

export async function getBusinessGroupStats() {
  const { data } = await http.get<BusinessGroupStats>('/resource-nodes/business_group_stats')
  return data
}

// 获取所有已存在的渠道列表（用于下拉选择）
export async function getChannelOptions(): Promise<string[]> {
  const stats = await getBusinessGroupStats()
  return stats.by_channel
    .map((g) => g.value)
    .filter((v): v is string => v !== null && v !== '')
}

// 获取所有已存在的系统列表（用于下拉选择）
export async function getSystemOptions(): Promise<string[]> {
  const stats = await getImplementationGroupStats()
  return stats.by_system
    .map((g) => g.value)
    .filter((v): v is string => v !== null && v !== '')
}

export interface ListBusinessesParams {
  q?: string
  channel?: string
  page?: number
  page_size?: number
}

export async function listBusinessesPaged(
  q: string,
  page: number,
  pageSize: number,
  channel?: string,
) {
  const { data } = await http.get<PaginatedResult<BusinessNode>>('/resource-nodes/list_businesses', {
    params: { q: q || undefined, page, page_size: pageSize, channel },
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

export async function getStepGroupStats() {
  const { data } = await http.get<StepGroupStats>('/resource-nodes/step_group_stats')
  return data
}

export async function listStepsPaged(
  q: string,
  page: number,
  pageSize: number,
  stepType?: string,
) {
  const { data } = await http.get<PaginatedResult<StepNode>>('/resource-nodes/list_steps', {
    params: { q: q || undefined, page, page_size: pageSize, step_type: stepType },
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

export async function getImplementationGroupStats() {
  const { data } = await http.get<ImplementationGroupStats>('/resource-nodes/implementation_group_stats')
  return data
}

export async function listImplementationsPaged(
  q: string,
  page: number,
  pageSize: number,
  system?: string,
  type?: string,
) {
  const { data } = await http.get<PaginatedResult<ImplementationNode>>('/resource-nodes/list_implementations', {
    params: { q: q || undefined, page, page_size: pageSize, system, type },
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

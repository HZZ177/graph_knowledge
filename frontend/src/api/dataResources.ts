import http from './http'

export interface DataResource {
  resource_id: string
  name: string
  type?: string
  system?: string
  location?: string
  description?: string
  ddl?: string
}

// 分组统计类型
export interface GroupCount {
  value: string | null
  count: number
}

export interface SystemTypeCount {
  system: string | null
  type: string | null
  count: number
}

export interface DataResourceGroupStats {
  by_system: GroupCount[]
  by_type: GroupCount[]
  by_system_type: SystemTypeCount[]
  total: number
}

export type DataResourceCreatePayload = Omit<DataResource, 'resource_id'>

export interface PaginatedDataResources {
  page: number
  page_size: number
  total: number
  items: DataResource[]
}

export interface ResourceAccessor {
  impl_id: string
  impl_name: string
  impl_system?: string
  access_type?: string
  access_pattern?: string
  step_id?: string | null
  step_name?: string | null
  process_id?: string | null
  process_name?: string | null
}

export interface ImplementationDataLink {
  id: number
  impl_id: string
  resource_id: string
  access_type?: string | null
  access_pattern?: string | null
}

export interface AccessChainItem {
  resource_id: string
  resource_name: string
  impl_id?: string | null
  impl_name?: string | null
  impl_system?: string | null
  access_type?: string | null
  access_pattern?: string | null
  step_id?: string | null
  step_name?: string | null
  process_id?: string | null
  process_name?: string | null
}

export interface ResourceWithAccessors {
  resource: DataResource
  accessors: ResourceAccessor[]
}

export interface BusinessSimple {
  process_id: string
  name: string
}

export interface StepSimple {
  step_id: string
  name: string
  process_id?: string | null
  process_name?: string | null
}

export interface ListDataResourcesParams {
  page?: number
  page_size?: number
  q?: string
  type?: string
  system?: string
  process_id?: string
  step_id?: string
}

export async function getDataResourceGroupStats() {
  const { data } = await http.get<DataResourceGroupStats>('/resource-nodes/data_resource_group_stats')
  return data
}

export async function listDataResources(params: ListDataResourcesParams) {
  const { data } = await http.get<PaginatedDataResources>('/resource-nodes/list_data_resources', { params })
  return data
}

export async function createDataResource(payload: DataResourceCreatePayload) {
  const { data } = await http.post<DataResource>('/resource-nodes/create_data_resource', payload)
  return data
}

export async function getDataResource(resourceId: string) {
  const { data } = await http.get<DataResource>('/resource-nodes/get_data_resource', {
    params: { resource_id: resourceId },
  })
  return data
}

export async function updateDataResource(resourceId: string, payload: Partial<DataResource>) {
  const { data } = await http.post<DataResource>('/resource-nodes/update_data_resource', {
    resource_id: resourceId,
    ...payload,
  })
  return data
}

export async function deleteDataResource(resourceId: string) {
  await http.post('/resource-nodes/delete_data_resource', { resource_id: resourceId })
}

export async function getResourceAccessors(resourceId: string) {
  const { data } = await http.get<ResourceWithAccessors>(`/resource-nodes/get_resource_accessors`, {
    params: { resource_id: resourceId },
  })
  return data
}

export async function createImplementationDataLink(
  payload: Omit<ImplementationDataLink, 'id'>,
): Promise<ImplementationDataLink> {
  const { data } = await http.post<ImplementationDataLink>(
    '/resource-nodes/create_implementation_data_link',
    payload,
  )
  return data
}

export async function updateImplementationDataLink(
  linkId: number,
  payload: Partial<Pick<ImplementationDataLink, 'access_type' | 'access_pattern'>>,
): Promise<ImplementationDataLink> {
  const { data } = await http.post<ImplementationDataLink>(
    `/resource-nodes/update_implementation_data_link`,
    {
      link_id: linkId,
      ...payload,
    },
  )
  return data
}

export async function deleteImplementationDataLink(linkId: number): Promise<void> {
  await http.post('/resource-nodes/delete_implementation_data_link', { link_id: linkId })
}

type AccessNodeKind = 'resource' | 'impl' | 'step' | 'process'

export async function listAccessChainsByNode(kind: AccessNodeKind, id: string) {
  const paramKeyMap: Record<AccessNodeKind, string> = {
    resource: 'resource_id',
    impl: 'impl_id',
    step: 'step_id',
    process: 'process_id',
  }

  const key = paramKeyMap[kind]
  const params: Record<string, string> = { [key]: id }

  const { data } = await http.get<AccessChainItem[]>('/resource-nodes/get_access_chains', { params })
  return data
}

export async function listBusinesses() {
  const { data } = await http.get<BusinessSimple[]>('/resource-nodes/list_data_resource_businesses')
  return data
}

export async function listSteps(processId?: string) {
  const { data } = await http.get<StepSimple[]>('/resource-nodes/list_data_resource_steps', {
    params: processId ? { process_id: processId } : undefined,
  })
  return data
}

// 批量创建数据资源
export interface DataResourceBatchCreateResult {
  success_count: number
  skip_count: number
  failed_count: number
  created_items: DataResource[]
  skipped_names: string[]
  failed_items: { name: string; error: string }[]
}

export async function batchCreateDataResources(
  items: DataResourceCreatePayload[]
): Promise<DataResourceBatchCreateResult> {
  const { data } = await http.post<DataResourceBatchCreateResult>(
    '/resource-nodes/batch_create_data_resources',
    { items }
  )
  return data
}

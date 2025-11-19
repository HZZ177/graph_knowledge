import http from './http'

export interface DataResource {
  resource_id: string
  name: string
  type?: string
  system?: string
  location?: string
  entity_id?: string
  description?: string
}

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

export async function listDataResources(params: ListDataResourcesParams) {
  const { data } = await http.get<PaginatedDataResources>('/data-resources', { params })
  return data
}

export async function createDataResource(payload: DataResource) {
  const { data } = await http.post<DataResource>('/data-resources', payload)
  return data
}

export async function getDataResource(resourceId: string) {
  const { data } = await http.get<DataResource>(`/data-resources/${resourceId}`)
  return data
}

export async function updateDataResource(resourceId: string, payload: Partial<DataResource>) {
  const { data } = await http.put<DataResource>(`/data-resources/${resourceId}` , payload)
  return data
}

export async function deleteDataResource(resourceId: string) {
  await http.delete(`/data-resources/${resourceId}`)
}

export async function getResourceAccessors(resourceId: string) {
  const { data } = await http.get<ResourceWithAccessors>(`/data-resources/${resourceId}/accessors`)
  return data
}

export async function createImplementationDataLink(
  payload: Omit<ImplementationDataLink, 'id'>,
): Promise<ImplementationDataLink> {
  const { data } = await http.post<ImplementationDataLink>(
    '/data-resources/implementation-links',
    payload,
  )
  return data
}

export async function updateImplementationDataLink(
  linkId: number,
  payload: Partial<Pick<ImplementationDataLink, 'access_type' | 'access_pattern'>>,
): Promise<ImplementationDataLink> {
  const { data } = await http.put<ImplementationDataLink>(
    `/data-resources/implementation-links/${linkId}`,
    payload,
  )
  return data
}

export async function deleteImplementationDataLink(linkId: number): Promise<void> {
  await http.delete(`/data-resources/implementation-links/${linkId}`)
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

  const { data } = await http.get<AccessChainItem[]>('/data-resources/access-chains', { params })
  return data
}

export async function listBusinesses() {
  const { data } = await http.get<BusinessSimple[]>('/data-resources/meta/businesses')
  return data
}

export async function listSteps(processId?: string) {
  const { data } = await http.get<StepSimple[]>('/data-resources/meta/steps', {
    params: processId ? { process_id: processId } : undefined,
  })
  return data
}

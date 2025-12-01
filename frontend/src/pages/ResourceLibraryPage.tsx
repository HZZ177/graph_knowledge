import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Card,
  Typography,
  Form,
  Input,
  Select,
  Button,
  Tabs,
  Space,
  Popconfirm,
  Tag,
  Pagination,
  Tooltip,
  Divider,
  Badge,
} from 'antd'
import {
  DatabaseOutlined,
  CodeOutlined,
  NodeIndexOutlined,
  BranchesOutlined,
  SearchOutlined,
  PlusOutlined,
} from '@ant-design/icons'

import '../styles/ResourceLibraryPage.css'

import { showSuccess, showError } from '../utils/message'

import {
  DataResource,
  listDataResources,
  createDataResource,
  updateDataResource,
  deleteDataResource,
  getDataResourceGroupStats,
  DataResourceGroupStats,
} from '../api/dataResources'

import {
  BusinessNode,
  StepNode,
  ImplementationNode,
  listBusinessesPaged,
  createBusiness,
  updateBusiness,
  deleteBusiness,
  listStepsPaged,
  createStep,
  updateStep,
  deleteStep,
  listImplementationsPaged,
  createImplementation,
  updateImplementation,
  deleteImplementation,
  getBusinessGroupStats,
  getStepGroupStats,
  getImplementationGroupStats,
  BusinessGroupStats,
  StepGroupStats,
  ImplementationGroupStats,
  getChannelOptions,
  getSystemOptions,
} from '../api/resourceNodes'

import ResourceSidebar, { SidebarGroup, buildSingleLevelGroups, buildTwoLevelGroups } from '../components/ResourceSidebar'

// ============ 类型定义 ============

const STEP_TYPE_LABELS: Record<string, string> = {
  inner: '内部步骤',
  outer: '外部步骤',
  '': '其他',
}

const IMPL_TYPE_LABELS: Record<string, string> = {
  api: '接口',
  function: '内部方法',
  job: '定时任务',
  '': '其他',
}

const DATA_TYPE_LABELS: Record<string, string> = {
  table: '库表',
  redis: 'Redis',
  '': '其他',
}

// ============ BusinessTab ============

interface BusinessFormValues {
  name: string
  channel?: string
  description?: string
  entrypoints?: string
}

const BusinessTab: React.FC = () => {
  const [items, setItems] = useState<BusinessNode[]>([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [total, setTotal] = useState(0)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [mode, setMode] = useState<'view' | 'edit' | 'create'>('view')
  const [form] = Form.useForm<BusinessFormValues>()

  // 分组相关
  const [groupStats, setGroupStats] = useState<BusinessGroupStats | null>(null)
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null)
  const [groupLoading, setGroupLoading] = useState(false)
  const [channelOptions, setChannelOptions] = useState<string[]>([])

  const fetchGroupStats = useCallback(async () => {
    setGroupLoading(true)
    try {
      const stats = await getBusinessGroupStats()
      setGroupStats(stats)
      // 提取渠道选项
      const channels = stats.by_channel
        .map((g) => g.value)
        .filter((v): v is string => v !== null && v !== '')
      setChannelOptions(channels)
    } catch (e) {
      showError('加载分组统计失败')
    } finally {
      setGroupLoading(false)
    }
  }, [])

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const channel = selectedGroup === null ? undefined : selectedGroup
      const data = await listBusinessesPaged(keyword, page, pageSize, channel)
      setItems(data.items)
      setTotal(data.total)

      if (data.items.length > 0) {
        setSelectedId((prev) => {
          if (prev && data.items.some((b) => b.process_id === prev)) {
            return prev
          }
          return data.items[0].process_id
        })
      } else {
        setSelectedId(null)
      }
    } catch (e) {
      showError('加载列表失败')
    } finally {
      setLoading(false)
    }
  }, [keyword, page, pageSize, selectedGroup])

  useEffect(() => {
    fetchGroupStats()
  }, [fetchGroupStats])

  useEffect(() => {
    fetchList()
  }, [fetchList])

  const selectedItem = useMemo(
    () => items.find((b) => b.process_id === selectedId) || null,
    [items, selectedId],
  )

  const isCreateMode = mode === 'create'
  const isEditMode = mode === 'edit'
  const isViewMode = mode === 'view'

  useEffect(() => {
    if (!selectedItem || isCreateMode) return
    form.setFieldsValue({
      name: selectedItem.name,
      channel: selectedItem.channel ?? undefined,
      description: selectedItem.description ?? undefined,
      entrypoints: selectedItem.entrypoints ?? undefined,
    })
  }, [selectedItem, isCreateMode, form])

  const sidebarGroups = useMemo<SidebarGroup[]>(() => {
    if (!groupStats) return []
    return buildSingleLevelGroups(groupStats.by_channel, { '': '其他' })
  }, [groupStats])

  const handleGroupSelect = (key: string | null) => {
    setSelectedGroup(key)
    setPage(1)
  }

  const handleStartCreate = () => {
    setMode('create')
    setSelectedId(null)
    form.resetFields()
  }

  const handleEditClick = () => {
    if (!selectedItem) return
    setMode('edit')
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      if (isCreateMode) {
        await createBusiness({
          name: values.name,
          channel: values.channel ?? null,
          description: values.description ?? null,
          entrypoints: values.entrypoints ?? null,
        })
        showSuccess('创建成功')
      } else if (selectedItem) {
        await updateBusiness(selectedItem.process_id, {
          name: values.name,
          channel: values.channel ?? null,
          description: values.description ?? null,
          entrypoints: values.entrypoints ?? null,
        })
        showSuccess('保存成功')
      }
      setMode('view')
      fetchList()
      fetchGroupStats()
    } catch (e: any) {
      if (e?.errorFields) return
      showError('保存失败')
    }
  }

  const handleCancelEdit = () => {
    if (isCreateMode) {
      setMode('view')
      if (items.length > 0) {
        setSelectedId(items[0].process_id)
      }
    } else if (isEditMode) {
      setMode('view')
      if (selectedItem) {
        form.setFieldsValue({
          name: selectedItem.name,
          channel: selectedItem.channel ?? undefined,
          description: selectedItem.description ?? undefined,
          entrypoints: selectedItem.entrypoints ?? undefined,
        })
      }
    }
  }

  const handleDelete = async (item: BusinessNode) => {
    try {
      await deleteBusiness(item.process_id)
      showSuccess('删除成功')
      if (selectedId === item.process_id) {
        setSelectedId(null)
      }
      fetchList()
      fetchGroupStats()
    } catch (e) {
      showError('删除失败')
    }
  }

  const groupTitle = selectedGroup === null
    ? '全部业务流程'
    : selectedGroup === ''
      ? '其他'
      : selectedGroup

  return (
    <div style={{ display: 'flex', height: '100%', gap: 0 }}>
      <ResourceSidebar
        title="按渠道"
        groups={sidebarGroups}
        selectedKey={selectedGroup}
        expandedKeys={[]}
        onSelect={handleGroupSelect}
        onExpand={() => {}}
        loading={groupLoading}
        totalCount={groupStats?.total ?? 0}
      />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8, padding: '0 16px', overflow: 'hidden' }}>
        <div className="toolbar-container" style={{ marginBottom: 4 }}>
          <Input.Search
            allowClear
            placeholder="搜索业务..."
            prefix={<SearchOutlined style={{ color: '#9ca3af' }} />}
            onSearch={(val) => { setKeyword(val); setPage(1) }}
            style={{ width: 280 }}
          />
          <Space>
            <Button onClick={fetchList}>刷新</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleStartCreate}>新建</Button>
          </Space>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Space>
            <Typography.Title level={5} style={{ margin: 0 }}>{groupTitle}</Typography.Title>
            <Badge count={total} style={{ backgroundColor: '#1d4ed8' }} overflowCount={999} showZero />
          </Space>
        </div>

        <div style={{ flex: 1, minHeight: 0, display: 'flex', gap: 16, overflow: 'hidden' }}>
          <div style={{ flex: 1, borderRadius: 8, border: '1px solid #e5e7eb', overflowY: 'auto', padding: 8, background: '#fff' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8 }}>
              {items.map((item) => {
                const isSelected = item.process_id === selectedId
                return (
                  <div
                    key={item.process_id}
                    onClick={() => { setSelectedId(item.process_id); setMode('view') }}
                    style={{
                      borderRadius: 8,
                      border: isSelected ? '2px solid #2563eb' : '1px solid #e5e7eb',
                      padding: 8,
                      cursor: 'pointer',
                      background: isSelected ? '#eff6ff' : '#fff',
                      display: 'flex',
                      flexDirection: 'column',
                    }}
                  >
                    <Space size={6} style={{ marginBottom: 4 }}>
                      <BranchesOutlined style={{ color: '#2563eb' }} />
                      <Tooltip title={item.name}>
                        <Typography.Text strong style={{ fontSize: 13 }}>{item.name}</Typography.Text>
                      </Tooltip>
                    </Space>
                    {item.channel && <div><Tag color="blue" style={{ fontSize: 11, marginBottom: 4 }}>{item.channel}</Tag></div>}
                    <div style={{ fontSize: 11, color: '#6b7280' }}>{item.description || '暂无描述'}</div>
                    <div style={{ marginTop: 'auto', textAlign: 'right', paddingTop: 4 }}>
                      <Popconfirm title="确认删除？" onConfirm={(e) => { e?.stopPropagation(); handleDelete(item) }} onCancel={(e) => e?.stopPropagation()}>
                        <Typography.Text type="secondary" style={{ fontSize: 11, color: '#f97316' }} onClick={(e) => e.stopPropagation()}>删除</Typography.Text>
                      </Popconfirm>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          <div style={{ width: 320, borderLeft: '1px solid #f3f4f6', paddingLeft: 16, overflowY: 'auto' }}>
            <Typography.Title level={5} style={{ margin: 0, marginBottom: 12 }}>详情</Typography.Title>
            {(selectedItem || isCreateMode) && (
              <Card size="small" bordered={false}>
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <Space size={8}>
                      {isViewMode && selectedItem && <Tag color="blue" style={{ cursor: 'pointer' }} onClick={handleEditClick}>编辑</Tag>}
                      {(isEditMode || isCreateMode) && (
                        <>
                          <Tag color="default" style={{ cursor: 'pointer' }} onClick={handleCancelEdit}>取消</Tag>
                          <Tag color="blue" style={{ cursor: 'pointer' }} onClick={handleSubmit}>保存</Tag>
                        </>
                      )}
                    </Space>
                  </div>
                  <Divider style={{ margin: '8px 0' }} />
                  <Form form={form} layout="vertical" disabled={isViewMode && !isCreateMode}>
                    <Form.Item label="名称" name="name" rules={[{ required: true, message: '请输入名称' }]}><Input /></Form.Item>
                    <Form.Item label="渠道" name="channel">
                      <Select placeholder="选择或输入渠道" allowClear showSearch mode={undefined}
                        options={channelOptions.map((c) => ({ label: c, value: c }))}
                        dropdownRender={(menu) => (
                          <>
                            {menu}
                            {channelOptions.length > 0 && <Divider style={{ margin: '4px 0' }} />}
                            <div style={{ padding: '4px 8px', color: '#8c8c8c', fontSize: 12 }}>可直接输入新渠道</div>
                          </>
                        )}
                        filterOption={(input, option) => (option?.label ?? '').toLowerCase().includes(input.toLowerCase())}
                        onSearch={() => {}}
                      />
                    </Form.Item>
                    <Form.Item label="触发场景" name="entrypoints"><Input.TextArea rows={2} /></Form.Item>
                    <Form.Item label="描述" name="description"><Input.TextArea rows={3} /></Form.Item>
                  </Form>
                </Space>
              </Card>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Pagination size="small" current={page} pageSize={pageSize} total={total} showSizeChanger onChange={(p, ps) => { setPage(p); setPageSize(ps) }} />
        </div>
      </div>
    </div>
  )
}

// ============ StepTab ============

interface StepFormValues {
  name: string
  description?: string
  step_type?: string
}

const StepTab: React.FC = () => {
  const [items, setItems] = useState<StepNode[]>([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [total, setTotal] = useState(0)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [mode, setMode] = useState<'view' | 'edit' | 'create'>('view')
  const [form] = Form.useForm<StepFormValues>()

  const [groupStats, setGroupStats] = useState<StepGroupStats | null>(null)
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null)
  const [groupLoading, setGroupLoading] = useState(false)

  const fetchGroupStats = useCallback(async () => {
    setGroupLoading(true)
    try {
      const stats = await getStepGroupStats()
      setGroupStats(stats)
    } catch (e) {
      showError('加载分组统计失败')
    } finally {
      setGroupLoading(false)
    }
  }, [])

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const stepType = selectedGroup === null ? undefined : selectedGroup
      const data = await listStepsPaged(keyword, page, pageSize, stepType)
      setItems(data.items)
      setTotal(data.total)
      if (data.items.length > 0) {
        setSelectedId((prev) => prev && data.items.some((s) => s.step_id === prev) ? prev : data.items[0].step_id)
      } else {
        setSelectedId(null)
      }
    } catch (e) {
      showError('加载列表失败')
    } finally {
      setLoading(false)
    }
  }, [keyword, page, pageSize, selectedGroup])

  useEffect(() => { fetchGroupStats() }, [fetchGroupStats])
  useEffect(() => { fetchList() }, [fetchList])

  const selectedItem = useMemo(() => items.find((s) => s.step_id === selectedId) || null, [items, selectedId])
  const isCreateMode = mode === 'create'
  const isEditMode = mode === 'edit'
  const isViewMode = mode === 'view'

  useEffect(() => {
    if (!selectedItem || isCreateMode) return
    form.setFieldsValue({
      name: selectedItem.name,
      description: selectedItem.description ?? undefined,
      step_type: selectedItem.step_type ?? undefined,
    })
  }, [selectedItem, isCreateMode, form])

  const sidebarGroups = useMemo<SidebarGroup[]>(() => {
    if (!groupStats) return []
    return buildSingleLevelGroups(groupStats.by_step_type, STEP_TYPE_LABELS)
  }, [groupStats])

  const handleGroupSelect = (key: string | null) => { setSelectedGroup(key); setPage(1) }
  const handleStartCreate = () => { setMode('create'); setSelectedId(null); form.resetFields() }
  const handleEditClick = () => { if (selectedItem) setMode('edit') }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      if (isCreateMode) {
        await createStep({ name: values.name, description: values.description ?? null, step_type: values.step_type ?? null })
        showSuccess('创建成功')
      } else if (selectedItem) {
        await updateStep(selectedItem.step_id, { name: values.name, description: values.description ?? null, step_type: values.step_type ?? null })
        showSuccess('保存成功')
      }
      setMode('view')
      fetchList()
      fetchGroupStats()
    } catch (e: any) {
      if (e?.errorFields) return
      showError('保存失败')
    }
  }

  const handleCancelEdit = () => {
    if (isCreateMode) {
      setMode('view')
      if (items.length > 0) setSelectedId(items[0].step_id)
    } else if (isEditMode) {
      setMode('view')
      if (selectedItem) form.setFieldsValue({ name: selectedItem.name, description: selectedItem.description ?? undefined, step_type: selectedItem.step_type ?? undefined })
    }
  }

  const handleDelete = async (item: StepNode) => {
    try {
      await deleteStep(item.step_id)
      showSuccess('删除成功')
      if (selectedId === item.step_id) setSelectedId(null)
      fetchList()
      fetchGroupStats()
    } catch (e) {
      showError('删除失败')
    }
  }

  const groupTitle = selectedGroup === null ? '全部步骤' : STEP_TYPE_LABELS[selectedGroup] || selectedGroup

  return (
    <div style={{ display: 'flex', height: '100%', gap: 0 }}>
      <ResourceSidebar
        title="按步骤类型"
        groups={sidebarGroups}
        selectedKey={selectedGroup}
        expandedKeys={[]}
        onSelect={handleGroupSelect}
        onExpand={() => {}}
        loading={groupLoading}
        totalCount={groupStats?.total ?? 0}
      />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8, padding: '0 16px', overflow: 'hidden' }}>
        <div className="toolbar-container" style={{ marginBottom: 4 }}>
          <Input.Search allowClear placeholder="搜索步骤..." prefix={<SearchOutlined style={{ color: '#9ca3af' }} />} onSearch={(val) => { setKeyword(val); setPage(1) }} style={{ width: 280 }} />
          <Space>
            <Button onClick={fetchList}>刷新</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleStartCreate}>新建</Button>
          </Space>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Space>
            <Typography.Title level={5} style={{ margin: 0 }}>{groupTitle}</Typography.Title>
            <Badge count={total} style={{ backgroundColor: '#059669' }} overflowCount={999} showZero />
          </Space>
        </div>

        <div style={{ flex: 1, minHeight: 0, display: 'flex', gap: 16, overflow: 'hidden' }}>
          <div style={{ flex: 1, borderRadius: 8, border: '1px solid #e5e7eb', overflowY: 'auto', padding: 8, background: '#fff' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8 }}>
              {items.map((item) => {
                const isSelected = item.step_id === selectedId
                return (
                  <div
                    key={item.step_id}
                    onClick={() => { setSelectedId(item.step_id); setMode('view') }}
                    style={{ borderRadius: 8, border: isSelected ? '2px solid #059669' : '1px solid #e5e7eb', padding: 8, cursor: 'pointer', background: isSelected ? '#ecfdf5' : '#fff', display: 'flex', flexDirection: 'column' }}
                  >
                    <Space size={6} style={{ marginBottom: 4 }}>
                      <NodeIndexOutlined style={{ color: '#059669' }} />
                      <Tooltip title={item.name}><Typography.Text strong style={{ fontSize: 13 }}>{item.name}</Typography.Text></Tooltip>
                    </Space>
                    {item.step_type && <div><Tag style={{ fontSize: 11, marginBottom: 4 }}>{STEP_TYPE_LABELS[item.step_type] || item.step_type}</Tag></div>}
                    <div style={{ fontSize: 11, color: '#6b7280' }}>{item.description || '暂无描述'}</div>
                    <div style={{ marginTop: 'auto', textAlign: 'right', paddingTop: 4 }}>
                      <Popconfirm title="确认删除？" onConfirm={(e) => { e?.stopPropagation(); handleDelete(item) }} onCancel={(e) => e?.stopPropagation()}>
                        <Typography.Text type="secondary" style={{ fontSize: 11, color: '#f97316' }} onClick={(e) => e.stopPropagation()}>删除</Typography.Text>
                      </Popconfirm>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          <div style={{ width: 320, borderLeft: '1px solid #f3f4f6', paddingLeft: 16, overflowY: 'auto' }}>
            <Typography.Title level={5} style={{ margin: 0, marginBottom: 12 }}>详情</Typography.Title>
            {(selectedItem || isCreateMode) && (
              <Card size="small" bordered={false}>
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <Space size={8}>
                      {isViewMode && selectedItem && <Tag color="blue" style={{ cursor: 'pointer' }} onClick={handleEditClick}>编辑</Tag>}
                      {(isEditMode || isCreateMode) && (
                        <>
                          <Tag color="default" style={{ cursor: 'pointer' }} onClick={handleCancelEdit}>取消</Tag>
                          <Tag color="blue" style={{ cursor: 'pointer' }} onClick={handleSubmit}>保存</Tag>
                        </>
                      )}
                    </Space>
                  </div>
                  <Divider style={{ margin: '8px 0' }} />
                  <Form form={form} layout="vertical" disabled={isViewMode && !isCreateMode}>
                    <Form.Item label="名称" name="name" rules={[{ required: true, message: '请输入名称' }]}><Input /></Form.Item>
                    <Form.Item label="步骤类型" name="step_type" rules={[{ required: true, message: '请选择步骤类型' }]}>
                      <Select placeholder="选择类型">
                        <Select.Option value="inner">内部步骤</Select.Option>
                        <Select.Option value="outer">外部步骤</Select.Option>
                      </Select>
                    </Form.Item>
                    <Form.Item label="描述" name="description"><Input.TextArea rows={3} /></Form.Item>
                  </Form>
                </Space>
              </Card>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Pagination size="small" current={page} pageSize={pageSize} total={total} showSizeChanger onChange={(p, ps) => { setPage(p); setPageSize(ps) }} />
        </div>
      </div>
    </div>
  )
}

// ============ ImplementationTab ============

interface ImplFormValues {
  name: string
  type?: string
  system?: string
  description?: string
  code_ref?: string
}

const ImplementationTab: React.FC = () => {
  const [items, setItems] = useState<ImplementationNode[]>([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [total, setTotal] = useState(0)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [mode, setMode] = useState<'view' | 'edit' | 'create'>('view')
  const [form] = Form.useForm<ImplFormValues>()

  const [groupStats, setGroupStats] = useState<ImplementationGroupStats | null>(null)
  const [selectedSystem, setSelectedSystem] = useState<string | null>(null)
  const [selectedType, setSelectedType] = useState<string | null>(null)
  const [expandedKeys, setExpandedKeys] = useState<string[]>([])
  const [groupLoading, setGroupLoading] = useState(false)
  const [systemOptions, setSystemOptions] = useState<string[]>([])

  const fetchGroupStats = useCallback(async () => {
    setGroupLoading(true)
    try {
      const stats = await getImplementationGroupStats()
      setGroupStats(stats)
      // 提取系统选项
      const systems = stats.by_system
        .map((g) => g.value)
        .filter((v): v is string => v !== null && v !== '')
      setSystemOptions(systems)
    } catch (e) {
      showError('加载分组统计失败')
    } finally {
      setGroupLoading(false)
    }
  }, [])

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const system = selectedSystem === null ? undefined : selectedSystem
      const type = selectedType === null ? undefined : selectedType
      const data = await listImplementationsPaged(keyword, page, pageSize, system, type)
      setItems(data.items)
      setTotal(data.total)
      if (data.items.length > 0) {
        setSelectedId((prev) => prev && data.items.some((i) => i.impl_id === prev) ? prev : data.items[0].impl_id)
      } else {
        setSelectedId(null)
      }
    } catch (e) {
      showError('加载列表失败')
    } finally {
      setLoading(false)
    }
  }, [keyword, page, pageSize, selectedSystem, selectedType])

  useEffect(() => { fetchGroupStats() }, [fetchGroupStats])
  useEffect(() => { fetchList() }, [fetchList])

  const selectedItem = useMemo(() => items.find((i) => i.impl_id === selectedId) || null, [items, selectedId])
  const isCreateMode = mode === 'create'
  const isEditMode = mode === 'edit'
  const isViewMode = mode === 'view'

  useEffect(() => {
    if (!selectedItem || isCreateMode) return
    form.setFieldsValue({
      name: selectedItem.name,
      type: selectedItem.type ?? undefined,
      system: selectedItem.system ?? undefined,
      description: selectedItem.description ?? undefined,
      code_ref: selectedItem.code_ref ?? undefined,
    })
  }, [selectedItem, isCreateMode, form])

  const sidebarGroups = useMemo<SidebarGroup[]>(() => {
    if (!groupStats) return []
    return buildTwoLevelGroups(groupStats.by_system, groupStats.by_type, { '': '其他' }, IMPL_TYPE_LABELS)
  }, [groupStats])

  const handleGroupSelect = (key: string | null) => {
    if (key === null) {
      setSelectedSystem(null)
      setSelectedType(null)
    } else if (key.includes('::')) {
      const [sys, type] = key.split('::')
      setSelectedSystem(sys)
      setSelectedType(type)
    } else {
      setSelectedSystem(key)
      setSelectedType(null)
    }
    setPage(1)
  }

  const getSelectedKey = () => {
    if (selectedSystem === null && selectedType === null) return null
    if (selectedType !== null) return `${selectedSystem}::${selectedType}`
    return selectedSystem
  }

  const handleStartCreate = () => { setMode('create'); setSelectedId(null); form.resetFields() }
  const handleEditClick = () => { if (selectedItem) setMode('edit') }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      if (isCreateMode) {
        await createImplementation({ name: values.name, type: values.type ?? null, system: values.system ?? null, description: values.description ?? null, code_ref: values.code_ref ?? null })
        showSuccess('创建成功')
      } else if (selectedItem) {
        await updateImplementation(selectedItem.impl_id, { name: values.name, type: values.type ?? null, system: values.system ?? null, description: values.description ?? null, code_ref: values.code_ref ?? null })
        showSuccess('保存成功')
      }
      setMode('view')
      fetchList()
      fetchGroupStats()
    } catch (e: any) {
      if (e?.errorFields) return
      showError('保存失败')
    }
  }

  const handleCancelEdit = () => {
    if (isCreateMode) {
      setMode('view')
      if (items.length > 0) setSelectedId(items[0].impl_id)
    } else if (isEditMode) {
      setMode('view')
      if (selectedItem) form.setFieldsValue({ name: selectedItem.name, type: selectedItem.type ?? undefined, system: selectedItem.system ?? undefined, description: selectedItem.description ?? undefined, code_ref: selectedItem.code_ref ?? undefined })
    }
  }

  const handleDelete = async (item: ImplementationNode) => {
    try {
      await deleteImplementation(item.impl_id)
      showSuccess('删除成功')
      if (selectedId === item.impl_id) setSelectedId(null)
      fetchList()
      fetchGroupStats()
    } catch (e) {
      showError('删除失败')
    }
  }

  const groupTitle = (() => {
    if (selectedSystem === null) return '全部实现单元'
    const sysLabel = selectedSystem || '其他'
    if (selectedType !== null) {
      const typeLabel = IMPL_TYPE_LABELS[selectedType] || selectedType || '其他'
      return `${sysLabel} / ${typeLabel}`
    }
    return sysLabel
  })()

  return (
    <div style={{ display: 'flex', height: '100%', gap: 0 }}>
      <ResourceSidebar
        title="按系统"
        groups={sidebarGroups}
        selectedKey={getSelectedKey()}
        expandedKeys={expandedKeys}
        onSelect={handleGroupSelect}
        onExpand={setExpandedKeys}
        loading={groupLoading}
        totalCount={groupStats?.total ?? 0}
      />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8, padding: '0 16px', overflow: 'hidden' }}>
        <div className="toolbar-container" style={{ marginBottom: 4 }}>
          <Input.Search allowClear placeholder="搜索实现..." prefix={<SearchOutlined style={{ color: '#9ca3af' }} />} onSearch={(val) => { setKeyword(val); setPage(1) }} style={{ width: 280 }} />
          <Space>
            <Button onClick={fetchList}>刷新</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleStartCreate}>新建</Button>
          </Space>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Space>
            <Typography.Title level={5} style={{ margin: 0 }}>{groupTitle}</Typography.Title>
            <Badge count={total} style={{ backgroundColor: '#7c3aed' }} overflowCount={999} showZero />
          </Space>
        </div>

        <div style={{ flex: 1, minHeight: 0, display: 'flex', gap: 16, overflow: 'hidden' }}>
          <div style={{ flex: 1, borderRadius: 8, border: '1px solid #e5e7eb', overflowY: 'auto', padding: 8, background: '#fff' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8 }}>
              {items.map((item) => {
                const isSelected = item.impl_id === selectedId
                return (
                  <div
                    key={item.impl_id}
                    onClick={() => { setSelectedId(item.impl_id); setMode('view') }}
                    style={{ borderRadius: 8, border: isSelected ? '2px solid #7c3aed' : '1px solid #e5e7eb', padding: 8, cursor: 'pointer', background: isSelected ? '#f5f3ff' : '#fff', display: 'flex', flexDirection: 'column' }}
                  >
                    <Space size={6} style={{ marginBottom: 4 }}>
                      <CodeOutlined style={{ color: '#7c3aed' }} />
                      <Tooltip title={item.name}><Typography.Text strong style={{ fontSize: 13 }}>{item.name}</Typography.Text></Tooltip>
                    </Space>
                    <Space size={4} style={{ marginBottom: 4 }}>
                      {item.system && <Tag color="purple" style={{ fontSize: 10 }}>{item.system}</Tag>}
                      {item.type && <Tag style={{ fontSize: 10 }}>{IMPL_TYPE_LABELS[item.type] || item.type}</Tag>}
                    </Space>
                    <div style={{ fontSize: 11, color: '#6b7280' }}>{item.description || '暂无描述'}</div>
                    <div style={{ marginTop: 'auto', textAlign: 'right', paddingTop: 4 }}>
                      <Popconfirm title="确认删除？" onConfirm={(e) => { e?.stopPropagation(); handleDelete(item) }} onCancel={(e) => e?.stopPropagation()}>
                        <Typography.Text type="secondary" style={{ fontSize: 11, color: '#f97316' }} onClick={(e) => e.stopPropagation()}>删除</Typography.Text>
                      </Popconfirm>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          <div style={{ width: 320, borderLeft: '1px solid #f3f4f6', paddingLeft: 16, overflowY: 'auto' }}>
            <Typography.Title level={5} style={{ margin: 0, marginBottom: 12 }}>详情</Typography.Title>
            {(selectedItem || isCreateMode) && (
              <Card size="small" bordered={false}>
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <Space size={8}>
                      {isViewMode && selectedItem && <Tag color="blue" style={{ cursor: 'pointer' }} onClick={handleEditClick}>编辑</Tag>}
                      {(isEditMode || isCreateMode) && (
                        <>
                          <Tag color="default" style={{ cursor: 'pointer' }} onClick={handleCancelEdit}>取消</Tag>
                          <Tag color="blue" style={{ cursor: 'pointer' }} onClick={handleSubmit}>保存</Tag>
                        </>
                      )}
                    </Space>
                  </div>
                  <Divider style={{ margin: '8px 0' }} />
                  <Form form={form} layout="vertical" disabled={isViewMode && !isCreateMode}>
                    <Form.Item label="名称" name="name" rules={[{ required: true, message: '请输入名称' }]}><Input /></Form.Item>
                    <Form.Item label="所属系统" name="system" rules={[{ required: true, message: '请选择系统' }]}>
                      <Select placeholder="选择系统" allowClear>
                        <Select.Option value="admin">admin</Select.Option>
                        <Select.Option value="owner-center">owner-center</Select.Option>
                        <Select.Option value="pay-center">pay-center</Select.Option>
                      </Select>
                    </Form.Item>
                    <Form.Item label="类型" name="type" rules={[{ required: true, message: '请选择类型' }]}>
                      <Select placeholder="选择类型" allowClear>
                        <Select.Option value="api">接口</Select.Option>
                        <Select.Option value="function">内部方法</Select.Option>
                        <Select.Option value="job">定时任务</Select.Option>
                      </Select>
                    </Form.Item>
                    <Form.Item label="代码引用" name="code_ref"><Input placeholder="如 com.example.Service#method" /></Form.Item>
                    <Form.Item label="描述" name="description"><Input.TextArea rows={3} /></Form.Item>
                  </Form>
                </Space>
              </Card>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Pagination size="small" current={page} pageSize={pageSize} total={total} showSizeChanger onChange={(p, ps) => { setPage(p); setPageSize(ps) }} />
        </div>
      </div>
    </div>
  )
}

// ============ DataResourceTab ============

interface DataResourceFormValues {
  name: string
  type?: string
  system?: string
  location?: string
  description?: string
}

const DataResourceTab: React.FC = () => {
  const [items, setItems] = useState<DataResource[]>([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [total, setTotal] = useState(0)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [mode, setMode] = useState<'view' | 'edit' | 'create'>('view')
  const [form] = Form.useForm<DataResourceFormValues>()

  const [groupStats, setGroupStats] = useState<DataResourceGroupStats | null>(null)
  const [selectedSystem, setSelectedSystem] = useState<string | null>(null)
  const [selectedType, setSelectedType] = useState<string | null>(null)
  const [expandedKeys, setExpandedKeys] = useState<string[]>([])
  const [groupLoading, setGroupLoading] = useState(false)
  const [systemOptions, setSystemOptions] = useState<string[]>([])

  const fetchGroupStats = useCallback(async () => {
    setGroupLoading(true)
    try {
      const stats = await getDataResourceGroupStats()
      setGroupStats(stats)
      // 提取系统选项
      const systems = stats.by_system
        .map((g) => g.value)
        .filter((v): v is string => v !== null && v !== '')
      setSystemOptions(systems)
    } catch (e) {
      showError('加载分组统计失败')
    } finally {
      setGroupLoading(false)
    }
  }, [])

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const system = selectedSystem === null ? undefined : selectedSystem
      const type = selectedType === null ? undefined : selectedType
      const data = await listDataResources({ q: keyword || undefined, page, page_size: pageSize, system, type })
      setItems(data.items)
      setTotal(data.total)
      if (data.items.length > 0) {
        setSelectedId((prev) => prev && data.items.some((r) => r.resource_id === prev) ? prev : data.items[0].resource_id)
      } else {
        setSelectedId(null)
      }
    } catch (e) {
      showError('加载列表失败')
    } finally {
      setLoading(false)
    }
  }, [keyword, page, pageSize, selectedSystem, selectedType])

  useEffect(() => { fetchGroupStats() }, [fetchGroupStats])
  useEffect(() => { fetchList() }, [fetchList])

  const selectedItem = useMemo(() => items.find((r) => r.resource_id === selectedId) || null, [items, selectedId])
  const isCreateMode = mode === 'create'
  const isEditMode = mode === 'edit'
  const isViewMode = mode === 'view'

  useEffect(() => {
    if (!selectedItem || isCreateMode) return
    form.setFieldsValue({
      name: selectedItem.name,
      type: selectedItem.type ?? undefined,
      system: selectedItem.system ?? undefined,
      location: selectedItem.location ?? undefined,
      description: selectedItem.description ?? undefined,
    })
  }, [selectedItem, isCreateMode, form])

  const sidebarGroups = useMemo<SidebarGroup[]>(() => {
    if (!groupStats) return []
    return buildTwoLevelGroups(groupStats.by_system, groupStats.by_type, { '': '其他' }, DATA_TYPE_LABELS)
  }, [groupStats])

  const handleGroupSelect = (key: string | null) => {
    if (key === null) {
      setSelectedSystem(null)
      setSelectedType(null)
    } else if (key.includes('::')) {
      const [sys, type] = key.split('::')
      setSelectedSystem(sys)
      setSelectedType(type)
    } else {
      setSelectedSystem(key)
      setSelectedType(null)
    }
    setPage(1)
  }

  const getSelectedKey = () => {
    if (selectedSystem === null && selectedType === null) return null
    if (selectedType !== null) return `${selectedSystem}::${selectedType}`
    return selectedSystem
  }

  const handleStartCreate = () => { setMode('create'); setSelectedId(null); form.resetFields() }
  const handleEditClick = () => { if (selectedItem) setMode('edit') }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      if (isCreateMode) {
        await createDataResource({ name: values.name, type: values.type, system: values.system, location: values.location, description: values.description })
        showSuccess('创建成功')
      } else if (selectedItem) {
        await updateDataResource(selectedItem.resource_id, { name: values.name, type: values.type, system: values.system, location: values.location, description: values.description })
        showSuccess('保存成功')
      }
      setMode('view')
      fetchList()
      fetchGroupStats()
    } catch (e: any) {
      if (e?.errorFields) return
      showError('保存失败')
    }
  }

  const handleCancelEdit = () => {
    if (isCreateMode) {
      setMode('view')
      if (items.length > 0) setSelectedId(items[0].resource_id)
    } else if (isEditMode) {
      setMode('view')
      if (selectedItem) form.setFieldsValue({ name: selectedItem.name, type: selectedItem.type ?? undefined, system: selectedItem.system ?? undefined, location: selectedItem.location ?? undefined, description: selectedItem.description ?? undefined })
    }
  }

  const handleDelete = async (item: DataResource) => {
    try {
      await deleteDataResource(item.resource_id)
      showSuccess('删除成功')
      if (selectedId === item.resource_id) setSelectedId(null)
      fetchList()
      fetchGroupStats()
    } catch (e) {
      showError('删除失败')
    }
  }

  const groupTitle = (() => {
    if (selectedSystem === null) return '全部数据资源'
    const sysLabel = selectedSystem || '其他'
    if (selectedType !== null) {
      const typeLabel = DATA_TYPE_LABELS[selectedType] || selectedType || '其他'
      return `${sysLabel} / ${typeLabel}`
    }
    return sysLabel
  })()

  return (
    <div style={{ display: 'flex', height: '100%', gap: 0 }}>
      <ResourceSidebar
        title="按系统"
        groups={sidebarGroups}
        selectedKey={getSelectedKey()}
        expandedKeys={expandedKeys}
        onSelect={handleGroupSelect}
        onExpand={setExpandedKeys}
        loading={groupLoading}
        totalCount={groupStats?.total ?? 0}
      />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8, padding: '0 16px', overflow: 'hidden' }}>
        <div className="toolbar-container" style={{ marginBottom: 4 }}>
          <Input.Search allowClear placeholder="搜索数据资源..." prefix={<SearchOutlined style={{ color: '#9ca3af' }} />} onSearch={(val) => { setKeyword(val); setPage(1) }} style={{ width: 280 }} />
          <Space>
            <Button onClick={fetchList}>刷新</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleStartCreate}>新建</Button>
          </Space>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Space>
            <Typography.Title level={5} style={{ margin: 0 }}>{groupTitle}</Typography.Title>
            <Badge count={total} style={{ backgroundColor: '#faad14' }} overflowCount={999} showZero />
          </Space>
        </div>

        <div style={{ flex: 1, minHeight: 0, display: 'flex', gap: 16, overflow: 'hidden' }}>
          <div style={{ flex: 1, borderRadius: 8, border: '1px solid #e5e7eb', overflowY: 'auto', padding: 8, background: '#fff' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8 }}>
              {items.map((item) => {
                const isSelected = item.resource_id === selectedId
                return (
                  <div
                    key={item.resource_id}
                    onClick={() => { setSelectedId(item.resource_id); setMode('view') }}
                    style={{ borderRadius: 8, border: isSelected ? '2px solid #faad14' : '1px solid #e5e7eb', padding: 8, cursor: 'pointer', background: isSelected ? '#fffbe6' : '#fff', display: 'flex', flexDirection: 'column' }}
                  >
                    <Space size={6} style={{ marginBottom: 4 }}>
                      <DatabaseOutlined style={{ color: '#faad14' }} />
                      <Tooltip title={item.name}><Typography.Text strong style={{ fontSize: 13 }}>{item.name}</Typography.Text></Tooltip>
                    </Space>
                    <Space size={4} style={{ marginBottom: 4 }}>
                      {item.system && <Tag color="orange" style={{ fontSize: 10 }}>{item.system}</Tag>}
                      {item.type && <Tag style={{ fontSize: 10 }}>{DATA_TYPE_LABELS[item.type] || item.type}</Tag>}
                    </Space>
                    <div style={{ fontSize: 11, color: '#6b7280' }}>{item.location || item.description || '暂无描述'}</div>
                    <div style={{ marginTop: 'auto', textAlign: 'right', paddingTop: 4 }}>
                      <Popconfirm title="确认删除？" onConfirm={(e) => { e?.stopPropagation(); handleDelete(item) }} onCancel={(e) => e?.stopPropagation()}>
                        <Typography.Text type="secondary" style={{ fontSize: 11, color: '#f97316' }} onClick={(e) => e.stopPropagation()}>删除</Typography.Text>
                      </Popconfirm>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          <div style={{ width: 320, borderLeft: '1px solid #f3f4f6', paddingLeft: 16, overflowY: 'auto' }}>
            <Typography.Title level={5} style={{ margin: 0, marginBottom: 12 }}>详情</Typography.Title>
            {(selectedItem || isCreateMode) && (
              <Card size="small" bordered={false}>
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <Space size={8}>
                      {isViewMode && selectedItem && <Tag color="blue" style={{ cursor: 'pointer' }} onClick={handleEditClick}>编辑</Tag>}
                      {(isEditMode || isCreateMode) && (
                        <>
                          <Tag color="default" style={{ cursor: 'pointer' }} onClick={handleCancelEdit}>取消</Tag>
                          <Tag color="blue" style={{ cursor: 'pointer' }} onClick={handleSubmit}>保存</Tag>
                        </>
                      )}
                    </Space>
                  </div>
                  <Divider style={{ margin: '8px 0' }} />
                  <Form form={form} layout="vertical" disabled={isViewMode && !isCreateMode}>
                    <Form.Item label="名称" name="name" rules={[{ required: true, message: '请输入名称' }]}><Input /></Form.Item>
                    <Form.Item label="所属系统" name="system" rules={[{ required: true, message: '请选择系统' }]}>
                      <Select placeholder="选择系统" allowClear>
                        <Select.Option value="admin">admin</Select.Option>
                        <Select.Option value="owner-center">owner-center</Select.Option>
                        <Select.Option value="pay-center">pay-center</Select.Option>
                      </Select>
                    </Form.Item>
                    <Form.Item label="类型" name="type" rules={[{ required: true, message: '请选择类型' }]}>
                      <Select placeholder="选择类型" allowClear>
                        <Select.Option value="table">库表</Select.Option>
                        <Select.Option value="redis">Redis</Select.Option>
                      </Select>
                    </Form.Item>
                    <Form.Item label="物理位置" name="location"><Input placeholder="如 member_db.user_card" /></Form.Item>
                    <Form.Item label="描述" name="description"><Input.TextArea rows={3} /></Form.Item>
                  </Form>
                </Space>
              </Card>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Pagination size="small" current={page} pageSize={pageSize} total={total} showSizeChanger onChange={(p, ps) => { setPage(p); setPageSize(ps) }} />
        </div>
      </div>
    </div>
  )
}

// ============ 主页面 ============

const ResourceLibraryPage: React.FC = () => {
  const searchParams = new URLSearchParams(window.location.search)
  const tabFromUrl = searchParams.get('tab')
  const validTabs = ['business', 'step', 'implementation', 'resource']
  const initialTab = tabFromUrl && validTabs.includes(tabFromUrl) ? tabFromUrl : 'business'
  const [activeTab, setActiveTab] = useState<string>(initialTab)

  return (
    <div className="resource-library-container">
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
        <Tabs
          className="custom-tabs"
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            { key: 'business', label: <span><BranchesOutlined /> 业务流程</span>, children: <BusinessTab /> },
            { key: 'step', label: <span><NodeIndexOutlined /> 业务步骤</span>, children: <StepTab /> },
            { key: 'implementation', label: <span><CodeOutlined /> 实现单元</span>, children: <ImplementationTab /> },
            { key: 'resource', label: <span><DatabaseOutlined /> 数据资源</span>, children: <DataResourceTab /> },
          ]}
        />
      </div>
    </div>
  )
}

export default ResourceLibraryPage

import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Typography,
  Form,
  Input,
  Select,
  Button,
  Space,
  Popconfirm,
  Tag,
  Pagination,
  Divider,
  Badge,
  Descriptions,
} from 'antd'
import {
  BranchesOutlined,
  SearchOutlined,
  PlusOutlined,
  LeftOutlined,
  RightOutlined,
  EditOutlined,
  DeleteOutlined,
} from '@ant-design/icons'

import '../styles/ResourceLibraryPage.css'
import { showSuccess, showError } from '../utils/message'

import {
  BusinessNode,
  listBusinessesPaged,
  createBusiness,
  updateBusiness,
  deleteBusiness,
  getBusinessGroupStats,
  BusinessGroupStats,
  getChannelOptions,
} from '../api/resourceNodes'

import ResourceSidebar, { SidebarGroup, buildSingleLevelGroups } from '../components/ResourceSidebar'

interface BusinessFormValues {
  name: string
  channel?: string
  description?: string
  entrypoints?: string
}

const BusinessProcessPage: React.FC = () => {
  const [items, setItems] = useState<BusinessNode[]>([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [filterKeyword, setFilterKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [total, setTotal] = useState(0)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [mode, setMode] = useState<'view' | 'edit' | 'create'>('view')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [form] = Form.useForm<BusinessFormValues>()

  const [groupStats, setGroupStats] = useState<BusinessGroupStats | null>(null)
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null)
  const [groupLoading, setGroupLoading] = useState(false)
  const [channelOptions, setChannelOptions] = useState<string[]>([])

  const fetchGroupStats = useCallback(async () => {
    setGroupLoading(true)
    try {
      const stats = await getBusinessGroupStats()
      setGroupStats(stats)
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
      if (data.items.length === 0) {
        setSelectedId(null)
        setDrawerOpen(false)
      } else if (selectedId && !data.items.some((b) => b.process_id === selectedId)) {
        setSelectedId(null)
        setDrawerOpen(false)
      }
    } catch (e) {
      showError('加载列表失败')
    } finally {
      setLoading(false)
    }
  }, [keyword, page, pageSize, selectedGroup, selectedId])

  useEffect(() => { fetchGroupStats() }, [fetchGroupStats])
  useEffect(() => { fetchList() }, [fetchList])

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

  const handleSearch = () => {
    setKeyword(filterKeyword)
    setPage(1)
  }

  const handleReset = () => {
    setFilterKeyword('')
    setKeyword('')
    setPage(1)
  }

  const handleStartCreate = () => {
    setMode('create')
    setSelectedId(null)
    setDrawerOpen(true)
    form.resetFields()
  }

  const handleCardClick = (id: string) => {
    setSelectedId(id)
    setMode('view')
    setDrawerOpen(true)
  }

  const handlePrevious = () => {
    const currentIndex = items.findIndex((item) => item.process_id === selectedId)
    if (currentIndex > 0) {
      const prevItem = items[currentIndex - 1]
      setSelectedId(prevItem.process_id)
      setMode('view')
    }
  }

  const handleNext = () => {
    const currentIndex = items.findIndex((item) => item.process_id === selectedId)
    if (currentIndex < items.length - 1) {
      const nextItem = items[currentIndex + 1]
      setSelectedId(nextItem.process_id)
      setMode('view')
    }
  }

  const currentIndex = items.findIndex((item) => item.process_id === selectedId)
  const hasPrevious = currentIndex > 0
  const hasNext = currentIndex < items.length - 1

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
      setDrawerOpen(false)
      setMode('view')
      setSelectedId(null)
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

  const handleDeleteFromDrawer = async () => {
    if (!selectedItem) return
    try {
      await deleteBusiness(selectedItem.process_id)
      showSuccess('删除成功')
      setDrawerOpen(false)
      setSelectedId(null)
      fetchList()
      fetchGroupStats()
    } catch (e) {
      showError('删除失败')
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
          <Input
            allowClear
            placeholder="搜索业务..."
            prefix={<SearchOutlined style={{ color: '#9ca3af' }} />}
            value={filterKeyword}
            onChange={(e) => setFilterKeyword(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 240 }}
          />
          <Space>
            <Button type="primary" onClick={handleSearch}>查询</Button>
            <Button onClick={handleReset}>重置</Button>
            <Button icon={<PlusOutlined />} onClick={handleStartCreate}>新增</Button>
          </Space>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Space>
            <Typography.Title level={5} style={{ margin: 0 }}>{groupTitle}</Typography.Title>
            <Badge count={total} style={{ backgroundColor: '#1d4ed8' }} overflowCount={999} showZero />
          </Space>
        </div>

        <div style={{ flex: 1, minHeight: 0, display: 'flex', gap: 16, overflow: 'hidden' }}>
          <div style={{ 
            width: drawerOpen ? 'calc(100% - 716px)' : '100%',
            borderRadius: 8, 
            border: '1px solid #e5e7eb', 
            overflowY: 'auto', 
            padding: 8, 
            background: '#fff',
            transition: 'width 0.3s cubic-bezier(0.4, 0, 0.2, 1)'
          }}>
            <div style={{ display: 'grid', gridTemplateColumns: drawerOpen ? 'repeat(3, minmax(0, 1fr))' : 'repeat(4, minmax(0, 1fr))', gap: 8 }}>
              {items.map((item) => {
                const isSelected = item.process_id === selectedId
                return (
                  <div
                    key={item.process_id}
                    onClick={() => handleCardClick(item.process_id)}
                    style={{
                      borderRadius: 8,
                      border: isSelected ? '2px solid #2563eb' : '1px solid #e5e7eb',
                      padding: 8,
                      cursor: 'pointer',
                      background: isSelected ? '#eff6ff' : '#fff',
                      display: 'flex',
                      flexDirection: 'column',
                      transition: 'all 0.2s',
                    }}
                  >
                    <div style={{ display: 'flex', gap: 6, marginBottom: 4 }}>
                      <BranchesOutlined style={{ color: '#2563eb', flexShrink: 0, marginTop: 2 }} />
                      <Typography.Text strong style={{ 
                        fontSize: 13, 
                        overflow: 'hidden', 
                        textOverflow: 'ellipsis', 
                        display: '-webkit-box', 
                        WebkitLineClamp: 2, 
                        WebkitBoxOrient: 'vertical',
                        wordBreak: 'break-all',
                        flex: 1
                      }}>{item.name}</Typography.Text>
                    </div>
                    {item.channel && <div style={{ wordBreak: 'break-word' }}><Tag color="blue" style={{ fontSize: 11, marginBottom: 4 }}>{item.channel}</Tag></div>}
                    <div style={{ fontSize: 11, color: '#6b7280', overflow: 'hidden', textOverflow: 'ellipsis', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>{item.description || '暂无描述'}</div>
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

          {drawerOpen && (selectedItem || isCreateMode) && (
            <div style={{ width: 700, borderRadius: 8, border: '1px solid #e5e7eb', background: '#fff', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <div style={{ padding: '16px 24px', borderBottom: '1px solid #f0f0f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography.Title level={5} style={{ margin: 0 }}>
                  {isCreateMode ? '新增业务流程' : '业务流程详情'}
                </Typography.Title>
                <Space>
                  <Button size="small" icon={<LeftOutlined />} disabled={!hasPrevious} onClick={handlePrevious}>上一个</Button>
                  <Button size="small" disabled={!hasNext} onClick={handleNext}>下一个 <RightOutlined /></Button>
                </Space>
              </div>
              <div style={{ flex: 1, padding: 24, overflowY: 'auto' }}>
                {isViewMode && selectedItem ? (
                  <Descriptions column={1} labelStyle={{ width: 100, fontWeight: 500, color: '#374151' }} contentStyle={{ color: '#1f2937' }}>
                    <Descriptions.Item label="名称">{selectedItem.name}</Descriptions.Item>
                    <Descriptions.Item label="渠道">{selectedItem.channel || '-'}</Descriptions.Item>
                    <Descriptions.Item label="触发场景">
                      <div style={{ whiteSpace: 'pre-wrap' }}>{selectedItem.entrypoints || '-'}</div>
                    </Descriptions.Item>
                    <Descriptions.Item label="描述">
                      <div style={{ whiteSpace: 'pre-wrap' }}>{selectedItem.description || '-'}</div>
                    </Descriptions.Item>
                  </Descriptions>
                ) : (
                  <Form form={form} layout="vertical">
                    <Form.Item label="名称" name="name" rules={[{ required: true, message: '请输入名称' }]}>
                      <Input placeholder="请输入业务流程名称" />
                    </Form.Item>
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
                    <Form.Item label="触发场景" name="entrypoints">
                      <Input.TextArea rows={3} placeholder="请输入触发该业务流程的场景" />
                    </Form.Item>
                    <Form.Item label="描述" name="description">
                      <Input.TextArea rows={4} placeholder="请输入业务流程描述" />
                    </Form.Item>
                  </Form>
                )}
              </div>
              <div style={{ padding: '12px 24px', borderTop: '1px solid #f0f0f0', display: 'flex', justifyContent: 'space-between' }}>
                <Space>
                  {isViewMode && selectedItem && (
                    <>
                      <Button icon={<EditOutlined />} onClick={handleEditClick}>编辑</Button>
                      <Popconfirm title="确认删除？" description="删除后将无法恢复" onConfirm={handleDeleteFromDrawer}>
                        <Button danger icon={<DeleteOutlined />}>删除</Button>
                      </Popconfirm>
                    </>
                  )}
                </Space>
                <Space>
                  {(isEditMode || isCreateMode) && (
                    <>
                      <Button onClick={handleCancelEdit}>取消</Button>
                      <Button type="primary" onClick={handleSubmit}>保存</Button>
                    </>
                  )}
                  {isViewMode && <Button onClick={() => setDrawerOpen(false)}>关闭</Button>}
                </Space>
              </div>
            </div>
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Pagination size="small" current={page} pageSize={pageSize} total={total} showSizeChanger onChange={(p, ps) => { setPage(p); setPageSize(ps) }} />
        </div>
      </div>
    </div>
  )
}

export default BusinessProcessPage

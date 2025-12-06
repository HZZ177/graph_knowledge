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
  Badge,
  Descriptions,
} from 'antd'
import {
  CodeOutlined,
  SearchOutlined,
  PlusOutlined,
  ImportOutlined,
  LeftOutlined,
  RightOutlined,
  EditOutlined,
  DeleteOutlined,
} from '@ant-design/icons'

import '../styles/ResourceLibraryPage.css'
import { showSuccess, showError } from '../utils/message'
import { IMPL_TYPE_LABELS } from '../constants/resourceConstants'

import {
  ImplementationNode,
  ImplementationCreatePayload,
  listImplementationsPaged,
  createImplementation,
  updateImplementation,
  deleteImplementation,
  batchCreateImplementations,
  getImplementationGroupStats,
  ImplementationGroupStats,
} from '../api/resourceNodes'

import ResourceSidebar, { SidebarGroup, buildTwoLevelGroups } from '../components/ResourceSidebar'
import OpenAPIImportModal from '../components/OpenAPIImportModal'

interface ImplFormValues {
  name: string
  type?: string
  system?: string
  description?: string
  code_ref?: string
}

const ImplementationLibraryPage: React.FC = () => {
  const [items, setItems] = useState<ImplementationNode[]>([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [filterKeyword, setFilterKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [total, setTotal] = useState(0)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [mode, setMode] = useState<'view' | 'edit' | 'create'>('view')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [form] = Form.useForm<ImplFormValues>()

  const [groupStats, setGroupStats] = useState<ImplementationGroupStats | null>(null)
  const [selectedSystem, setSelectedSystem] = useState<string | null>(null)
  const [selectedType, setSelectedType] = useState<string | null>(null)
  const [expandedKeys, setExpandedKeys] = useState<string[]>([])
  const [groupLoading, setGroupLoading] = useState(false)
  const [systemOptions, setSystemOptions] = useState<string[]>([])
  const [importModalOpen, setImportModalOpen] = useState(false)

  const fetchGroupStats = useCallback(async () => {
    setGroupLoading(true)
    try {
      const stats = await getImplementationGroupStats()
      setGroupStats(stats)
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
      if (data.items.length === 0) {
        setSelectedId(null)
        setDrawerOpen(false)
      } else if (selectedId && !data.items.some((i) => i.impl_id === selectedId)) {
        setSelectedId(null)
        setDrawerOpen(false)
      }
    } catch (e) {
      showError('加载列表失败')
    } finally {
      setLoading(false)
    }
  }, [keyword, page, pageSize, selectedSystem, selectedType, selectedId])

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
    return buildTwoLevelGroups(groupStats.by_system, groupStats.by_type, { '': '其他' }, IMPL_TYPE_LABELS, groupStats.by_system_type)
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

  const handleSearch = () => {
    setKeyword(filterKeyword)
    setPage(1)
  }

  const handleReset = () => {
    setFilterKeyword('')
    setKeyword('')
    setPage(1)
  }

  const handleStartCreate = () => { setMode('create'); setSelectedId(null); setDrawerOpen(true); form.resetFields() }
  const handleEditClick = () => { if (selectedItem) setMode('edit') }

  const handleCardClick = (id: string) => {
    setSelectedId(id)
    setMode('view')
    setDrawerOpen(true)
  }

  const handlePrevious = () => {
    const currentIndex = items.findIndex((item) => item.impl_id === selectedId)
    if (currentIndex > 0) {
      setSelectedId(items[currentIndex - 1].impl_id)
      setMode('view')
    }
  }

  const handleNext = () => {
    const currentIndex = items.findIndex((item) => item.impl_id === selectedId)
    if (currentIndex < items.length - 1) {
      setSelectedId(items[currentIndex + 1].impl_id)
      setMode('view')
    }
  }

  const currentIndex = items.findIndex((item) => item.impl_id === selectedId)
  const hasPrevious = currentIndex > 0
  const hasNext = currentIndex < items.length - 1

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
      setDrawerOpen(false)
      setMode('view')
      setSelectedId(null)
    } else if (isEditMode) {
      setMode('view')
      if (selectedItem) form.setFieldsValue({ name: selectedItem.name, type: selectedItem.type ?? undefined, system: selectedItem.system ?? undefined, description: selectedItem.description ?? undefined, code_ref: selectedItem.code_ref ?? undefined })
    }
  }

  const handleDeleteFromDrawer = async () => {
    if (!selectedItem) return
    try {
      await deleteImplementation(selectedItem.impl_id)
      showSuccess('删除成功')
      setDrawerOpen(false)
      setSelectedId(null)
      fetchList()
      fetchGroupStats()
    } catch (e) {
      showError('删除失败')
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

  const handleImport = async (payloads: ImplementationCreatePayload[]) => {
    try {
      const result = await batchCreateImplementations(payloads)
      showSuccess(`导入完成：成功 ${result.success_count} 条，跳过 ${result.skip_count} 条`)
      fetchList()
      fetchGroupStats()
    } catch (e) {
      showError('导入失败')
      throw e
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
          <Input
            allowClear
            placeholder="搜索实现..."
            prefix={<SearchOutlined style={{ color: '#9ca3af' }} />}
            value={filterKeyword}
            onChange={(e) => setFilterKeyword(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 240 }}
          />
          <Space>
            <Button type="primary" onClick={handleSearch}>查询</Button>
            <Button onClick={handleReset}>重置</Button>
            <Button icon={<ImportOutlined />} onClick={() => setImportModalOpen(true)}>导入</Button>
            <Button icon={<PlusOutlined />} onClick={handleStartCreate}>新增</Button>
          </Space>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Space>
            <Typography.Title level={5} style={{ margin: 0 }}>{groupTitle}</Typography.Title>
            <Badge count={total} style={{ backgroundColor: '#7c3aed' }} overflowCount={999} showZero />
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
                const isSelected = item.impl_id === selectedId
                return (
                  <div
                    key={item.impl_id}
                    onClick={() => handleCardClick(item.impl_id)}
                    style={{
                      borderRadius: 8,
                      border: isSelected ? '2px solid #7c3aed' : '1px solid #e5e7eb',
                      padding: 8,
                      cursor: 'pointer',
                      background: isSelected ? '#f5f3ff' : '#fff',
                      display: 'flex',
                      flexDirection: 'column',
                      transition: 'all 0.2s',
                    }}
                  >
                    <div style={{ display: 'flex', gap: 6, marginBottom: 4 }}>
                      <CodeOutlined style={{ color: '#7c3aed', flexShrink: 0, marginTop: 2 }} />
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
                    <Space size={4} style={{ marginBottom: 4, flexWrap: 'wrap' }}>
                      {item.system && <Tag color="purple" style={{ fontSize: 10 }}>{item.system}</Tag>}
                      {item.type && <Tag style={{ fontSize: 10 }}>{IMPL_TYPE_LABELS[item.type] || item.type}</Tag>}
                    </Space>
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
                  {isCreateMode ? '新增实现单元' : '实现单元详情'}
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
                    <Descriptions.Item label="所属系统">{selectedItem.system || '-'}</Descriptions.Item>
                    <Descriptions.Item label="类型">{selectedItem.type ? (IMPL_TYPE_LABELS[selectedItem.type] || selectedItem.type) : '-'}</Descriptions.Item>
                    <Descriptions.Item label="代码引用">
                      <code style={{ padding: '2px 6px', background: '#f3f4f6', borderRadius: 4, fontSize: 12 }}>{selectedItem.code_ref || '-'}</code>
                    </Descriptions.Item>
                    <Descriptions.Item label="描述">
                      <div style={{ whiteSpace: 'pre-wrap' }}>{selectedItem.description || '-'}</div>
                    </Descriptions.Item>
                  </Descriptions>
                ) : (
                  <Form form={form} layout="vertical">
                    <Form.Item label="名称" name="name" rules={[{ required: true, message: '请输入名称' }]}>
                      <Input placeholder="请输入实现单元名称" />
                    </Form.Item>
                    <Form.Item label="所属系统" name="system" rules={[{ required: true, message: '请选择系统' }]}>
                      <Select placeholder="选择系统" allowClear>
                        <Select.Option value="admin-vehicle-owner">admin-vehicle-owner</Select.Option>
                        <Select.Option value="owner-center">owner-center</Select.Option>
                        <Select.Option value="vehicle-pay-center">vehicle-pay-center</Select.Option>
                      </Select>
                    </Form.Item>
                    <Form.Item label="类型" name="type" rules={[{ required: true, message: '请选择类型' }]}>
                      <Select placeholder="选择类型" allowClear>
                        <Select.Option value="api">接口</Select.Option>
                        <Select.Option value="function">内部方法</Select.Option>
                        <Select.Option value="job">定时任务</Select.Option>
                      </Select>
                    </Form.Item>
                    <Form.Item label="代码引用" name="code_ref">
                      <Input placeholder="如 com.example.Service#method" />
                    </Form.Item>
                    <Form.Item label="描述" name="description">
                      <Input.TextArea rows={4} placeholder="请输入实现单元描述" />
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

      <OpenAPIImportModal
        open={importModalOpen}
        onCancel={() => setImportModalOpen(false)}
        onImport={handleImport}
      />
    </div>
  )
}

export default ImplementationLibraryPage

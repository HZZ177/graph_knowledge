import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Card,
  Typography,
  Row,
  Col,
  Form,
  Input,
  Select,
  Button,
  Table,
  Tabs,
  Space,
  Popconfirm,
  Tag,
  Pagination,
  ConfigProvider,
  Avatar,
  Tooltip,
  Divider,
  Badge,
} from 'antd'
import {
  DatabaseOutlined,
  CodeOutlined,
  ApiOutlined,
  NodeIndexOutlined,
  BranchesOutlined,
  AppstoreOutlined,
  FileTextOutlined,
  SearchOutlined,
  PlusOutlined,
  GlobalOutlined,
  LaptopOutlined,
} from '@ant-design/icons'

import '../styles/ResourceLibraryPage.css'


import { showSuccess, showError } from '../utils/message'

import {
  DataResource,
  listDataResources,
  createDataResource,
  updateDataResource,
  deleteDataResource,
  listAccessChainsByNode,
  AccessChainItem,
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
} from '../api/resourceNodes'

const { Title } = Typography
const { Option } = Select

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
  const [pageSize, setPageSize] = useState(10)
  const [total, setTotal] = useState(0)
  const [selectedBusinessId, setSelectedBusinessId] = useState<string | null>(null)
  const [mode, setMode] = useState<'view' | 'edit' | 'create'>('view')
  const [form] = Form.useForm<BusinessFormValues>()

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listBusinessesPaged(keyword, page, pageSize)
      setItems(data.items)
      setTotal(data.total)

      if (data.items.length > 0) {
        setSelectedBusinessId((prev) => {
          if (prev && data.items.some((b) => b.process_id === prev)) {
            return prev
          }
          return data.items[0].process_id
        })
      } else {
        setSelectedBusinessId(null)
      }
    } catch (e) {
      showError('加载流程列表失败')
    } finally {
      setLoading(false)
    }
  }, [keyword, page, pageSize])

  useEffect(() => {
    fetchList()
  }, [fetchList])

  const selectedBusiness = useMemo(
    () => items.find((b) => b.process_id === selectedBusinessId) || null,
    [items, selectedBusinessId],
  )

  const isCreateMode = mode === 'create'
  const isEditMode = mode === 'edit'
  const isViewMode = mode === 'view'

  useEffect(() => {
    if (!selectedBusiness || isCreateMode) return

    form.setFieldsValue({
      name: selectedBusiness.name,
      channel: selectedBusiness.channel ?? undefined,
      description: selectedBusiness.description ?? undefined,
      entrypoints: selectedBusiness.entrypoints ?? undefined,
    })
  }, [selectedBusiness, isCreateMode, form])

  const handleStartCreate = () => {
    setMode('create')
    setSelectedBusinessId(null)
    form.resetFields()
  }

  const handleEditClick = () => {
    if (!selectedBusiness) return
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
      } else if (selectedBusiness) {
        await updateBusiness(selectedBusiness.process_id, {
          name: values.name,
          channel: values.channel ?? null,
          description: values.description ?? null,
          entrypoints: values.entrypoints ?? null,
        })
        showSuccess('保存成功')
      }
      setMode('view')
      fetchList()
    } catch (e: any) {
      if (e?.errorFields) return
      showError('保存失败')
    }
  }

  const handleCancelEdit = () => {
    if (isCreateMode) {
      setMode('view')
      if (items.length > 0) {
        setSelectedBusinessId(items[0].process_id)
      }
    } else if (isEditMode) {
      setMode('view')
      if (selectedBusiness) {
        form.setFieldsValue({
          name: selectedBusiness.name,
          channel: selectedBusiness.channel ?? undefined,
          description: selectedBusiness.description ?? undefined,
          entrypoints: selectedBusiness.entrypoints ?? undefined,
        })
      }
    }
  }

  const handleDelete = async (item: BusinessNode) => {
    try {
      await deleteBusiness(item.process_id)
      showSuccess('删除成功')
      if (selectedBusinessId === item.process_id) {
        setSelectedBusinessId(null)
      }
      fetchList()
    } catch (e) {
      showError('删除失败')
    }
  }

  return (
    <div style={{ display: 'flex', height: '100%', gap: 16 }}>
      {/* 左侧：业务流程列表 */}
      <div
        style={{
          flex: 1.8,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          overflow: 'hidden',
        }}
      >
        <div className="toolbar-container" style={{ marginBottom: 4 }}>
          <Input.Search
            allowClear
            placeholder="按名称或流程ID搜索..."
            prefix={<SearchOutlined style={{ color: '#9ca3af' }} />}
            onSearch={(val) => {
              setKeyword(val)
              setPage(1)
            }}
            style={{ width: 320 }}
          />
          <Space>
            <Button onClick={fetchList}>刷新</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleStartCreate}>
              新建流程
            </Button>
          </Space>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Space>
            <Typography.Title level={5} style={{ margin: 0 }}>
              业务流程列表
            </Typography.Title>
            <Badge
              count={total}
              style={{ backgroundColor: '#1d4ed8' }}
              overflowCount={999}
              showZero
            />
          </Space>
        </div>

        <div
          style={{
            flex: 1,
            minHeight: 0,
            borderRadius: 8,
            border: '1px solid #e5e7eb',
            overflowY: 'auto',
            overflowX: 'hidden',
            padding: 8,
            background: '#ffffff',
          }}
        >
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
              gap: 8,
            }}
          >
            {items.map((item) => {
              const isSelected = item.process_id === selectedBusinessId

              return (
                <div
                  key={item.process_id}
                  onClick={() => {
                    setSelectedBusinessId(item.process_id)
                    setMode('view')
                  }}
                  style={{
                    borderRadius: 8,
                    border: isSelected ? '2px solid #2563eb' : '1px solid #e5e7eb',
                    padding: 8,
                    cursor: 'pointer',
                    background: isSelected ? '#eff6ff' : '#ffffff',
                    boxShadow: isSelected
                      ? '0 0 0 1px rgba(37, 99, 235, 0.25)'
                      : '0 1px 2px rgba(15,23,42,0.03)',
                    transition:
                      'border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease',
                    display: 'flex',
                    flexDirection: 'column',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: 4,
                    }}
                  >
                    <Space size={6}>
                      <span style={{ color: '#2563eb' }}>
                        <BranchesOutlined />
                      </span>
                      <Tooltip title={item.name}>
                        <Typography.Text
                          strong
                          style={{
                            fontSize: 13,
                            wordBreak: 'break-all',
                            whiteSpace: 'normal',
                          }}
                        >
                          {item.name}
                        </Typography.Text>
                      </Tooltip>
                    </Space>
                    <Space size={4}>
                      {item.channel && (
                        <Tag color="blue" style={{ fontSize: 11 }}>
                          {item.channel}
                        </Tag>
                      )}
                    </Space>
                  </div>

                  <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 4 }}>
                    <div>流程ID: {item.process_id}</div>
                    {item.entrypoints && (
                      <div
                        style={{
                          marginTop: 2,
                          display: '-webkit-box',
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        入口: {item.entrypoints}
                      </div>
                    )}
                  </div>

                  <div
                    style={{
                      fontSize: 11,
                      color: '#6b7280',
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                    title={item.description || ''}
                  >
                    {item.description || '暂无描述'}
                  </div>

                  <div style={{ marginTop: 'auto', textAlign: 'right', paddingTop: 4 }}>
                    <Popconfirm
                      title="确认删除该流程？"
                      onConfirm={(e) => {
                        e?.stopPropagation()
                        handleDelete(item)
                      }}
                      onCancel={(e) => e?.stopPropagation()}
                      okText="删除"
                      cancelText="取消"
                    >
                      <Typography.Text
                        type="secondary"
                        style={{ fontSize: 11, color: '#f97316' }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        删除
                      </Typography.Text>
                    </Popconfirm>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <div
          style={{
            marginTop: 8,
            display: 'flex',
            justifyContent: 'flex-end',
          }}
        >
          <Pagination
            size="small"
            current={page}
            pageSize={pageSize}
            total={total}
            showSizeChanger
            onChange={(p, ps) => {
              setPage(p)
              setPageSize(ps)
            }}
          />
        </div>
      </div>

      {/* 右侧：流程详情 */}
      <div
        style={{
          width: 360,
          borderLeft: '1px solid #f3f4f6',
          paddingLeft: 16,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          minHeight: 0,
          maxHeight: '100%',
          overflowY: 'auto',
          overflowX: 'hidden',
        }}
      >
        <Typography.Title level={5} style={{ margin: 0 }}>
          流程详情
        </Typography.Title>

        {!selectedBusiness && !isCreateMode && (
          <Card size="small" bordered={false} style={{ background: '#f9fafb' }}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              在左侧列表中点击任意流程，这里将展示该流程的基础信息，
              包括名称、渠道、触发场景与描述。
            </Typography.Text>
          </Card>
        )}

        {(selectedBusiness || isCreateMode) && (
          <Card size="small" bordered={false}>
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <Space size={6}>
                  <span style={{ color: '#2563eb' }}>
                    <BranchesOutlined />
                  </span>
                  <Typography.Text
                    strong
                    style={{
                      whiteSpace: 'normal',
                      wordBreak: 'break-word',
                    }}
                  >
                    {isCreateMode
                      ? '新建流程'
                      : selectedBusiness?.name || '未选择流程'}
                  </Typography.Text>
                </Space>
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <Space size={8}>
                    {isViewMode && selectedBusiness && <Tag>详情</Tag>}
                    {isViewMode && selectedBusiness && (
                      <Tag
                        color="blue"
                        style={{ cursor: 'pointer' }}
                        onClick={handleEditClick}
                      >
                        编辑
                      </Tag>
                    )}
                    {(isEditMode || isCreateMode) && (
                      <Space size={8}>
                        <Tag
                          color="default"
                          style={{ cursor: 'pointer' }}
                          onClick={handleCancelEdit}
                        >
                          取消
                        </Tag>
                        <Tag
                          color="blue"
                          style={{ cursor: 'pointer' }}
                          onClick={handleSubmit}
                        >
                          保存
                        </Tag>
                      </Space>
                    )}
                  </Space>
                </div>
              </div>

              <Divider style={{ margin: '8px 0' }} />

              <Form
                form={form}
                layout="vertical"
                disabled={isViewMode && !isCreateMode}
              >
                <Form.Item
                  label="名称"
                  name="name"
                  rules={[{ required: true, message: '请输入名称' }]}
                >
                  <Input />
                </Form.Item>
                <Form.Item label="渠道" name="channel">
                  <Input />
                </Form.Item>
                <Form.Item label="业务触发场景" name="entrypoints">
                  <Input.TextArea
                    rows={2}
                    placeholder="描述用户如何触发该业务流程，如：用户在C端App点击开通月卡按钮"
                  />
                </Form.Item>
                <Form.Item label="描述" name="description">
                  <Input.TextArea rows={3} />
                </Form.Item>
              </Form>

              {isCreateMode && (
                <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                  新建模式下，这里只编辑流程本身的基础字段，
                  具体步骤与实现的编排建议在业务画布中维护。
                </Typography.Text>
              )}
            </Space>
          </Card>
        )}
      </div>
    </div>
  )
}

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
  const [pageSize, setPageSize] = useState(10)
  const [total, setTotal] = useState(0)
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null)
  const [mode, setMode] = useState<'view' | 'edit' | 'create'>('view')
  const [form] = Form.useForm<StepFormValues>()

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listStepsPaged(keyword, page, pageSize)
      setItems(data.items)
      setTotal(data.total)

      if (data.items.length > 0) {
        setSelectedStepId((prev) => {
          if (prev && data.items.some((s) => s.step_id === prev)) {
            return prev
          }
          return data.items[0].step_id
        })
      } else {
        setSelectedStepId(null)
      }
    } catch (e) {
      showError('加载步骤列表失败')
    } finally {
      setLoading(false)
    }
  }, [keyword, page, pageSize])

  useEffect(() => {
    fetchList()
  }, [fetchList])

  const selectedStep = useMemo(
    () => items.find((s) => s.step_id === selectedStepId) || null,
    [items, selectedStepId],
  )

  const isCreateMode = mode === 'create'
  const isEditMode = mode === 'edit'
  const isViewMode = mode === 'view'

  useEffect(() => {
    if (!selectedStep || isCreateMode) return

    form.setFieldsValue({
      name: selectedStep.name,
      description: selectedStep.description ?? undefined,
      step_type: selectedStep.step_type ?? undefined,
    })
  }, [selectedStep, isCreateMode, form])

  const handleStartCreate = () => {
    setMode('create')
    setSelectedStepId(null)
    form.resetFields()
  }

  const handleEditClick = () => {
    if (!selectedStep) return
    setMode('edit')
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      if (isCreateMode) {
        await createStep({
          name: values.name,
          description: values.description ?? null,
          step_type: values.step_type ?? null,
        })
        showSuccess('创建成功')
      } else if (selectedStep) {
        await updateStep(selectedStep.step_id, {
          name: values.name,
          description: values.description ?? null,
          step_type: values.step_type ?? null,
        })
        showSuccess('保存成功')
      }
      setMode('view')
      fetchList()
    } catch (e: any) {
      if (e?.errorFields) return
      showError('保存失败')
    }
  }

  const handleCancelEdit = () => {
    if (isCreateMode) {
      setMode('view')
      if (items.length > 0) {
        setSelectedStepId(items[0].step_id)
      }
    } else if (isEditMode) {
      setMode('view')
      if (selectedStep) {
        form.setFieldsValue({
          name: selectedStep.name,
          description: selectedStep.description ?? undefined,
          step_type: selectedStep.step_type ?? undefined,
        })
      }
    }
  }

  const handleDelete = async (item: StepNode) => {
    try {
      await deleteStep(item.step_id)
      showSuccess('删除成功')
      if (selectedStepId === item.step_id) {
        setSelectedStepId(null)
      }
      fetchList()
    } catch (e) {
      showError('删除失败')
    }
  }

  return (
    <div style={{ display: 'flex', height: '100%', gap: 16 }}>
      {/* 左侧：步骤列表 */}
      <div
        style={{
          flex: 1.8,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          overflow: 'hidden',
        }}
      >
        <div className="toolbar-container" style={{ marginBottom: 4 }}>
          <Input.Search
            allowClear
            placeholder="按名称或步骤ID搜索..."
            prefix={<SearchOutlined style={{ color: '#9ca3af' }} />}
            onSearch={(val) => {
              setKeyword(val)
              setPage(1)
            }}
            style={{ width: 320 }}
          />
          <Space>
            <Button onClick={fetchList}>刷新</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleStartCreate}>
              新建步骤
            </Button>
          </Space>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Space>
            <Typography.Title level={5} style={{ margin: 0 }}>
              业务步骤列表
            </Typography.Title>
            <Badge
              count={total}
              style={{ backgroundColor: '#1677ff' }}
              overflowCount={999}
              showZero
            />
          </Space>
        </div>

        <div
          style={{
            flex: 1,
            minHeight: 0,
            borderRadius: 8,
            border: '1px solid #e5e7eb',
            overflowY: 'auto',
            overflowX: 'hidden',
            padding: 8,
            background: '#ffffff',
          }}
        >
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
              gap: 8,
            }}
          >
            {items.map((item) => {
              const isSelected = item.step_id === selectedStepId

              return (
                <div
                  key={item.step_id}
                  onClick={() => {
                    setSelectedStepId(item.step_id)
                    setMode('view')
                  }}
                  style={{
                    borderRadius: 8,
                    border: isSelected ? '2px solid #1677ff' : '1px solid #e5e7eb',
                    padding: 8,
                    cursor: 'pointer',
                    background: isSelected ? '#eff6ff' : '#ffffff',
                    boxShadow: isSelected
                      ? '0 0 0 1px rgba(37, 99, 235, 0.25)'
                      : '0 1px 2px rgba(15,23,42,0.03)',
                    transition:
                      'border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease',
                    display: 'flex',
                    flexDirection: 'column',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: 4,
                    }}
                  >
                    <Space size={6}>
                      <span style={{ color: '#1677ff' }}>
                        <NodeIndexOutlined />
                      </span>
                      <Tooltip title={item.name}>
                        <Typography.Text
                          strong
                          style={{
                            fontSize: 13,
                            wordBreak: 'break-all',
                            whiteSpace: 'normal',
                          }}
                        >
                          {item.name}
                        </Typography.Text>
                      </Tooltip>
                    </Space>
                    <Space size={4}>
                      {item.step_type && (
                        <Tag color="green" style={{ fontSize: 11 }}>
                          {item.step_type}
                        </Tag>
                      )}
                    </Space>
                  </div>

                  <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 4 }}>
                    <div>步骤ID: {item.step_id}</div>
                  </div>

                  <div
                    style={{
                      fontSize: 11,
                      color: '#6b7280',
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                    title={item.description || ''}
                  >
                    {item.description || '暂无描述'}
                  </div>

                  <div style={{ marginTop: 'auto', textAlign: 'right', paddingTop: 4 }}>
                    <Popconfirm
                      title="确认删除该步骤？"
                      onConfirm={(e) => {
                        e?.stopPropagation()
                        handleDelete(item)
                      }}
                      onCancel={(e) => e?.stopPropagation()}
                      okText="删除"
                      cancelText="取消"
                    >
                      <Typography.Text
                        type="secondary"
                        style={{ fontSize: 11, color: '#f97316' }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        删除
                      </Typography.Text>
                    </Popconfirm>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <div
          style={{
            marginTop: 8,
            display: 'flex',
            justifyContent: 'flex-end',
          }}
        >
          <Pagination
            size="small"
            current={page}
            pageSize={pageSize}
            total={total}
            showSizeChanger
            onChange={(p, ps) => {
              setPage(p)
              setPageSize(ps)
            }}
          />
        </div>
      </div>

      {/* 右侧：步骤详情 */}
      <div
        style={{
          width: 360,
          borderLeft: '1px solid #f3f4f6',
          paddingLeft: 16,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          minHeight: 0,
          maxHeight: '100%',
          overflowY: 'auto',
          overflowX: 'hidden',
        }}
      >
        <Typography.Title level={5} style={{ margin: 0 }}>
          步骤详情
        </Typography.Title>

        {!selectedStep && !isCreateMode && (
          <Card size="small" bordered={false} style={{ background: '#f9fafb' }}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              在左侧列表中点击任意步骤，这里将展示该步骤的基础信息，
              包括名称、类型与描述。
            </Typography.Text>
          </Card>
        )}

        {(selectedStep || isCreateMode) && (
          <Card size="small" bordered={false}>
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <Space size={6}>
                  <span style={{ color: '#16a34a' }}>
                    <NodeIndexOutlined />
                  </span>
                  <Typography.Text
                    strong
                    style={{
                      whiteSpace: 'normal',
                      wordBreak: 'break-word',
                    }}
                  >
                    {isCreateMode
                      ? '新建步骤'
                      : selectedStep?.name || '未选择步骤'}
                  </Typography.Text>
                </Space>
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <Space size={8}>
                    {isViewMode && selectedStep && <Tag>详情</Tag>}
                    {isViewMode && selectedStep && (
                      <Tag
                        color="blue"
                        style={{ cursor: 'pointer' }}
                        onClick={handleEditClick}
                      >
                        编辑
                      </Tag>
                    )}
                    {(isEditMode || isCreateMode) && (
                      <Space size={8}>
                        <Tag
                          color="default"
                          style={{ cursor: 'pointer' }}
                          onClick={handleCancelEdit}
                        >
                          取消
                        </Tag>
                        <Tag
                          color="blue"
                          style={{ cursor: 'pointer' }}
                          onClick={handleSubmit}
                        >
                          保存
                        </Tag>
                      </Space>
                    )}
                  </Space>
                </div>
              </div>

              <Divider style={{ margin: '8px 0' }} />

              <Form
                form={form}
                layout="vertical"
                disabled={isViewMode && !isCreateMode}
              >
                <Form.Item
                  label="名称"
                  name="name"
                  rules={[{ required: true, message: '请输入名称' }]}
                >
                  <Input />
                </Form.Item>
                <Form.Item label="类型" name="step_type">
                  <Input />
                </Form.Item>
                <Form.Item label="描述" name="description">
                  <Input.TextArea rows={3} />
                </Form.Item>
              </Form>

              {isCreateMode && (
                <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                  新建模式下，这里只编辑步骤本身的基础字段，
                  与实现、数据资源的关系建议在业务画布或关系工作台中维护。
                </Typography.Text>
              )}
            </Space>
          </Card>
        )}
      </div>
    </div>
  )
}

interface ImplementationFormValues {
  name: string
  type?: string
  system?: string
  description?: string
  code_ref?: string
}

interface ImplStepRef {
  step_id: string
  step_name: string
  process_id?: string | null
  process_name?: string | null
}

interface ImplResourceRef {
  resource_id: string
  resource_name: string
  access_type?: string | null
  access_pattern?: string | null
}

const ImplementationTab: React.FC = () => {
  const [items, setItems] = useState<ImplementationNode[]>([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [total, setTotal] = useState(0)
  const [activeSystem, setActiveSystem] = useState<string>('all')
  const [selectedImplId, setSelectedImplId] = useState<string | null>(null)
  const [mode, setMode] = useState<'view' | 'edit' | 'create'>('view')
  const [relationsLoading, setRelationsLoading] = useState(false)
  const [accessChains, setAccessChains] = useState<AccessChainItem[]>([])
  const [form] = Form.useForm<ImplementationFormValues>()

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listImplementationsPaged(keyword, page, pageSize)
      setItems(data.items)
      setTotal(data.total)

      if (data.items.length > 0) {
        setSelectedImplId((prev) => {
          if (prev && data.items.some((impl) => impl.impl_id === prev)) {
            return prev
          }
          return data.items[0].impl_id
        })
      } else {
        setSelectedImplId(null)
        setAccessChains([])
      }
    } catch (e) {
      showError('加载实现列表失败')
    } finally {
      setLoading(false)
    }
  }, [keyword, page, pageSize])

  useEffect(() => {
    fetchList()
  }, [fetchList])

  const loadRelations = useCallback(async (implId: string) => {
    setRelationsLoading(true)
    try {
      const chains = await listAccessChainsByNode('impl', implId)
      setAccessChains(chains)
    } catch (e) {
      showError('加载实现关联关系失败')
      setAccessChains([])
    } finally {
      setRelationsLoading(false)
    }
  }, [])

  const systems = useMemo(() => {
    const set = new Set<string>()
    items.forEach((impl: ImplementationNode) => {
      if (impl.system) {
        set.add(impl.system)
      }
    })
    return Array.from(set).sort()
  }, [items])

  const filteredItems = useMemo(() => {
    if (activeSystem === 'all') return items
    return items.filter((impl) => impl.system === activeSystem)
  }, [items, activeSystem])

  const selectedImpl = useMemo(
    () => items.find((impl) => impl.impl_id === selectedImplId) || null,
    [items, selectedImplId],
  )

  const stepRefs: ImplStepRef[] = useMemo(() => {
    const map = new Map<string, ImplStepRef>()
    accessChains.forEach((c: AccessChainItem) => {
      if (c.step_id && !map.has(c.step_id)) {
        map.set(c.step_id, {
          step_id: c.step_id,
          step_name: c.step_name || c.step_id,
          process_id: c.process_id,
          process_name: c.process_name,
        })
      }
    })
    return Array.from(map.values())
  }, [accessChains])

  const resourceRefs: ImplResourceRef[] = useMemo(() => {
    const map = new Map<string, ImplResourceRef>()
    accessChains.forEach((c: AccessChainItem) => {
      const existing = map.get(c.resource_id)
      if (!existing) {
        map.set(c.resource_id, {
          resource_id: c.resource_id,
          resource_name: c.resource_name,
          access_type: c.access_type || null,
          access_pattern: c.access_pattern || null,
        })
      } else {
        if (!existing.access_type && c.access_type) {
          existing.access_type = c.access_type
        }
        if (!existing.access_pattern && c.access_pattern) {
          existing.access_pattern = c.access_pattern
        }
      }
    })
    return Array.from(map.values())
  }, [accessChains])

  const isCreateMode = mode === 'create'
  const isEditMode = mode === 'edit'
  const isViewMode = mode === 'view'

  useEffect(() => {
    if (!selectedImpl || isCreateMode) {
      return
    }

    form.setFieldsValue({
      name: selectedImpl.name,
      type: selectedImpl.type ?? undefined,
      system: selectedImpl.system ?? undefined,
      description: selectedImpl.description ?? undefined,
      code_ref: selectedImpl.code_ref ?? undefined,
    })
    loadRelations(selectedImpl.impl_id)
  }, [selectedImpl, isCreateMode, form, loadRelations])

  const handleStartCreate = () => {
    setMode('create')
    setSelectedImplId(null)
    form.resetFields()
  }

  const handleEditClick = () => {
    if (!selectedImpl) return
    setMode('edit')
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      if (isCreateMode) {
        await createImplementation({
          name: values.name,
          type: values.type ?? null,
          system: values.system ?? null,
          description: values.description ?? null,
          code_ref: values.code_ref ?? null,
        })
        showSuccess('创建成功')
      } else if (selectedImpl) {
        await updateImplementation(selectedImpl.impl_id, {
          name: values.name,
          type: values.type ?? null,
          system: values.system ?? null,
          description: values.description ?? null,
          code_ref: values.code_ref ?? null,
        })
        showSuccess('保存成功')
      }
      setMode('view')
      fetchList()
    } catch (e: any) {
      if (e?.errorFields) return
      showError('保存失败')
    }
  }

  const handleCancelEdit = () => {
    if (isCreateMode) {
      setMode('view')
      if (items.length > 0) {
        setSelectedImplId(items[0].impl_id)
      }
    } else if (isEditMode) {
      setMode('view')
      if (selectedImpl) {
        form.setFieldsValue({
          name: selectedImpl.name,
          type: selectedImpl.type ?? undefined,
          system: selectedImpl.system ?? undefined,
          description: selectedImpl.description ?? undefined,
          code_ref: selectedImpl.code_ref ?? undefined,
        })
      }
    }
  }

  const handleDelete = async (item: ImplementationNode) => {
    try {
      await deleteImplementation(item.impl_id)
      showSuccess('删除成功')
      if (selectedImplId === item.impl_id) {
        setSelectedImplId(null)
        setAccessChains([])
      }
      fetchList()
    } catch (e) {
      showError('删除失败')
    }
  }

  return (
    <div style={{ display: 'flex', height: '100%', gap: 16 }}>
      {/* 中间：实现节点画廊 + 筛选 */}
      <div
        style={{
          flex: 1.8,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          overflow: 'hidden',
        }}
      >
        <div className="toolbar-container" style={{ marginBottom: 4 }}>
          <Input.Search
            allowClear
            placeholder="按名称或实现ID搜索..."
            prefix={<SearchOutlined style={{ color: '#9ca3af' }} />}
            onSearch={(val) => {
              setKeyword(val)
              setPage(1)
            }}
            style={{ width: 320 }}
          />
          <Space>
            <Button onClick={fetchList}>刷新</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleStartCreate}>
              新建实现
            </Button>
          </Space>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Space>
            <Typography.Title level={5} style={{ margin: 0 }}>
              实现单元列表
            </Typography.Title>
            <Badge
              count={total}
              style={{ backgroundColor: '#52c41a' }}
              overflowCount={999}
              showZero
            />
          </Space>
          <Space>
            <Space size={4}>
              <span style={{ fontSize: 12 }}>按系统过滤:</span>
              <Select
                size="small"
                value={activeSystem}
                style={{ width: 180 }}
                onChange={(val) => setActiveSystem(val)}
              >
                <Select.Option value="all">全部系统</Select.Option>
                {systems.map((s) => (
                  <Select.Option key={s} value={s}>
                    {s}
                  </Select.Option>
                ))}
              </Select>
            </Space>
          </Space>
        </div>

        <div
          style={{
            flex: 1,
            minHeight: 0,
            borderRadius: 8,
            border: '1px solid #e5e7eb',
            overflowY: 'auto',
            overflowX: 'hidden',
            padding: 8,
            background: '#ffffff',
          }}
        >
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
              gap: 8,
            }}
          >
            {filteredItems.map((impl: ImplementationNode) => {
              const isSelected = impl.impl_id === selectedImplId

              return (
                <div
                  key={impl.impl_id}
                  onClick={() => {
                    setSelectedImplId(impl.impl_id)
                    setMode('view')
                  }}
                  style={{
                    borderRadius: 8,
                    border: isSelected ? '2px solid #52c41a' : '1px solid #e5e7eb',
                    padding: 8,
                    cursor: 'pointer',
                    background: isSelected ? '#f6ffed' : '#ffffff',
                    boxShadow: isSelected
                      ? '0 0 0 1px rgba(82, 196, 26, 0.25)'
                      : '0 1px 2px rgba(15,23,42,0.03)',
                    transition:
                      'border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease',
                    display: 'flex',
                    flexDirection: 'column',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: 4,
                    }}
                  >
                    <Space size={6}>
                      <span style={{ color: '#52c41a' }}>
                        <CodeOutlined />
                      </span>
                      <Tooltip title={impl.name}>
                        <Typography.Text
                          strong
                          style={{
                            fontSize: 13,
                            wordBreak: 'break-all',
                            whiteSpace: 'normal',
                          }}
                        >
                          {impl.name}
                        </Typography.Text>
                      </Tooltip>
                    </Space>
                    <Space size={4}>
                      {impl.system && (
                        <Tag color="geekblue" style={{ fontSize: 11 }}>
                          {impl.system}
                        </Tag>
                      )}
                      {impl.type && (
                        <Tag color="default" style={{ fontSize: 11 }}>
                          {impl.type}
                        </Tag>
                      )}
                    </Space>
                  </div>

                  <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 4 }}>
                    <div>实现ID: {impl.impl_id}</div>
                    {impl.code_ref && (
                      <div style={{ wordBreak: 'break-all', whiteSpace: 'normal' }}>
                        代码引用: {impl.code_ref}
                      </div>
                    )}
                  </div>

                  {impl.description && (
                    <div
                      style={{
                        fontSize: 11,
                        color: '#6b7280',
                        marginBottom: 4,
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {impl.description}
                    </div>
                  )}

                  <div style={{ marginTop: 'auto', textAlign: 'right', paddingTop: 4 }}>
                    <Popconfirm
                      title="确认删除该实现？"
                      onConfirm={(e) => {
                        e?.stopPropagation()
                        handleDelete(impl)
                      }}
                      onCancel={(e) => e?.stopPropagation()}
                      okText="删除"
                      cancelText="取消"
                    >
                      <Typography.Text
                        type="secondary"
                        style={{ fontSize: 11, color: '#f97316' }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        删除
                      </Typography.Text>
                    </Popconfirm>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <div
          style={{
            marginTop: 8,
            display: 'flex',
            justifyContent: 'flex-end',
          }}
        >
          <Pagination
            size="small"
            current={page}
            pageSize={pageSize}
            total={total}
            showSizeChanger
            onChange={(p, ps) => {
              setPage(p)
              setPageSize(ps)
            }}
          />
        </div>
      </div>

      {/* 右侧：实现详情 + 基础信息表单 + 关系只读视图 */}
      <div
        style={{
          width: 360,
          borderLeft: '1px solid #f3f4f6',
          paddingLeft: 16,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          minHeight: 0,
          maxHeight: '100%',
          overflowY: 'auto',
          overflowX: 'hidden',
        }}
      >
        <Typography.Title level={5} style={{ margin: 0 }}>
          实现详情与关系
        </Typography.Title>

        {!selectedImpl && !isCreateMode && (
          <Card size="small" bordered={false} style={{ background: '#f9fafb' }}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              在左侧列表中点击任意实现，
              这里将展示该实现的基础信息，以及它关联的步骤、流程和访问的数据资源。
            </Typography.Text>
          </Card>
        )}

        {(selectedImpl || isCreateMode) && (
          <Card size="small" bordered={false}>
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <Space size={6}>
                  <span style={{ color: '#ea580c' }}>
                    <CodeOutlined />
                  </span>
                  <Typography.Text
                    strong
                    style={{
                      whiteSpace: 'normal',
                      wordBreak: 'break-word',
                    }}
                  >
                    {isCreateMode
                      ? '新建实现'
                      : selectedImpl?.name || '未选择实现'}
                  </Typography.Text>
                </Space>
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <Space size={8}>
                    {isViewMode && selectedImpl && <Tag>详情</Tag>}
                    {isViewMode && selectedImpl && (
                      <Tag
                        color="blue"
                        style={{ cursor: 'pointer' }}
                        onClick={handleEditClick}
                      >
                        编辑
                      </Tag>
                    )}
                    {(isEditMode || isCreateMode) && (
                      <Space size={8}>
                        <Tag
                          color="default"
                          style={{ cursor: 'pointer' }}
                          onClick={handleCancelEdit}
                        >
                          取消
                        </Tag>
                        <Tag
                          color="blue"
                          style={{ cursor: 'pointer' }}
                          onClick={handleSubmit}
                        >
                          保存
                        </Tag>
                      </Space>
                    )}
                  </Space>
                </div>
              </div>

              <Divider style={{ margin: '8px 0' }} />

              <Form
                form={form}
                layout="vertical"
                disabled={isViewMode && !isCreateMode}
              >
                <Form.Item
                  label="名称"
                  name="name"
                  rules={[{ required: true, message: '请输入名称' }]}
                >
                  <Input />
                </Form.Item>
                <Form.Item label="类型" name="type">
                  <Input placeholder="例如 http_api / batch_job" />
                </Form.Item>
                <Form.Item label="系统" name="system">
                  <Input placeholder="例如 member-service" />
                </Form.Item>
                <Form.Item label="代码引用" name="code_ref">
                  <Input placeholder="例如 仓库路径或接口路径" />
                </Form.Item>
                <Form.Item label="描述" name="description">
                  <Input.TextArea rows={3} />
                </Form.Item>
              </Form>

              {!isCreateMode && selectedImpl && (
                <>
                  <Divider style={{ margin: '8px 0' }} />

                  <div>
                    <Space style={{ marginBottom: 4 }}>
                      <Typography.Text strong style={{ fontSize: 12 }}>
                        关联步骤 & 流程
                      </Typography.Text>
                      {relationsLoading && (
                        <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                          加载中...
                        </Typography.Text>
                      )}
                    </Space>
                    <div style={{ marginTop: 4, maxHeight: 130, overflowY: 'auto' }}>
                      {stepRefs.map((s: ImplStepRef) => (
                        <div
                          key={s.step_id + (s.process_id || '')}
                          style={{
                            fontSize: 11,
                            padding: 6,
                            borderRadius: 6,
                            border: '1px solid #e5e7eb',
                            marginBottom: 4,
                            background: '#f9fafb',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <Space size={4}>
                              <span style={{ color: '#16a34a' }}>
                                <NodeIndexOutlined />
                              </span>
                              <Typography.Text
                                style={{
                                  maxWidth: 190,
                                  whiteSpace: 'nowrap',
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  display: 'inline-block',
                                }}
                              >
                                {s.step_name}
                              </Typography.Text>
                            </Space>
                          </div>
                          <div>
                            <Typography.Text type="secondary">步骤ID:</Typography.Text>{' '}
                            {s.step_id}
                          </div>
                          {s.process_name && (
                            <div>
                              <Space size={4}>
                                <span style={{ color: '#2563eb' }}>
                                  <BranchesOutlined />
                                </span>
                                <Typography.Text
                                  style={{
                                    maxWidth: 190,
                                    whiteSpace: 'nowrap',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    display: 'inline-block',
                                  }}
                                >
                                  {s.process_name}（{s.process_id}）
                                </Typography.Text>
                              </Space>
                            </div>
                          )}
                        </div>
                      ))}
                      {stepRefs.length === 0 && !relationsLoading && (
                        <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                          当前未查询到该实现绑定的步骤关系。
                        </Typography.Text>
                      )}
                    </div>
                  </div>

                  <Divider style={{ margin: '8px 0' }} />

                  <div>
                    <Space style={{ marginBottom: 4 }}>
                      <Typography.Text strong style={{ fontSize: 12 }}>
                        访问的数据资源
                      </Typography.Text>
                    </Space>
                    <div style={{ marginTop: 4, maxHeight: 140, overflowY: 'auto' }}>
                      {resourceRefs.map((r: ImplResourceRef) => (
                        <div
                          key={r.resource_id}
                          style={{
                            fontSize: 11,
                            padding: 6,
                            borderRadius: 6,
                            border: '1px solid #e5e7eb',
                            marginBottom: 4,
                            background: '#f9fafb',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <Space size={4}>
                              <span style={{ color: '#7c3aed' }}>
                                <DatabaseOutlined />
                              </span>
                              <Typography.Text
                                style={{
                                  maxWidth: 190,
                                  whiteSpace: 'nowrap',
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  display: 'inline-block',
                                }}
                              >
                                {r.resource_name}
                              </Typography.Text>
                            </Space>
                            <Space size={4}>
                              {r.access_type && (
                                <Tag color={
                                  r.access_type === 'read'
                                    ? 'green'
                                    : r.access_type === 'write'
                                    ? 'red'
                                    : 'blue'
                                }>
                                  {r.access_type === 'read'
                                    ? '读'
                                    : r.access_type === 'write'
                                    ? '写'
                                    : '读/写'}
                                </Tag>
                              )}
                              {r.access_pattern && (
                                <Tag color="default" style={{ fontSize: 10 }}>
                                  {r.access_pattern}
                                </Tag>
                              )}
                            </Space>
                          </div>
                          <div>
                            <Typography.Text type="secondary">资源ID:</Typography.Text>{' '}
                            {r.resource_id}
                          </div>
                        </div>
                      ))}
                      {resourceRefs.length === 0 && !relationsLoading && (
                        <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                          当前未查询到该实现访问的数据资源。
                        </Typography.Text>
                      )}
                    </div>
                  </div>
                </>
              )}

              {isCreateMode && (
                <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                  新建模式下，这里只编辑实现本身的基础字段，
                  关联步骤与数据资源的关系建议在画布或专门的关系管理视图中维护。
                </Typography.Text>
              )}
            </Space>
          </Card>
        )}
      </div>
    </div>
  )
}

interface DataResourceFormValues {
  name: string
  type?: string
  system?: string
  location?: string
  description?: string
}

const DataResourceTab: React.FC = () => {
  const [form] = Form.useForm<DataResourceFormValues>()

  const [resources, setResources] = useState<DataResource[]>([])
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  const [keyword, setKeyword] = useState('')
  const [systemFilter, setSystemFilter] = useState<string | undefined>()

  const [selectedResourceId, setSelectedResourceId] = useState<string | null>(null)
  const [mode, setMode] = useState<'view' | 'edit' | 'create'>('view')

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listDataResources({
        page,
        page_size: pageSize,
        q: keyword || undefined,
        system: systemFilter,
      })
      setResources(data.items)
      setTotal(data.total)

      if (data.items.length > 0) {
        setSelectedResourceId((prev) => {
          if (prev && data.items.some((r) => r.resource_id === prev)) {
            return prev
          }
          return data.items[0].resource_id
        })
      } else {
        setSelectedResourceId(null)
      }
    } catch (e) {
      showError('加载数据资源列表失败')
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, keyword, systemFilter])

  useEffect(() => {
    fetchList()
  }, [fetchList])

  const selectedResource = useMemo(
    () => resources.find((r) => r.resource_id === selectedResourceId) || null,
    [resources, selectedResourceId],
  )

  const isCreateMode = mode === 'create'
  const isEditMode = mode === 'edit'
  const isViewMode = mode === 'view'

  useEffect(() => {
    if (!selectedResource || isCreateMode) return

    form.setFieldsValue({
      name: selectedResource.name,
      type: selectedResource.type ?? undefined,
      system: selectedResource.system ?? undefined,
      location: selectedResource.location ?? undefined,
      description: selectedResource.description ?? undefined,
    })
  }, [selectedResource, isCreateMode, form])

  const handleStartCreate = () => {
    setMode('create')
    setSelectedResourceId(null)
    form.resetFields()
  }

  const handleEditClick = () => {
    if (!selectedResource) return
    setMode('edit')
  }

  const handleSaveBasic = async () => {
    try {
      const values = await form.validateFields()

      if (isCreateMode || !selectedResource) {
        const created = await createDataResource({
          name: values.name,
          type: values.type,
          system: values.system,
          location: values.location,
          description: values.description,
        })
        showSuccess('创建成功')
        setSelectedResourceId(created.resource_id)
      } else {
        const updated = await updateDataResource(selectedResource.resource_id, {
          name: values.name,
          type: values.type,
          system: values.system,
          location: values.location,
          description: values.description,
        })
        showSuccess('保存成功')
        setSelectedResourceId(updated.resource_id)
      }
      setMode('view')
      await fetchList()
    } catch (e: any) {
      if (e?.errorFields) {
        return
      }
      showError('保存失败')
    }
  }

  const handleCancelEdit = () => {
    if (isCreateMode) {
      setMode('view')
      if (resources.length > 0) {
        setSelectedResourceId(resources[0].resource_id)
      }
    } else if (isEditMode) {
      setMode('view')
      if (selectedResource) {
        form.setFieldsValue({
          name: selectedResource.name,
          type: selectedResource.type ?? undefined,
          system: selectedResource.system ?? undefined,
          location: selectedResource.location ?? undefined,
          description: selectedResource.description ?? undefined,
        })
      }
    }
  }

  const handleDelete = async (resource: DataResource) => {
    try {
      await deleteDataResource(resource.resource_id)
      showSuccess('删除成功')
      if (selectedResourceId === resource.resource_id) {
        setSelectedResourceId(null)
      }
      await fetchList()
    } catch (e) {
      showError('删除失败')
    }
  }

  return (
    <div style={{ display: 'flex', height: '100%', gap: 16 }}>
      {/* 左侧：数据资源列表 */}
      <div
        style={{
          flex: 1.8,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          overflow: 'hidden',
        }}
      >
        <div className="toolbar-container" style={{ marginBottom: 4 }}>
          <Space>
            <Input.Search
              allowClear
              placeholder="按名称或资源ID搜索..."
              prefix={<SearchOutlined style={{ color: '#9ca3af' }} />}
              onSearch={(val) => {
                setKeyword(val)
                setPage(1)
              }}
              style={{ width: 320 }}
            />
            <Input
              allowClear
              placeholder="所属系统过滤"
              prefix={<LaptopOutlined style={{ color: '#9ca3af' }} />}
              value={systemFilter}
              onChange={(e) => {
                setSystemFilter(e.target.value || undefined)
                setPage(1)
              }}
              style={{ width: 220 }}
            />
          </Space>
          <Space>
            <Button onClick={fetchList}>刷新</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleStartCreate}>
              新建数据资源
            </Button>
          </Space>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Space>
            <Typography.Title level={5} style={{ margin: 0 }}>
              数据资源列表
            </Typography.Title>
            <Badge
              count={total}
              style={{ backgroundColor: '#7c3aed' }}
              overflowCount={999}
              showZero
            />
          </Space>
        </div>

        <div
          style={{
            flex: 1,
            minHeight: 0,
            borderRadius: 8,
            border: '1px solid #e5e7eb',
            overflowY: 'auto',
            overflowX: 'hidden',
            padding: 8,
            background: '#ffffff',
          }}
        >
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
              gap: 8,
            }}
          >
            {resources.map((r) => {
              const isSelected = r.resource_id === selectedResourceId

              return (
                <div
                  key={r.resource_id}
                  onClick={() => {
                    setSelectedResourceId(r.resource_id)
                    setMode('view')
                  }}
                  style={{
                    borderRadius: 8,
                    border: isSelected ? '2px solid #faad14' : '1px solid #e5e7eb',
                    padding: 8,
                    cursor: 'pointer',
                    background: isSelected ? '#fff7e6' : '#ffffff',
                    boxShadow: isSelected
                      ? '0 0 0 1px rgba(250, 173, 20, 0.25)'
                      : '0 1px 2px rgba(15,23,42,0.03)',
                    transition:
                      'border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease',
                    display: 'flex',
                    flexDirection: 'column',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: 4,
                    }}
                  >
                    <Space size={6}>
                      <span style={{ color: '#faad14' }}>
                        <DatabaseOutlined />
                      </span>
                      <Tooltip title={r.name}>
                        <Typography.Text
                          strong
                          style={{
                            fontSize: 13,
                            wordBreak: 'break-all',
                            whiteSpace: 'normal',
                          }}
                        >
                          {r.name}
                        </Typography.Text>
                      </Tooltip>
                    </Space>
                    <Space size={4}>
                      {r.type && (
                        <Tag style={{ fontSize: 11 }}>
                          {r.type}
                        </Tag>
                      )}
                    </Space>
                  </div>

                  <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 4 }}>
                    <div>资源ID: {r.resource_id}</div>
                    <div>
                      位置: {r.location || '-'}
                    </div>
                  </div>

                  <div
                    style={{
                      fontSize: 11,
                      color: '#6b7280',
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                    title={r.description || ''}
                  >
                    {r.description || '暂无描述'}
                  </div>

                  <div style={{ marginTop: 'auto', textAlign: 'right', paddingTop: 4 }}>
                    <Popconfirm
                      title="确认删除该数据资源？"
                      onConfirm={(e) => {
                        e?.stopPropagation()
                        handleDelete(r)
                      }}
                      onCancel={(e) => e?.stopPropagation()}
                      okText="删除"
                      cancelText="取消"
                    >
                      <Typography.Text
                        type="secondary"
                        style={{ fontSize: 11, color: '#f97316' }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        删除
                      </Typography.Text>
                    </Popconfirm>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <div
          style={{
            marginTop: 8,
            display: 'flex',
            justifyContent: 'flex-end',
          }}
        >
          <Pagination
            size="small"
            current={page}
            pageSize={pageSize}
            total={total}
            showSizeChanger
            onChange={(p, ps) => {
              setPage(p)
              setPageSize(ps)
            }}
          />
        </div>
      </div>

      {/* 右侧：数据资源详情 */}
      <div
        style={{
          width: 360,
          borderLeft: '1px solid #f3f4f6',
          paddingLeft: 16,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          minHeight: 0,
          maxHeight: '100%',
          overflowY: 'auto',
          overflowX: 'hidden',
        }}
      >
        <Typography.Title level={5} style={{ margin: 0 }}>
          数据资源详情
        </Typography.Title>

        {!selectedResource && !isCreateMode && (
          <Card size="small" bordered={false} style={{ background: '#f9fafb' }}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              在左侧列表中点击任意数据资源，这里将展示该资源的基础信息，
              包括名称、类型、所属系统、物理位置与描述。
            </Typography.Text>
          </Card>
        )}

        {(selectedResource || isCreateMode) && (
          <Card size="small" bordered={false}>
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <Space size={6}>
                  <span style={{ color: '#7c3aed' }}>
                    <DatabaseOutlined />
                  </span>
                  <Typography.Text
                    strong
                    style={{
                      whiteSpace: 'normal',
                      wordBreak: 'break-word',
                    }}
                  >
                    {isCreateMode
                      ? '新建数据资源'
                      : selectedResource?.name || '未选择数据资源'}
                  </Typography.Text>
                </Space>
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <Space size={8}>
                    {isViewMode && selectedResource && <Tag>详情</Tag>}
                    {isViewMode && selectedResource && (
                      <Tag
                        color="blue"
                        style={{ cursor: 'pointer' }}
                        onClick={handleEditClick}
                      >
                        编辑
                      </Tag>
                    )}
                    {(isEditMode || isCreateMode) && (
                      <Space size={8}>
                        <Tag
                          color="default"
                          style={{ cursor: 'pointer' }}
                          onClick={handleCancelEdit}
                        >
                          取消
                        </Tag>
                        <Tag
                          color="blue"
                          style={{ cursor: 'pointer' }}
                          onClick={handleSaveBasic}
                        >
                          保存
                        </Tag>
                      </Space>
                    )}
                  </Space>
                </div>
              </div>

              <Divider style={{ margin: '8px 0' }} />

              <Form
                form={form}
                layout="vertical"
                disabled={isViewMode && !isCreateMode}
              >
                <Form.Item
                  label="名称"
                  name="name"
                  rules={[{ required: true, message: '请输入名称' }]}
                >
                  <Input />
                </Form.Item>
                <Form.Item label="类型" name="type">
                  <Input placeholder="如 db_table/api 等" />
                </Form.Item>
                <Form.Item label="所属系统" name="system">
                  <Input placeholder="如 member-service" />
                </Form.Item>
                <Form.Item label="物理位置" name="location">
                  <Input placeholder="如 member_db.user_card" />
                </Form.Item>
                <Form.Item label="描述" name="description">
                  <Input.TextArea rows={4} />
                </Form.Item>
              </Form>

              {isCreateMode && (
                <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                  新建模式下，这里只编辑数据资源本身的基础字段，
                  与实现、步骤的访问关系建议在关系工作台中维护。
                </Typography.Text>
              )}
            </Space>
          </Card>
        )}
      </div>
    </div>
  )
}

const ResourceLibraryPage: React.FC = () => {
  // 从 URL 参数读取初始 Tab
  const searchParams = new URLSearchParams(window.location.search)
  const tabFromUrl = searchParams.get('tab')
  const validTabs = ['business', 'step', 'implementation', 'resource']
  const initialTab = tabFromUrl && validTabs.includes(tabFromUrl) ? tabFromUrl : 'business'
  
  const [activeTab, setActiveTab] = useState<string>(initialTab)

  return (
    <div className="resource-library-container">
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
          minHeight: 0,
        }}
      >
        <Tabs
          className="custom-tabs"
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'business',
              label: (
                <span>
                  <BranchesOutlined />
                  业务流程
                </span>
              ),
              children: <BusinessTab />,
            },
            {
              key: 'step',
              label: (
                <span>
                  <NodeIndexOutlined />
                  业务步骤
                </span>
              ),
              children: <StepTab />,
            },
            {
              key: 'implementation',
              label: (
                <span>
                  <CodeOutlined />
                  实现单元
                </span>
              ),
              children: <ImplementationTab />,
            },
            {
              key: 'resource',
              label: (
                <span>
                  <DatabaseOutlined />
                  数据资源
                </span>
              ),
              children: <DataResourceTab />,
            },
          ]}
        />
      </div>
    </div>
  )

}

export default ResourceLibraryPage

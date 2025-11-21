import React, { useCallback, useEffect, useState } from 'react'
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
  const [modalVisible, setModalVisible] = useState(false)
  const [editing, setEditing] = useState<BusinessNode | null>(null)
  const [form] = Form.useForm<BusinessFormValues>()

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listBusinessesPaged(keyword, page, pageSize)
      setItems(data.items)
      setTotal(data.total)
    } catch (e) {
      showError('加载流程列表失败')
    } finally {
      setLoading(false)
    }
  }, [keyword, page, pageSize])

  useEffect(() => {
    fetchList()
  }, [fetchList])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    setModalVisible(true)
  }

  const openEdit = (item: BusinessNode) => {
    setEditing(item)
    form.setFieldsValue({
      name: item.name,
      channel: item.channel ?? undefined,
      description: item.description ?? undefined,
      entrypoints: item.entrypoints ?? undefined,
    })
    setModalVisible(true)
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      if (!editing) {
        await createBusiness({
          name: values.name,
          channel: values.channel ?? null,
          description: values.description ?? null,
          entrypoints: values.entrypoints ?? null,
        })
        showSuccess('创建成功')
      } else {
        await updateBusiness(editing.process_id, {
          name: values.name,
          channel: values.channel ?? null,
          description: values.description ?? null,
          entrypoints: values.entrypoints ?? null,
        })
        showSuccess('保存成功')
      }
      setModalVisible(false)
      setEditing(null)
      fetchList()
    } catch (e: any) {
      if (e?.errorFields) return
      showError('保存失败')
    }
  }

  const handleDelete = async (item: BusinessNode) => {
    try {
      await deleteBusiness(item.process_id)
      showSuccess('删除成功')
      fetchList()
    } catch (e) {
      showError('删除失败')
    }
  }

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
          minHeight: 0,
          paddingRight: modalVisible ? 24 : 0,
          transition: 'padding-right 0.2s ease',
        }}
      >
        <div className="toolbar-container">
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
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
              新建流程
            </Button>
          </Space>
        </div>

        <div
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            overflowX: 'hidden',
            paddingBottom: 24,
          }}
        >
          <Row gutter={[24, 24]}>
            {items.map((item) => (
              <Col key={item.process_id} xs={24} sm={12} md={8} lg={6} xl={6}>
                <Card
                  className="resource-card"
                  title={
                    <Space>
                      <Avatar
                        icon={<BranchesOutlined />}
                        style={{ backgroundColor: '#e6f7ff', color: '#1890ff' }}
                        size="small"
                      />
                      <Tooltip title={item.name}>
                        <span>{item.name}</span>
                      </Tooltip>
                    </Space>
                  }
                  loading={loading}
                  extra={item.channel ? <Tag color="blue">{item.channel}</Tag> : null}
                  hoverable
                  onClick={() => openEdit(item)}
                  actions={[
                    <span
                      key="edit"
                      onClick={(e) => {
                        e.stopPropagation()
                        openEdit(item)
                      }}
                    >
                      编辑
                    </span>,
                    <Popconfirm
                      key="delete"
                      title="确认删除该流程？"
                      onConfirm={(e) => {
                        e?.stopPropagation()
                        handleDelete(item)
                      }}
                      onCancel={(e) => e?.stopPropagation()}
                      okText="删除"
                      cancelText="取消"
                    >
                      <span
                        onClick={(e) => {
                          e.stopPropagation()
                        }}
                        style={{ color: '#ff4d4f' }}
                      >
                        删除
                      </span>
                    </Popconfirm>,
                  ]}
                >
                  <div className="card-meta-row">
                    <AppstoreOutlined className="card-meta-icon" />
                    <span className="card-meta-label">ID:</span>
                    <span className="card-meta-value">{item.process_id}</span>
                  </div>
                  <div className="card-meta-row">
                    <GlobalOutlined className="card-meta-icon" />
                    <span className="card-meta-label">渠道:</span>
                    <span className="card-meta-value">{item.channel || '-'}</span>
                  </div>
                  <div className="card-meta-row">
                    <ApiOutlined className="card-meta-icon" />
                    <span className="card-meta-label">入口:</span>
                    <span className="card-meta-value">{item.entrypoints || '-'}</span>
                  </div>
                  <div className="card-description" title={item.description || ''}>
                    {item.description || '暂无描述'}
                  </div>
                </Card>
              </Col>
            ))}
          </Row>
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

      <div
        style={{
          width: modalVisible ? 420 : 0,
          transition: 'width 0.25s ease',
          borderLeft: modalVisible ? '1px solid #f0f0f0' : 'none',
          background: modalVisible ? '#fff' : 'transparent',
          overflow: 'hidden',
        }}
      >
        {modalVisible && (
          <div style={{ padding: 16, height: '100%', overflowY: 'auto', overflowX: 'hidden' }}>
            <Typography.Title level={5} style={{ marginBottom: 16 }}>
              {editing ? '编辑流程' : '新建流程'}
            </Typography.Title>
            <Form form={form} layout="vertical">
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
                <Input.TextArea rows={2} placeholder="描述用户如何触发该业务流程，如：用户在C端App点击开通月卡按钮" />
              </Form.Item>
              <Form.Item label="描述" name="description">
                <Input.TextArea rows={3} />
              </Form.Item>
              <Space style={{ marginTop: 8 }}>
                <Button type="primary" onClick={handleSubmit}>
                  保存
                </Button>
                <Button
                  onClick={() => {
                    setModalVisible(false)
                    setEditing(null)
                  }}
                >
                  取消
                </Button>
              </Space>
            </Form>
          </div>
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
  const [modalVisible, setModalVisible] = useState(false)
  const [editing, setEditing] = useState<StepNode | null>(null)
  const [form] = Form.useForm<StepFormValues>()

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listStepsPaged(keyword, page, pageSize)
      setItems(data.items)
      setTotal(data.total)
    } catch (e) {
      showError('加载步骤列表失败')
    } finally {
      setLoading(false)
    }
  }, [keyword, page, pageSize])

  useEffect(() => {
    fetchList()
  }, [fetchList])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    setModalVisible(true)
  }

  const openEdit = (item: StepNode) => {
    setEditing(item)
    form.setFieldsValue({
      name: item.name,
      description: item.description ?? undefined,
      step_type: item.step_type ?? undefined,
    })
    setModalVisible(true)
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      if (!editing) {
        await createStep({
          name: values.name,
          description: values.description ?? null,
          step_type: values.step_type ?? null,
        })
        showSuccess('创建成功')
      } else {
        await updateStep(editing.step_id, {
          name: values.name,
          description: values.description ?? null,
          step_type: values.step_type ?? null,
        })
        showSuccess('保存成功')
      }
      setModalVisible(false)
      setEditing(null)
      fetchList()
    } catch (e: any) {
      if (e?.errorFields) return
      showError('保存失败')
    }
  }

  const handleDelete = async (item: StepNode) => {
    try {
      await deleteStep(item.step_id)
      showSuccess('删除成功')
      fetchList()
    } catch (e) {
      showError('删除失败')
    }
  }

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
          minHeight: 0,
          paddingRight: modalVisible ? 24 : 0,
          transition: 'padding-right 0.2s ease',
        }}
      >
        <div className="toolbar-container">
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
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
              新建步骤
            </Button>
          </Space>
        </div>

        <div
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            overflowX: 'hidden',
            paddingBottom: 24,
          }}
        >
          <Row gutter={[24, 24]}>
            {items.map((item) => (
              <Col key={item.step_id} xs={24} sm={12} md={8} lg={6} xl={6}>
                <Card
                  className="resource-card"
                  title={
                    <Space>
                      <Avatar
                        icon={<NodeIndexOutlined />}
                        style={{ backgroundColor: '#f6ffed', color: '#52c41a' }}
                        size="small"
                      />
                      <Tooltip title={item.name}>
                        <span>{item.name}</span>
                      </Tooltip>
                    </Space>
                  }
                  loading={loading}
                  extra={item.step_type ? <Tag color="green">{item.step_type}</Tag> : null}
                  hoverable
                  onClick={() => openEdit(item)}
                  actions={[
                    <span
                      key="edit"
                      onClick={(e) => {
                        e.stopPropagation()
                        openEdit(item)
                      }}
                    >
                      编辑
                    </span>,
                    <Popconfirm
                      key="delete"
                      title="确认删除该步骤？"
                      onConfirm={(e) => {
                        e?.stopPropagation()
                        handleDelete(item)
                      }}
                      onCancel={(e) => e?.stopPropagation()}
                      okText="删除"
                      cancelText="取消"
                    >
                      <span
                        onClick={(e) => {
                          e.stopPropagation()
                        }}
                        style={{ color: '#ff4d4f' }}
                      >
                        删除
                      </span>
                    </Popconfirm>,
                  ]}
                >
                  <div className="card-meta-row">
                    <AppstoreOutlined className="card-meta-icon" />
                    <span className="card-meta-label">ID:</span>
                    <span className="card-meta-value">{item.step_id}</span>
                  </div>
                  <div className="card-description" title={item.description || ''}>
                    {item.description || '暂无描述'}
                  </div>
                </Card>
              </Col>
            ))}
          </Row>
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
      <div
        style={{
          width: modalVisible ? 420 : 0,
          transition: 'width 0.25s ease',
          borderLeft: modalVisible ? '1px solid #f0f0f0' : 'none',
          background: modalVisible ? '#fff' : 'transparent',
          overflow: 'hidden',
        }}
      >
        {modalVisible && (
          <div
            style={{
              padding: 16,
              height: '100%',
              overflowY: 'auto',
              overflowX: 'hidden',
            }}
          >
            <Typography.Title level={5} style={{ marginBottom: 16 }}>
              {editing ? '编辑步骤' : '新建步骤'}
            </Typography.Title>
            <Form form={form} layout="vertical">
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
              <Space style={{ marginTop: 8 }}>
                <Button type="primary" onClick={handleSubmit}>
                  保存
                </Button>
                <Button
                  onClick={() => {
                    setModalVisible(false)
                    setEditing(null)
                  }}
                >
                  取消
                </Button>
              </Space>
            </Form>
          </div>
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

const ImplementationTab: React.FC = () => {
  const [items, setItems] = useState<ImplementationNode[]>([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [total, setTotal] = useState(0)
  const [modalVisible, setModalVisible] = useState(false)
  const [editing, setEditing] = useState<ImplementationNode | null>(null)
  const [form] = Form.useForm<ImplementationFormValues>()

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listImplementationsPaged(keyword, page, pageSize)
      setItems(data.items)
      setTotal(data.total)
    } catch (e) {
      showError('加载实现列表失败')
    } finally {
      setLoading(false)
    }
  }, [keyword, page, pageSize])

  useEffect(() => {
    fetchList()
  }, [fetchList])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    setModalVisible(true)
  }

  const openEdit = (item: ImplementationNode) => {
    setEditing(item)
    form.setFieldsValue({
      name: item.name,
      type: item.type ?? undefined,
      system: item.system ?? undefined,
      description: item.description ?? undefined,
      code_ref: item.code_ref ?? undefined,
    })
    setModalVisible(true)
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      if (!editing) {
        await createImplementation({
          name: values.name,
          type: values.type ?? null,
          system: values.system ?? null,
          description: values.description ?? null,
          code_ref: values.code_ref ?? null,
        })
        showSuccess('创建成功')
      } else {
        await updateImplementation(editing.impl_id, {
          name: values.name,
          type: values.type ?? null,
          system: values.system ?? null,
          description: values.description ?? null,
          code_ref: values.code_ref ?? null,
        })
        showSuccess('保存成功')
      }
      setModalVisible(false)
      setEditing(null)
      fetchList()
    } catch (e: any) {
      if (e?.errorFields) return
      showError('保存失败')
    }
  }

  const handleDelete = async (item: ImplementationNode) => {
    try {
      await deleteImplementation(item.impl_id)
      showSuccess('删除成功')
      fetchList()
    } catch (e) {
      showError('删除失败')
    }
  }

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
          minHeight: 0,
          paddingRight: modalVisible ? 24 : 0,
          transition: 'padding-right 0.2s ease',
        }}
      >
        <div className="toolbar-container">
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
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
              新建实现
            </Button>
          </Space>
        </div>

        <div
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            overflowX: 'hidden',
            paddingBottom: 24,
          }}
        >
          <Row gutter={[24, 24]}>
            {items.map((item) => (
              <Col key={item.impl_id} xs={24} sm={12} md={8} lg={6} xl={6}>
                <Card
                  className="resource-card"
                  title={
                    <Space>
                      <Avatar
                        icon={<CodeOutlined />}
                        style={{ backgroundColor: '#fff2e8', color: '#fa541c' }}
                        size="small"
                      />
                      <Tooltip title={item.name}>
                        <span>{item.name}</span>
                      </Tooltip>
                    </Space>
                  }
                  loading={loading}
                  extra={item.system ? <Tag color="geekblue">{item.system}</Tag> : null}
                  hoverable
                  onClick={() => openEdit(item)}
                  actions={[
                    <span
                      key="edit"
                      onClick={(e) => {
                        e.stopPropagation()
                        openEdit(item)
                      }}
                    >
                      编辑
                    </span>,
                    <Popconfirm
                      key="delete"
                      title="确认删除该实现？"
                      onConfirm={(e) => {
                        e?.stopPropagation()
                        handleDelete(item)
                      }}
                      onCancel={(e) => e?.stopPropagation()}
                      okText="删除"
                      cancelText="取消"
                    >
                      <span
                        onClick={(e) => {
                          e.stopPropagation()
                        }}
                        style={{ color: '#ff4d4f' }}
                      >
                        删除
                      </span>
                    </Popconfirm>,
                  ]}
                >
                  <div className="card-meta-row">
                    <AppstoreOutlined className="card-meta-icon" />
                    <span className="card-meta-label">ID:</span>
                    <span className="card-meta-value">{item.impl_id}</span>
                  </div>
                  <div className="card-meta-row">
                    <AppstoreOutlined className="card-meta-icon" />
                    <span className="card-meta-label">类型:</span>
                    <span className="card-meta-value">{item.type || '-'}</span>
                  </div>
                  <div className="card-meta-row">
                    <CodeOutlined className="card-meta-icon" />
                    <span className="card-meta-label">引用:</span>
                    <span className="card-meta-value">{item.code_ref || '-'}</span>
                  </div>
                  <div className="card-description" title={item.description || ''}>
                    {item.description || '暂无描述'}
                  </div>
                </Card>
              </Col>
            ))}
          </Row>
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
      <div
        style={{
          width: modalVisible ? 420 : 0,
          transition: 'width 0.25s ease',
          borderLeft: modalVisible ? '1px solid #f0f0f0' : 'none',
          background: modalVisible ? '#fff' : 'transparent',
          overflow: 'hidden',
        }}
      >
        {modalVisible && (
          <div
            style={{
              padding: 16,
              height: '100%',
              overflowY: 'auto',
              overflowX: 'hidden',
            }}
          >
            <Typography.Title level={5} style={{ marginBottom: 16 }}>
              {editing ? '编辑实现' : '新建实现'}
            </Typography.Title>
            <Form form={form} layout="vertical">
              <Form.Item
                label="名称"
                name="name"
                rules={[{ required: true, message: '请输入名称' }]}
              >
                <Input />
              </Form.Item>
              <Form.Item label="类型" name="type">
                <Input />
              </Form.Item>
              <Form.Item label="系统" name="system">
                <Input />
              </Form.Item>
              <Form.Item label="代码引用" name="code_ref">
                <Input />
              </Form.Item>
              <Form.Item label="描述" name="description">
                <Input.TextArea rows={3} />
              </Form.Item>
              <Space style={{ marginTop: 8 }}>
                <Button type="primary" onClick={handleSubmit}>
                  保存
                </Button>
                <Button
                  onClick={() => {
                    setModalVisible(false)
                    setEditing(null)
                  }}
                >
                  取消
                </Button>
              </Space>
            </Form>
          </div>
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
  const [loadingList, setLoadingList] = useState(false)

  const [keyword, setKeyword] = useState('')
  const [systemFilter, setSystemFilter] = useState<string | undefined>()

  const [selectedResource, setSelectedResource] = useState<DataResource | null>(null)
  const [creatingNew, setCreatingNew] = useState(false)
  const [drawerVisible, setDrawerVisible] = useState(false)

  const fetchList = useCallback(async () => {
    setLoadingList(true)
    try {
      const data = await listDataResources({
        page,
        page_size: pageSize,
        q: keyword || undefined,
        system: systemFilter,
      })
      setResources(data.items)
      setTotal(data.total)
    } catch (e) {
      showError('加载数据资源列表失败')
    } finally {
      setLoadingList(false)
    }
  }, [page, pageSize, keyword, systemFilter])

  useEffect(() => {
    fetchList()
  }, [fetchList])

  const handleSelectResource = useCallback((record: DataResource) => {
    setSelectedResource(record)
    setCreatingNew(false)
    form.setFieldsValue(record)
    setDrawerVisible(true)
  }, [form])

  const handleNewResource = () => {
    setCreatingNew(true)
    setSelectedResource(null)
    form.resetFields()
    setDrawerVisible(true)
  }

  const handleSaveBasic = async () => {
    try {
      const values = await form.validateFields()

      if (creatingNew || !selectedResource) {
        const created = await createDataResource({
          name: values.name,
          type: values.type,
          system: values.system,
          location: values.location,
          description: values.description,
        })
        showSuccess('创建成功')
        setCreatingNew(false)
        setSelectedResource(created)
        await fetchList()
      } else {
        const updated = await updateDataResource(selectedResource.resource_id, {
          name: values.name,
          type: values.type,
          system: values.system,
          location: values.location,
          description: values.description,
        })
        showSuccess('保存成功')
        setSelectedResource(updated)
        await fetchList()
      }
    } catch (e: any) {
      if (e?.errorFields) {
        return
      }
      showError('保存失败')
    }
  }

  const handleDelete = async () => {
    if (!selectedResource) return
    try {
      await deleteDataResource(selectedResource.resource_id)
      showSuccess('删除成功')
      setSelectedResource(null)
      setDrawerVisible(false)
      await fetchList()
    } catch (e) {
      showError('删除失败')
    }
  }


  return (
    <div style={{ display: 'flex', height: '100%' }}>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
          minHeight: 0,
          paddingRight: drawerVisible ? 24 : 0,
          transition: 'padding-right 0.2s ease',
        }}
      >
        <div className="toolbar-container">
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
          <Button type="primary" icon={<PlusOutlined />} onClick={handleNewResource}>
            新建数据资源
          </Button>
        </Space>
      </div>

      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          overflowX: 'hidden',
          paddingBottom: 24,
        }}
      >
        <Row gutter={[24, 24]}>
          {resources.map((r) => (
            <Col key={r.resource_id} xs={24} sm={12} md={12} lg={8} xl={6}>
              <Card
                className="resource-card"
                size="small"
                hoverable
                loading={loadingList}
                onClick={() => handleSelectResource(r)}
                title={
                  <Space>
                    <Avatar
                      icon={<DatabaseOutlined />}
                      style={{ backgroundColor: '#f9f0ff', color: '#722ed1' }}
                      size="small"
                    />
                    <Tooltip title={r.name}>
                      <span>{r.name}</span>
                    </Tooltip>
                  </Space>
                }
                extra={
                  <Space size={4}>
                    {r.type && <Tag>{r.type}</Tag>}
                  </Space>
                }
              >
                <div className="card-meta-row">
                  <GlobalOutlined className="card-meta-icon" />
                  <span className="card-meta-label">位置:</span>
                  <span className="card-meta-value">{r.location || '-'}</span>
                </div>
                <div className="card-meta-row">
                  <FileTextOutlined className="card-meta-icon" />
                  <span className="card-meta-label">ID:</span>
                  <span className="card-meta-value">{r.resource_id}</span>
                </div>
                <div className="card-description" title={r.description || ''}>
                  {r.description || '暂无描述'}
                </div>
              </Card>
            </Col>
          ))}
        </Row>
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

      <div
        style={{
          width: drawerVisible ? 420 : 0,
          transition: 'width 0.25s ease',
          borderLeft: drawerVisible ? '1px solid #f0f0f0' : 'none',
          background: drawerVisible ? '#fff' : 'transparent',
          overflow: 'hidden',
        }}
      >
        {drawerVisible && (
          <div
            style={{
              padding: 16,
              height: '100%',
              overflowY: 'auto',
              overflowX: 'hidden',
            }}
          >
          <Typography.Title level={5} style={{ marginBottom: 16 }}>
            {creatingNew ? '新建数据资源' : '编辑数据资源'}
          </Typography.Title>

          <Form
            form={form}
            layout="vertical"
            initialValues={{ name: '' }}
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
            <Space style={{ marginTop: 8 }}>
              <Button type="primary" onClick={handleSaveBasic}>
                保存
              </Button>
              <Button
                onClick={() => {
                  setDrawerVisible(false)
                }}
              >
                取消
              </Button>
            </Space>
          </Form>
          </div>
        )}
      </div>
    </div>
  )
}

const ResourceLibraryPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('business')

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

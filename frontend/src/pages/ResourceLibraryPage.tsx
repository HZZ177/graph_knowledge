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
} from 'antd'

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
  process_id: string
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
      process_id: item.process_id,
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
          process_id: values.process_id,
          name: values.name,
          channel: values.channel ?? null,
          description: values.description ?? null,
          entrypoints: values.entrypoints ?? null,
        })
        showSuccess('创建成功')
      } else {
        const { process_id: _pid, ...rest } = values
        await updateBusiness(editing.process_id, rest)
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
          flex: 1,
          paddingRight: modalVisible ? 24 : 0,
          transition: 'padding-right 0.25s ease',
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          minHeight: 0,
        }}
      >
        <Row justify="space-between" style={{ marginBottom: 16 }} gutter={16}>
          <Col flex="auto">
            <Input.Search
              allowClear
              placeholder="按名称或流程ID搜索"
              onSearch={(val) => {
                setKeyword(val)
                setPage(1)
              }}
            />
          </Col>
          <Col>
            <Button type="primary" onClick={openCreate}>
              新建流程
            </Button>
          </Col>
        </Row>
        <div
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            overflowX: 'hidden',
          }}
        >
          <Row gutter={[16, 16]}>
            {items.map((item) => (
              <Col key={item.process_id} xs={24} sm={12} md={8} lg={6}>
                <Card
                  title={item.name}
                  loading={loading}
                  extra={<Tag color="blue">{item.process_id}</Tag>}
                  hoverable
                  onClick={() => openEdit(item)}
                  actions={[
                    <a
                      key="edit"
                      onClick={(e) => {
                        e.stopPropagation()
                        openEdit(item)
                      }}
                    >
                      编辑
                    </a>,
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
                      <a
                        onClick={(e) => {
                          e.stopPropagation()
                        }}
                      >
                        删除
                      </a>
                    </Popconfirm>,
                  ]}
                >
                  <div style={{ fontSize: 12, color: '#666', lineHeight: 1.8 }}>
                    <div>
                      <strong>渠道：</strong>
                      {item.channel || '-'}
                    </div>
                    <div style={{ wordBreak: 'break-all', overflowWrap: 'break-word' }}>
                      <strong>入口：</strong>
                      {item.entrypoints || '-'}
                    </div>
                    <div>
                      <strong>描述：</strong>
                      {item.description || '-'}
                    </div>
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
            pageSizeOptions={['10', '20', '50', '100']}
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
              label="流程ID"
              name="process_id"
              rules={[{ required: true, message: '请输入流程ID' }]}
            >
              <Input disabled={!!editing} />
            </Form.Item>
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
            <Form.Item label="入口（逗号分隔）" name="entrypoints">
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

interface StepFormValues {
  step_id: string
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
      step_id: item.step_id,
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
          step_id: values.step_id,
          name: values.name,
          description: values.description ?? null,
          step_type: values.step_type ?? null,
        })
        showSuccess('创建成功')
      } else {
        const { step_id: _sid, ...rest } = values
        await updateStep(editing.step_id, rest)
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
          flex: 1,
          paddingRight: modalVisible ? 24 : 0,
          transition: 'padding-right 0.2s ease',
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          minHeight: 0,
        }}
      >
        <Row justify="space-between" style={{ marginBottom: 16 }} gutter={16}>
          <Col flex="auto">
            <Input.Search
              allowClear
              placeholder="按名称或步骤ID搜索"
              onSearch={(val) => {
                setKeyword(val)
                setPage(1)
              }}
            />
          </Col>
          <Col>
            <Button type="primary" onClick={openCreate}>
              新建步骤
            </Button>
          </Col>
        </Row>
        <div
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            overflowX: 'hidden',
          }}
        >
          <Row gutter={[16, 16]}>
            {items.map((item) => (
              <Col key={item.step_id} xs={24} sm={12} md={8} lg={6}>
                <Card
                  title={item.name}
                  loading={loading}
                  extra={item.step_type ? <Tag>{item.step_type}</Tag> : null}
                  hoverable
                  onClick={() => openEdit(item)}
                  actions={[
                    <a
                      key="edit"
                      onClick={(e) => {
                        e.stopPropagation()
                        openEdit(item)
                      }}
                    >
                      编辑
                    </a>,
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
                      <a
                        onClick={(e) => {
                          e.stopPropagation()
                        }}
                      >
                        删除
                      </a>
                    </Popconfirm>,
                  ]}
                >
                  <div
                    style={{
                      fontSize: 12,
                      color: '#666',
                      lineHeight: 1.8,
                      wordBreak: 'break-all',
                      overflowWrap: 'break-word',
                    }}
                  >
                    <div>
                      <strong>步骤ID：</strong>
                      {item.step_id}
                    </div>
                    <div>
                      <strong>描述：</strong>
                      {item.description || '-'}
                    </div>
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
                label="步骤ID"
                name="step_id"
                rules={[{ required: true, message: '请输入步骤ID' }]}
              >
                <Input disabled={!!editing} />
              </Form.Item>
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
  impl_id: string
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
      impl_id: item.impl_id,
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
          impl_id: values.impl_id,
          name: values.name,
          type: values.type ?? null,
          system: values.system ?? null,
          description: values.description ?? null,
          code_ref: values.code_ref ?? null,
        })
        showSuccess('创建成功')
      } else {
        const { impl_id: _iid, ...rest } = values
        await updateImplementation(editing.impl_id, rest)
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
          flex: 1,
          paddingRight: modalVisible ? 24 : 0,
          transition: 'padding-right 0.2s ease',
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          minHeight: 0,
        }}
      >
        <Row justify="space-between" style={{ marginBottom: 16 }} gutter={16}>
          <Col flex="auto">
            <Input.Search
              allowClear
              placeholder="按名称或实现ID搜索"
              onSearch={(val) => {
                setKeyword(val)
                setPage(1)
              }}
            />
          </Col>
          <Col>
            <Button type="primary" onClick={openCreate}>
              新建实现
            </Button>
          </Col>
        </Row>
        <div
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            overflowX: 'hidden',
          }}
        >
          <Row gutter={[16, 16]}>
            {items.map((item) => (
              <Col key={item.impl_id} xs={24} sm={12} md={8} lg={6}>
                <Card
                  title={item.name}
                  loading={loading}
                  extra={item.system ? <Tag color="geekblue">{item.system}</Tag> : null}
                  hoverable
                  onClick={() => openEdit(item)}
                  actions={[
                    <a
                      key="edit"
                      onClick={(e) => {
                        e.stopPropagation()
                        openEdit(item)
                      }}
                    >
                      编辑
                    </a>,
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
                      <a
                        onClick={(e) => {
                          e.stopPropagation()
                        }}
                      >
                        删除
                      </a>
                    </Popconfirm>,
                  ]}
                >
                  <div
                    style={{
                      fontSize: 12,
                      color: '#666',
                      lineHeight: 1.8,
                      wordBreak: 'break-all',
                      overflowWrap: 'break-word',
                    }}
                  >
                    <div>
                      <strong>实现ID：</strong>
                      {item.impl_id}
                    </div>
                    <div>
                      <strong>类型：</strong>
                      {item.type || '-'}
                    </div>
                    <div>
                      <strong>系统：</strong>
                      {item.system || '-'}
                    </div>
                    <div>
                      <strong>代码引用：</strong>
                      {item.code_ref || '-'}
                    </div>
                    <div>
                      <strong>描述：</strong>
                      {item.description || '-'}
                    </div>
                  </div>
                </Card>
              </Col>
            ))}
          </Row>
        </div>
        <div
          style={{
            marginTop: 8,
            textAlign: 'right',
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
                label="实现ID"
                name="impl_id"
                rules={[{ required: true, message: '请输入实现ID' }]}
              >
                <Input disabled={!!editing} />
              </Form.Item>
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
  resource_id: string
  name: string
  type?: string
  system?: string
  location?: string
  entity_id?: string
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
      const payload: DataResourceFormValues = values

      if (creatingNew || !selectedResource) {
        const created = await createDataResource(payload)
        showSuccess('创建成功')
        setCreatingNew(false)
        setSelectedResource(created)
        await fetchList()
      } else {
        const updated = await updateDataResource(selectedResource.resource_id, {
          name: payload.name,
          type: payload.type,
          system: payload.system,
          location: payload.location,
          entity_id: payload.entity_id,
          description: payload.description,
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
          flex: 1,
          paddingRight: drawerVisible ? 24 : 0,
          transition: 'padding-right 0.25s ease',
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          minHeight: 0,
        }}
      >
        <Row justify="space-between" style={{ marginBottom: 16 }} gutter={16}>
          <Col flex="auto">
            <Space>
              <Input.Search
                allowClear
                placeholder="按名称或资源ID搜索"
                onSearch={(val) => {
                  setKeyword(val)
                  setPage(1)
                }}
              />
              <Input
                allowClear
                placeholder="所属系统（如 member-service）"
                value={systemFilter}
                onChange={(e) => {
                  setSystemFilter(e.target.value || undefined)
                  setPage(1)
                }}
                style={{ width: 220 }}
              />
            </Space>
          </Col>
          <Col>
            <Space>
              <Button onClick={fetchList}>刷新</Button>
              <Button type="primary" onClick={handleNewResource}>
                新建数据资源
              </Button>
            </Space>
          </Col>
        </Row>
        <div
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            overflowX: 'hidden',
          }}
        >
          <Row gutter={[16, 16]}>
            {resources.map((r) => (
              <Col key={r.resource_id} xs={24} sm={12} md={12} lg={8}>
                <Card
                  size="small"
                  hoverable
                  loading={loadingList}
                  onClick={() => handleSelectResource(r)}
                  title={r.name}
                  extra={
                    <Space size={4}>
                      {r.type && <Tag>{r.type}</Tag>}
                      {r.system && <Tag color="geekblue">{r.system}</Tag>}
                    </Space>
                  }
                >
                  <div
                    style={{
                      fontSize: 12,
                      color: '#666',
                      lineHeight: 1.8,
                      wordBreak: 'break-all',
                      overflowWrap: 'break-word',
                    }}
                  >
                    <div>
                      <strong>ID：</strong>
                      {r.resource_id}
                    </div>
                    <div>
                      <strong>位置：</strong>
                      {r.location || '-'}
                    </div>
                    <div>
                      <strong>实体：</strong>
                      {r.entity_id || '-'}
                    </div>
                    <div>
                      <strong>描述：</strong>
                      {r.description || '-'}
                    </div>
                  </div>
                </Card>
              </Col>
            ))}
          </Row>
        </div>
        <div
          style={{
            marginTop: 8,
            textAlign: 'right',
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
            initialValues={{ resource_id: '', name: '' }}
          >
            <Form.Item
              label="资源ID"
              name="resource_id"
              rules={[{ required: true, message: '请输入资源ID' }]}
            >
              <Input disabled={!creatingNew && !!selectedResource} />
            </Form.Item>
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
            <Form.Item label="实体标识" name="entity_id">
              <Input placeholder="如 card/plate 等" />
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
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        // 视口高度 - Header(64) - Content margin(24*2) - Content padding(24*2)
        height: 'calc(100vh - 160px)',
        minHeight: 0,
        overflow: 'hidden',
      }}
    >
      <Title level={3} style={{ marginBottom: 16 }}>
        资源库
      </Title>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
          minHeight: 0,
        }}
      >
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            { key: 'business', label: '流程' },
            { key: 'step', label: '步骤' },
            { key: 'implementation', label: '实现' },
            { key: 'resource', label: '数据资源' },
          ]}
        />
        <div style={{ flex: 1, minHeight: 0 }}>
          {activeTab === 'business' && <BusinessTab />}
          {activeTab === 'step' && <StepTab />}
          {activeTab === 'implementation' && <ImplementationTab />}
          {activeTab === 'resource' && <DataResourceTab />}
        </div>
      </div>
    </div>
  )
}

export default ResourceLibraryPage

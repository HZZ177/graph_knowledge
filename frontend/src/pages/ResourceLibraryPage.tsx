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
  message,
  Popconfirm,
  Tag,
  Pagination,
} from 'antd'

import ReactFlow, { Background, Controls, Edge, Node } from 'reactflow'
import 'reactflow/dist/style.css'

import {
  BusinessSimple,
  DataResource,
  AccessChainItem,
  listBusinesses,
  listDataResources,
  listSteps,
  createDataResource,
  updateDataResource,
  deleteDataResource,
  listAccessChainsByNode,
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
  const [modalVisible, setModalVisible] = useState(false)
  const [editing, setEditing] = useState<BusinessNode | null>(null)
  const [form] = Form.useForm<BusinessFormValues>()

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listBusinessesPaged(keyword, 1, 200)
      setItems(data.items)
    } catch (e) {
      message.error('加载流程列表失败')
    } finally {
      setLoading(false)
    }
  }, [keyword])

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
        message.success('创建成功')
      } else {
        const { process_id: _pid, ...rest } = values
        await updateBusiness(editing.process_id, rest)
        message.success('保存成功')
      }
      setModalVisible(false)
      setEditing(null)
      fetchList()
    } catch (e: any) {
      if (e?.errorFields) return
      message.error('保存失败')
    }
  }

  const handleDelete = async (item: BusinessNode) => {
    try {
      await deleteBusiness(item.process_id)
      message.success('删除成功')
      fetchList()
    } catch (e) {
      message.error('删除失败')
    }
  }

  return (
    <div style={{ display: 'flex' }}>
      <div
        style={{
          flex: 1,
          paddingRight: modalVisible ? 24 : 0,
          transition: 'padding-right 0.25s ease',
        }}
      >
        <Row justify="space-between" style={{ marginBottom: 16 }} gutter={16}>
          <Col flex="auto">
            <Input.Search
              allowClear
              placeholder="按名称或流程ID搜索"
              onSearch={(val) => setKeyword(val)}
            />
          </Col>
          <Col>
            <Button type="primary" onClick={openCreate}>
              新建流程
            </Button>
          </Col>
        </Row>
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
                  <a key="edit" onClick={(e) => { e.stopPropagation(); openEdit(item) }}>编辑</a>,
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
          width: modalVisible ? 420 : 0,
          transition: 'width 0.25s ease',
          borderLeft: modalVisible ? '1px solid #f0f0f0' : 'none',
          background: modalVisible ? '#fff' : 'transparent',
          overflow: 'hidden',
        }}
      >
        {modalVisible && (
          <div style={{ padding: 16 }}>
          <Space
            style={{
              width: '100%',
              justifyContent: 'space-between',
              marginBottom: 16,
            }}
          >
            <Typography.Title level={5} style={{ margin: 0 }}>
              {editing ? '编辑流程' : '新建流程'}
            </Typography.Title>
            <Button
              size="small"
              onClick={() => {
                setModalVisible(false)
                setEditing(null)
              }}
            >
              关闭
            </Button>
          </Space>
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
            <Space>
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
  const [modalVisible, setModalVisible] = useState(false)
  const [editing, setEditing] = useState<StepNode | null>(null)
  const [form] = Form.useForm<StepFormValues>()

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listStepsPaged(keyword, 1, 200)
      setItems(data.items)
    } catch (e) {
      message.error('加载步骤列表失败')
    } finally {
      setLoading(false)
    }
  }, [keyword])

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
        message.success('创建成功')
      } else {
        const { step_id: _sid, ...rest } = values
        await updateStep(editing.step_id, rest)
        message.success('保存成功')
      }
      setModalVisible(false)
      setEditing(null)
      fetchList()
    } catch (e: any) {
      if (e?.errorFields) return
      message.error('保存失败')
    }
  }

  const handleDelete = async (item: StepNode) => {
    try {
      await deleteStep(item.step_id)
      message.success('删除成功')
      fetchList()
    } catch (e) {
      message.error('删除失败')
    }
  }

  return (
    <div style={{ display: 'flex' }}>
      <div
        style={{
          flex: 1,
          paddingRight: modalVisible ? 24 : 0,
          transition: 'padding-right 0.2s ease',
        }}
      >
        <Row justify="space-between" style={{ marginBottom: 16 }} gutter={16}>
          <Col flex="auto">
            <Input.Search
              allowClear
              placeholder="按名称或步骤ID搜索"
              onSearch={(val) => setKeyword(val)}
            />
          </Col>
          <Col>
            <Button type="primary" onClick={openCreate}>
              新建步骤
            </Button>
          </Col>
        </Row>
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
                  <a key="edit" onClick={(e) => { e.stopPropagation(); openEdit(item) }}>编辑</a>,
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
              overflow: 'auto',
            }}
          >
            <Space
              style={{
                width: '100%',
                justifyContent: 'space-between',
                marginBottom: 16,
              }}
            >
              <Typography.Title level={5} style={{ margin: 0 }}>
                {editing ? '编辑步骤' : '新建步骤'}
              </Typography.Title>
              <Button
                size="small"
                onClick={() => {
                  setModalVisible(false)
                  setEditing(null)
                }}
              >
                关闭
              </Button>
            </Space>
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
              <Space>
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
  const [modalVisible, setModalVisible] = useState(false)
  const [editing, setEditing] = useState<ImplementationNode | null>(null)
  const [form] = Form.useForm<ImplementationFormValues>()

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listImplementationsPaged(keyword, 1, 200)
      setItems(data.items)
    } catch (e) {
      message.error('加载实现列表失败')
    } finally {
      setLoading(false)
    }
  }, [keyword])

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
        message.success('创建成功')
      } else {
        const { impl_id: _iid, ...rest } = values
        await updateImplementation(editing.impl_id, rest)
        message.success('保存成功')
      }
      setModalVisible(false)
      setEditing(null)
      fetchList()
    } catch (e: any) {
      if (e?.errorFields) return
      message.error('保存失败')
    }
  }

  const handleDelete = async (item: ImplementationNode) => {
    try {
      await deleteImplementation(item.impl_id)
      message.success('删除成功')
      fetchList()
    } catch (e) {
      message.error('删除失败')
    }
  }

  return (
    <div style={{ display: 'flex' }}>
      <div
        style={{
          flex: 1,
          paddingRight: modalVisible ? 24 : 0,
          transition: 'padding-right 0.2s ease',
        }}
      >
        <Row justify="space-between" style={{ marginBottom: 16 }} gutter={16}>
          <Col flex="auto">
            <Input.Search
              allowClear
              placeholder="按名称或实现ID搜索"
              onSearch={(val) => setKeyword(val)}
            />
          </Col>
          <Col>
            <Button type="primary" onClick={openCreate}>
              新建实现
            </Button>
          </Col>
        </Row>
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
                  <a key="edit" onClick={(e) => { e.stopPropagation(); openEdit(item) }}>编辑</a>,
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
              overflow: 'auto',
            }}
          >
            <Space
              style={{
                width: '100%',
                justifyContent: 'space-between',
                marginBottom: 16,
              }}
            >
              <Typography.Title level={5} style={{ margin: 0 }}>
                {editing ? '编辑实现' : '新建实现'}
              </Typography.Title>
              <Button
                size="small"
                onClick={() => {
                  setModalVisible(false)
                  setEditing(null)
                }}
              >
                关闭
              </Button>
            </Space>
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
              <Space>
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
  const [accessors, setAccessors] = useState<AccessChainItem[]>([])
  const [loadingDetail, setLoadingDetail] = useState(false)

  const [activeTab, setActiveTab] = useState<string>('basic')
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
      message.error('加载数据资源列表失败')
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
    setActiveTab('basic')
    setDrawerVisible(true)
    ;(async () => {
      setLoadingDetail(true)
      try {
        const chains = await listAccessChainsByNode('resource', record.resource_id)
        setAccessors(chains)
      } catch (e) {
        message.error('加载资源访问关系失败')
      } finally {
        setLoadingDetail(false)
      }
    })()
  }, [form])

  const handleNewResource = () => {
    setCreatingNew(true)
    setSelectedResource(null)
    setAccessors([])
    setActiveTab('basic')
    form.resetFields()
    setDrawerVisible(true)
  }

  const handleSaveBasic = async () => {
    try {
      const values = await form.validateFields()
      const payload: DataResourceFormValues = values

      if (creatingNew || !selectedResource) {
        const created = await createDataResource(payload)
        message.success('创建成功')
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
        message.success('保存成功')
        setSelectedResource(updated)
        await fetchList()
      }
    } catch (e: any) {
      if (e?.errorFields) {
        return
      }
      message.error('保存失败')
    }
  }

  const handleDelete = async () => {
    if (!selectedResource) return
    try {
      await deleteDataResource(selectedResource.resource_id)
      message.success('删除成功')
      setSelectedResource(null)
      setAccessors([])
      setDrawerVisible(false)
      await fetchList()
    } catch (e) {
      message.error('删除失败')
    }
  }

  const graphNodes: Node[] = useMemo(() => {
    if (!selectedResource) return []

    const nodes: Node[] = []
    const centerY = 0

    nodes.push({
      id: `resource:${selectedResource.resource_id}`,
      data: { label: `${selectedResource.name}\n${selectedResource.resource_id}` },
      position: { x: 0, y: centerY },
      type: 'default',
    })

    const implMap = new Map<string, AccessChainItem>()
    const stepMap = new Map<string, AccessChainItem>()
    const bizMap = new Map<string, AccessChainItem>()

    accessors.forEach((a) => {
      if (a.impl_id && !implMap.has(a.impl_id)) {
        implMap.set(a.impl_id, a)
      }
      if (a.step_id && !stepMap.has(a.step_id)) {
        stepMap.set(a.step_id, a)
      }
      if (a.process_id && !bizMap.has(a.process_id)) {
        bizMap.set(a.process_id, a)
      }
    })

    const impls = Array.from(implMap.values())
    const steps = Array.from(stepMap.values())
    const biz = Array.from(bizMap.values())

    impls.forEach((a, idx) => {
      nodes.push({
        id: `impl:${a.impl_id}`,
        data: { label: `${a.impl_name}\n${a.impl_system || ''}` },
        position: { x: 260, y: idx * 80 - 40 },
        type: 'default',
      })
    })

    steps.forEach((a, idx) => {
      if (!a.step_id) return
      nodes.push({
        id: `step:${a.step_id}`,
        data: { label: a.step_name || a.step_id },
        position: { x: -260, y: idx * 80 - 40 },
        type: 'default',
      })
    })

    biz.forEach((a, idx) => {
      if (!a.process_id) return
      nodes.push({
        id: `biz:${a.process_id}`,
        data: { label: a.process_name || a.process_id },
        position: { x: -520, y: idx * 80 - 40 },
        type: 'default',
      })
    })

    return nodes
  }, [selectedResource, accessors])

  const graphEdges: Edge[] = useMemo(() => {
    if (!selectedResource) return []
    const edges: Edge[] = []

    accessors.forEach((a, idx) => {
      const implNodeId = `impl:${a.impl_id}`
      const resourceNodeId = `resource:${selectedResource.resource_id}`
      edges.push({
        id: `e-impl-${idx}`,
        source: implNodeId,
        target: resourceNodeId,
      })

      if (a.step_id) {
        const stepNodeId = `step:${a.step_id}`
        edges.push({
          id: `e-step-impl-${idx}`,
          source: stepNodeId,
          target: implNodeId,
        })
      }

      if (a.process_id && a.step_id) {
        const bizNodeId = `biz:${a.process_id}`
        const stepNodeId = `step:${a.step_id}`
        edges.push({
          id: `e-biz-step-${idx}`,
          source: bizNodeId,
          target: stepNodeId,
        })
      }
    })

    return edges
  }, [selectedResource, accessors])

  return (
    <div style={{ display: 'flex' }}>
      <div
        style={{
          flex: 1,
          paddingRight: drawerVisible ? 24 : 0,
          transition: 'padding-right 0.25s ease',
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
        <div style={{ marginTop: 16, textAlign: 'right' }}>
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
              overflow: 'auto',
            }}
          >
          <Space
            style={{
              width: '100%',
              justifyContent: 'space-between',
              marginBottom: 16,
            }}
          >
            <Typography.Title level={5} style={{ margin: 0 }}>
              {creatingNew ? '新建数据资源' : '数据资源详情'}
            </Typography.Title>
            <Space>
              {selectedResource && !creatingNew ? (
                <Popconfirm
                  title="确认删除该资源？"
                  onConfirm={handleDelete}
                  okText="删除"
                  cancelText="取消"
                >
                  <Button danger size="small">
                    删除
                  </Button>
                </Popconfirm>
              ) : null}
              <Button
                size="small"
                onClick={() => {
                  setDrawerVisible(false)
                }}
              >
                关闭
              </Button>
            </Space>
          </Space>

          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            items={[
              { key: 'basic', label: '基本信息' },
              { key: 'accessors', label: '访问关系' },
              { key: 'graph', label: '图视图' },
            ]}
          />
          {activeTab === 'basic' && (
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
              <Space>
                <Button type="primary" onClick={handleSaveBasic}>
                  保存
                </Button>
                {creatingNew && (
                  <Button
                    onClick={() => {
                      form.resetFields()
                    }}
                  >
                    重置
                  </Button>
                )}
              </Space>
            </Form>
          )}
          {activeTab === 'accessors' && (
            <div style={{ marginTop: 16 }}>
              {selectedResource ? (
                <Table<AccessChainItem>
                  size="small"
                  rowKey={(r, idx) => `${r.impl_id}-${idx}`}
                  columns={[
                    {
                      title: '流程',
                      dataIndex: 'process_name',
                      width: 140,
                      render: (value, record) => value || record.process_id || '-',
                    },
                    {
                      title: '步骤',
                      dataIndex: 'step_name',
                      width: 160,
                      render: (value, record) => value || record.step_id || '-',
                    },
                    {
                      title: '实现',
                      dataIndex: 'impl_name',
                      render: (value, record) => (
                        <span>
                          {value}
                          {record.impl_system ? (
                            <Tag style={{ marginLeft: 8 }}>{record.impl_system}</Tag>
                          ) : null}
                        </span>
                      ),
                    },
                    {
                      title: '访问类型',
                      dataIndex: 'access_type',
                      width: 110,
                    },
                  ]}
                  dataSource={accessors}
                  pagination={false}
                  loading={loadingDetail}
                />
              ) : (
                <Typography.Paragraph type="secondary">
                  请先在上方选择一个数据资源
                </Typography.Paragraph>
              )}
            </div>
          )}
          {activeTab === 'graph' && (
            <div style={{ height: 360, marginTop: 16 }}>
              {selectedResource ? (
                <ReactFlow
                  nodes={graphNodes}
                  edges={graphEdges}
                  fitView
                >
                  <Background />
                  <Controls />
                </ReactFlow>
              ) : (
                <Typography.Paragraph type="secondary">
                  请先在上方选择一个数据资源
                </Typography.Paragraph>
              )}
            </div>
          )}
          </div>
        )}
      </div>
    </div>
  )
}

const ResourceLibraryPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('business')

  return (
    <div>
      <Title level={3} style={{ marginBottom: 16 }}>
        资源库
      </Title>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          { key: 'business', label: '流程', children: <BusinessTab /> },
          { key: 'step', label: '步骤', children: <StepTab /> },
          { key: 'implementation', label: '实现', children: <ImplementationTab /> },
          { key: 'resource', label: '数据资源', children: <DataResourceTab /> },
        ]}
      />
    </div>
  )
}

export default ResourceLibraryPage

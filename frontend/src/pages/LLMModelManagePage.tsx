import React, { useEffect, useState } from 'react'
import { Card, Typography, Button, Space, Tag, Modal, Form, Input, InputNumber, Select, Popconfirm, Avatar, Spin, Row, Col } from 'antd'
import { PlusOutlined, ReloadOutlined, FileTextOutlined, LinkOutlined, ExperimentOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'

import {
  listLLMModels,
  createLLMModel,
  updateLLMModel,
  deleteLLMModel,
  testLLMModel,
  testSavedLLMModel,
  type AIModelOut,
  type AIModelCreate,
  type AIModelUpdate,
  type ProviderType,
  LITELLM_PROVIDERS,
} from '../api/llmModels'
import { showError, showSuccess, showInfo } from '../utils/message'

const { Title, Text } = Typography
const { Option } = Select

interface ModelFormValues {
  name: string
  provider_type: ProviderType
  provider?: string           // LiteLLM 模式下选择
  model_name: string
  api_key: string
  gateway_endpoint?: string   // 自定义网关模式下填写
  temperature?: number
  max_tokens?: number
  timeout?: number
}

interface ModelModalProps {
  open: boolean
  mode: 'create' | 'edit'
  initial?: AIModelOut | null
  onOk: () => void
  onCancel: () => void
}

const ModelModal: React.FC<ModelModalProps> = ({ open, mode, initial, onOk, onCancel }) => {
  const [form] = Form.useForm<ModelFormValues>()
  const [confirmLoading, setConfirmLoading] = useState(false)
  const [testing, setTesting] = useState(false)
  const [providerType, setProviderType] = useState<ProviderType>('litellm')

  useEffect(() => {
    if (!open) return

    if (mode === 'edit' && initial) {
      const pt = initial.provider_type || 'litellm'
      setProviderType(pt)
      form.setFieldsValue({
        name: initial.name,
        provider_type: pt,
        provider: initial.provider ?? undefined,
        model_name: initial.model_name,
        gateway_endpoint: initial.gateway_endpoint ?? undefined,
        temperature: initial.temperature,
        max_tokens: initial.max_tokens ?? undefined,
        timeout: initial.timeout ?? 120,
        api_key: '', // 不回显已有密钥，留空表示不修改
      })
    } else {
      form.resetFields()
      setProviderType('litellm')
      form.setFieldsValue({
        provider_type: 'litellm',
        temperature: 0.7,
        timeout: 120,
      })
    }
  }, [open, mode, initial, form])

  const handleProviderTypeChange = (value: ProviderType) => {
    setProviderType(value)
    // 切换类型时清空对应的字段
    if (value === 'litellm') {
      form.setFieldsValue({ gateway_endpoint: undefined })
    } else {
      form.setFieldsValue({ provider: undefined })
    }
  }

  const handleOk = async () => {
    try {
      const values = await form.validateFields()
      setConfirmLoading(true)

      if (mode === 'create') {
        const payload: AIModelCreate = {
          name: values.name,
          provider_type: values.provider_type,
          provider: values.provider_type === 'litellm' ? (values.provider || '') : '',
          model_name: values.model_name,
          api_key: values.api_key,
          gateway_endpoint: values.provider_type === 'custom_gateway' ? values.gateway_endpoint : null,
          temperature: values.temperature ?? 0.7,
          max_tokens: values.max_tokens ?? null,
          timeout: values.timeout ?? 120,
        }
        await createLLMModel(payload)
        showSuccess('创建模型成功')
      } else if (mode === 'edit' && initial) {
        const payload: AIModelUpdate = {
          name: values.name,
          provider_type: values.provider_type,
          provider: values.provider_type === 'litellm' ? (values.provider || '') : '',
          model_name: values.model_name,
          gateway_endpoint: values.provider_type === 'custom_gateway' ? values.gateway_endpoint : null,
          temperature: values.temperature ?? 0.7,
          max_tokens: values.max_tokens ?? null,
          timeout: values.timeout ?? 120,
        }
        // api_key 仅在用户输入时更新
        if (values.api_key) {
          payload.api_key = values.api_key
        }
        await updateLLMModel(initial.id, payload)
        showSuccess('保存模型成功')
      }

      onOk()
    } catch (e: any) {
      if (e?.errorFields) return
      showError('保存失败')
    } finally {
      setConfirmLoading(false)
    }
  }

  const handleTest = async () => {
    try {
      const values = await form.validateFields()
      if (!values.api_key) {
        showInfo('请先填写 API 密钥再进行测试')
        return
      }

      setTesting(true)
      const payload: AIModelCreate = {
        name: values.name,
        provider_type: values.provider_type,
        provider: values.provider_type === 'litellm' ? (values.provider || '') : '',
        model_name: values.model_name,
        api_key: values.api_key,
        gateway_endpoint: values.provider_type === 'custom_gateway' ? values.gateway_endpoint : null,
        temperature: values.temperature ?? 0.7,
        max_tokens: values.max_tokens ?? null,
        timeout: values.timeout ?? 120,
      }
      const res = await testLLMModel(payload)
      if (res.ok) {
        showSuccess('模型连通性测试成功')
      } else {
        showError('模型连通性测试失败')
      }
    } catch (e: any) {
      if (e?.errorFields) return
      showError('测试失败')
    } finally {
      setTesting(false)
    }
  }

  const title = mode === 'create' ? '新增 AI 模型配置' : '编辑 AI 模型配置'

  return (
    <Modal
      open={open}
      title={title}
      onOk={handleOk}
      onCancel={onCancel}
      confirmLoading={confirmLoading}
      okText={mode === 'create' ? '创建' : '保存'}
      cancelText="取消"
      maskClosable={false}
      destroyOnClose
      width={560}
    >
      <Form<ModelFormValues> layout="vertical" form={form} size="middle">
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item
              label="配置名称"
              name="name"
              rules={[{ required: true, message: '请输入' }]}
            >
              <Input placeholder="如：gemini-2.5-flash 生产环境" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item
              label="接入方式"
              name="provider_type"
              rules={[{ required: true, message: '请选择' }]}
            >
              <Select onChange={handleProviderTypeChange}>
                <Option value="litellm">通用提供商</Option>
                <Option value="custom_gateway">自定义网关(暂无法流式响应)</Option>
              </Select>
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={16}>
          {providerType === 'litellm' ? (
            <Col span={12}>
              <Form.Item
                label="提供商"
                name="provider"
                rules={[{ required: true, message: '请选择' }]}
              >
                <Select placeholder="选择提供商">
                  {LITELLM_PROVIDERS.map((p) => (
                    <Option key={p.value} value={p.value}>
                      {p.label}
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          ) : (
            <Col span={24}>
              <Form.Item
                label="网关端点"
                name="gateway_endpoint"
                rules={[{ required: true, message: '请输入网关 URL' }]}
              >
                <Input placeholder="https://your-newapi.com/v1/chat/completions" />
              </Form.Item>
            </Col>
          )}
          {providerType === 'litellm' && (
            <Col span={12}>
              <Form.Item
                label="模型名称"
                name="model_name"
                rules={[{ required: true, message: '请输入' }]}
              >
                <Input placeholder="如：gemini-2.5-flash" />
              </Form.Item>
            </Col>
          )}
        </Row>

        {providerType === 'custom_gateway' && (
          <Form.Item
            label="模型名称"
            name="model_name"
            rules={[{ required: true, message: '请输入模型名称' }]}
          >
            <Input placeholder="如：gemini-2.5-flash、claude-4.5-opus" />
          </Form.Item>
        )}

        <Form.Item
          label="API 密钥"
          name="api_key"
          rules={mode === 'create' ? [{ required: true, message: '请输入 API 密钥' }] : []}
          extra={mode === 'edit' ? '留空表示不修改' : undefined}
        >
          <Input.Password placeholder="sk-..." />
        </Form.Item>

        <Row gutter={16}>
          <Col span={8}>
            <Form.Item label="温度" name="temperature">
              <InputNumber min={0} max={2} step={0.1} style={{ width: '100%' }} placeholder="0.7" />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item label="最大 Tokens" name="max_tokens">
              <InputNumber min={0} step={256} style={{ width: '100%' }} placeholder="可选" />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item label="超时(秒)" name="timeout">
              <InputNumber min={10} max={600} step={10} style={{ width: '100%' }} placeholder="120" />
            </Form.Item>
          </Col>
        </Row>

        {mode === 'create' && (
          <Form.Item style={{ marginBottom: 0 }}>
            <Button
              icon={<ExperimentOutlined />}
              onClick={handleTest}
              loading={testing}
            >
              测试连接
            </Button>
          </Form.Item>
        )}
      </Form>
    </Modal>
  )
}

const LLMModelManagePage: React.FC = () => {
  const [models, setModels] = useState<AIModelOut[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [modalMode, setModalMode] = useState<'create' | 'edit'>('create')
  const [editingModel, setEditingModel] = useState<AIModelOut | null>(null)
  const [testingSavedId, setTestingSavedId] = useState<number | null>(null)

  const fetchModels = async () => {
    setLoading(true)
    try {
      const data = await listLLMModels()
      setModels(data)
    } catch (e) {
      showError('加载模型列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchModels()
  }, [])

  const handleOpenCreate = () => {
    setModalMode('create')
    setEditingModel(null)
    setModalOpen(true)
  }

  const handleOpenEdit = (record: AIModelOut) => {
    setModalMode('edit')
    setEditingModel(record)
    setModalOpen(true)
  }

  const handleDelete = async (record: AIModelOut) => {
    try {
      await deleteLLMModel(record.id)
      showSuccess('删除模型成功')
      fetchModels()
    } catch (e: any) {
      showError('删除模型失败')
    }
  }

  const handleTestSaved = async (record: AIModelOut) => {
    try {
      setTestingSavedId(record.id)
      const res = await testSavedLLMModel(record.id)
      if (res.ok) {
        showSuccess('模型连通性测试成功')
      } else {
        showError('模型连通性测试失败')
      }
    } catch (e) {
      showError('测试失败')
    } finally {
      setTestingSavedId(null)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, height: '100%' }}>
      {/* 顶部标题区 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Title level={4} style={{ marginBottom: 4 }}>
            AI 模型管理
          </Title>
          <Text type="secondary">管理你的大语言模型配置（接入方式、密钥与参数等）。</Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchModels}>
            刷新
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleOpenCreate}>
            添加模型
          </Button>
        </Space>
      </div>

      {/* 列表区：三列瀑布式卡片 */}
      <div style={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>
        {loading ? (
          <Card style={{ marginTop: 8, borderRadius: 12 }}>
            <div style={{ padding: 16, textAlign: 'center' }}>
              <Spin />
            </div>
          </Card>
        ) : models.length === 0 ? (
          <Card style={{ marginTop: 8, borderRadius: 12 }}>
            <div style={{ padding: 16, textAlign: 'center', color: '#999' }}>暂无模型配置</div>
          </Card>
        ) : (
          <div
            style={{
              width: '100%',
              marginTop: 8,
              display: 'grid',
              gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
              gap: 16,
            }}
          >
            {models.map((m) => {
              const isCustomGateway = m.provider_type === 'custom_gateway'
              const typeLabel = isCustomGateway ? '自定义网关' : (m.provider || '默认').toUpperCase()
              const endpointDisplay = isCustomGateway && m.gateway_endpoint
                ? new URL(m.gateway_endpoint).host
                : null

              const modelLabel = m.provider ? `${m.provider}/${m.model_name}` : m.model_name

              return (
                <Card
                  key={m.id}
                  hoverable
                  bodyStyle={{
                    padding: '16px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 16,
                    height: 160,
                  }}
                  style={{
                    breakInside: 'avoid',
                    marginBottom: 16,
                    borderRadius: 12,
                    border: m.is_active ? '1px solid #1677ff' : '1px solid #f0f0f0',
                    boxShadow: m.is_active
                      ? '0 0 0 1px rgba(22,119,255,0.15), 0 6px 16px rgba(15,23,42,0.08)'
                      : '0 2px 8px rgba(15,23,42,0.04)',
                    background: m.is_active
                      ? 'linear-gradient(135deg, #f0f5ff, #ffffff)'
                      : '#ffffff',
                    transition: 'all 0.2s ease',
                  }}
                >
                  {/* 左侧：头像 */}
                  <Avatar
                    size={40}
                    style={{
                      width: 40,
                      height: 40,
                      lineHeight: '40px',
                      backgroundColor: isCustomGateway ? '#722ed1' : '#1677ff',
                      fontSize: 16,
                      flexShrink: 0,
                    }}
                  >
                    {isCustomGateway
                      ? 'GW'
                      : (m.provider || 'LL').slice(0, 2).toUpperCase()}
                  </Avatar>
                  {/* 中间：内容区 */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <Text strong style={{ fontSize: 14, marginBottom: 4, display: 'block' }}>
                      {m.name}
                    </Text>
                    <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 4 }}>
                      {m.model_name}
                    </div>
                    <Space size={6} style={{ flexWrap: 'wrap' }}>
                      <Tag color={m.is_active ? 'blue' : 'default'} style={{ borderRadius: 999 }}>
                        {m.is_active ? '已启用' : '未启用'}
                      </Tag>
                      <Tag color={isCustomGateway ? 'purple' : 'default'}>{typeLabel}</Tag>
                      {m.temperature !== undefined && (
                        <Tag color="geekblue">temp {m.temperature}</Tag>
                      )}
                      {m.max_tokens && (
                        <Tag color="gold">max {m.max_tokens}</Tag>
                      )}
                      {m.timeout && (
                        <Tag color="default">timeout {m.timeout}s</Tag>
                      )}
                    </Space>
                  </div>
                  {/* 右侧：操作按钮竖向排列 */}
                  <div
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 8,
                      flexShrink: 0,
                    }}
                  >
                    <Button
                      type="text"
                      size="small"
                      icon={<LinkOutlined />}
                      loading={testingSavedId === m.id}
                      onClick={() => handleTestSaved(m)}
                    />
                    <Button
                      type="text"
                      size="small"
                      icon={<EditOutlined />}
                      onClick={() => handleOpenEdit(m)}
                    />
                    <Popconfirm
                      title="确认删除该模型？"
                      onConfirm={() => handleDelete(m)}
                    >
                      <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                    </Popconfirm>
                  </div>
                </Card>
              )
            })}
          </div>
        )}
      </div>

      <ModelModal
        open={modalOpen}
        mode={modalMode}
        initial={editingModel}
        onOk={() => {
          setModalOpen(false)
          fetchModels()
        }}
        onCancel={() => setModalOpen(false)}
      />
    </div>
  )
}

export default LLMModelManagePage

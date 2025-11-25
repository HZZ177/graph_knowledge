import React, { useEffect, useState } from 'react'
import { Card, Typography, Button, Space, Tag, Modal, Form, Input, InputNumber, Select, Popconfirm, Avatar, Spin } from 'antd'
import { PlusOutlined, ReloadOutlined, FileTextOutlined, LinkOutlined, ExperimentOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'

import {
  listLLMModels,
  createLLMModel,
  updateLLMModel,
  deleteLLMModel,
  activateLLMModel,
  testLLMModel,
  testSavedLLMModel,
  type AIModelOut,
  type AIModelCreate,
  type AIModelUpdate,
} from '../api/llmModels'
import { showError, showSuccess, showInfo } from '../utils/message'

const { Title, Text } = Typography
const { Option } = Select

interface ModelFormValues {
  name: string
  provider?: string
  model_name: string
  api_key: string
  base_url?: string
  temperature?: number
  max_tokens?: number
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

  useEffect(() => {
    if (!open) return

    if (mode === 'edit' && initial) {
      form.setFieldsValue({
        name: initial.name,
        provider: (initial.provider ?? undefined) as string | undefined,
        model_name: initial.model_name,
        base_url: initial.base_url ?? undefined,
        temperature: initial.temperature,
        max_tokens: initial.max_tokens ?? undefined,
        api_key: '', // 不回显已有密钥，留空表示不修改
      })
    } else {
      form.resetFields()
      form.setFieldsValue({
        temperature: 0.7,
      })
    }
  }, [open, mode, initial, form])

  const handleOk = async () => {
    try {
      const values = await form.validateFields()
      setConfirmLoading(true)

      if (mode === 'create') {
        const payload: AIModelCreate = {
          name: values.name,
          provider: values.provider || '',
          model_name: values.model_name,
          api_key: values.api_key,
          base_url: values.base_url || null,
          temperature: values.temperature ?? 0.7,
          max_tokens: values.max_tokens ?? null,
        }
        await createLLMModel(payload)
        showSuccess('创建模型成功')
      } else if (mode === 'edit' && initial) {
        const payload: AIModelUpdate = {
          name: values.name,
          provider: values.provider || '',
          model_name: values.model_name,
          base_url: values.base_url || null,
          temperature: values.temperature ?? 0.7,
          max_tokens: values.max_tokens ?? null,
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
        provider: values.provider || '',
        model_name: values.model_name,
        api_key: values.api_key,
        base_url: values.base_url || null,
        temperature: values.temperature ?? 0.7,
        max_tokens: values.max_tokens ?? null,
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
    >
      <Form<ModelFormValues> layout="vertical" form={form}>
        <Form.Item
          label="配置名称"
          name="name"
          rules={[{ required: true, message: '请输入配置名称' }]}
        >
          <Input placeholder="请输入配置名称" />
        </Form.Item>

        <Form.Item
          label="模型提供商"
          name="provider"
        >
          <Input placeholder="可选，例如：openai、ollama 等；留空则直接使用模型名称" />
        </Form.Item>

        <Form.Item
          label="模型名称"
          name="model_name"
          rules={[{ required: true, message: '请输入模型名称' }]}
        >
          <Input placeholder="例如：gpt-4o 或 llama3.2" />
        </Form.Item>

        <Form.Item
          label="API 密钥"
          name="api_key"
          rules={mode === 'create' ? [{ required: true, message: '请输入 API 密钥' }] : []}
          extra={mode === 'edit' ? '留空表示不修改当前密钥' : undefined}
        >
          <Input.Password placeholder="请输入 API 密钥" />
        </Form.Item>

        <Form.Item
          label="API 基础 URL"
          name="base_url"
        >
          <Input placeholder="可选，例如：https://api.openai.com/v1" />
        </Form.Item>

        <Form.Item label="温度" name="temperature">
          <InputNumber min={0} max={2} step={0.1} style={{ width: '100%' }} />
        </Form.Item>

        <Form.Item label="最大输出 Tokens" name="max_tokens">
          <InputNumber min={0} step={256} style={{ width: '100%' }} />
        </Form.Item>

        {mode === 'create' && (
          <Form.Item>
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
  const [currentActiveId, setCurrentActiveId] = useState<number | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [modalMode, setModalMode] = useState<'create' | 'edit'>('create')
  const [editingModel, setEditingModel] = useState<AIModelOut | null>(null)
  const [testingSavedId, setTestingSavedId] = useState<number | null>(null)
  const [activating, setActivating] = useState(false)

  const fetchModels = async () => {
    setLoading(true)
    try {
      const data = await listLLMModels()
      setModels(data)
      const active = data.find((m) => m.is_active)
      setCurrentActiveId(active ? active.id : null)
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

  const handleActivate = async (record: AIModelOut) => {
    try {
      setActivating(true)
      await activateLLMModel(record.id)
      showSuccess('已设置为当前激活模型')
      fetchModels()
    } catch (e) {
      showError('激活模型失败')
    } finally {
      setActivating(false)
    }
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

  const handleChangeActive = async (value: number) => {
    const record = models.find((m) => m.id === value)
    if (!record) return
    await handleActivate(record)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, height: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Title level={4} style={{ marginBottom: 0 }}>
            AI 模型管理
          </Title>
          <Text type="secondary">管理你的大语言模型配置，并选择需要使用的当前模型。</Text>
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

      <Card>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 16,
          }}
        >
          <Space align="center">
            <Text strong>当前使用的模型：</Text>
            <Select
              style={{ minWidth: 260 }}
              placeholder="选择模型"
              value={currentActiveId ?? undefined}
              onChange={handleChangeActive}
              loading={activating}
            >
              {models.map((m) => {
                const modelLabel = m.provider ? `${m.provider}/${m.model_name}` : m.model_name
                return (
                  <Option key={m.id} value={m.id}>
                    {m.name}（{modelLabel}）
                  </Option>
                )
              })}
            </Select>
          </Space>
          <Text type="secondary">共 {models.length} 个模型配置</Text>
        </div>
      </Card>

      <div style={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>
        {loading ? (
          <Card style={{ marginTop: 8 }}>
            <div style={{ padding: 16, textAlign: 'center' }}>
              <Spin />
            </div>
          </Card>
        ) : models.length === 0 ? (
          <Card style={{ marginTop: 8 }}>
            <div style={{ padding: 16, textAlign: 'center', color: '#999' }}>暂无模型配置</div>
          </Card>
        ) : (
          <Space direction="vertical" style={{ width: '100%', marginTop: 8 }} size={12}>
            {models.map((m) => {
              const providerLabel = (m.provider || '默认').toUpperCase()
              return (
                <Card
                  key={m.id}
                  bodyStyle={{ padding: '12px 16px' }}
                  style={{ borderRadius: 8, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 16,
                    }}
                  >
                    <Space size={16}>
                      <Avatar
                        size={40}
                        style={{ backgroundColor: '#1677ff' }}
                        icon={<FileTextOutlined />}
                      />
                      <div>
                        <Space size={8} align="center">
                          <Text strong>{m.name}</Text>
                          {m.is_active && <Tag color="blue">启用</Tag>}
                        </Space>
                        <Space size={8} style={{ marginTop: 4, flexWrap: 'wrap' }}>
                          <Tag>{providerLabel}</Tag>
                          <Tag>{m.model_name}</Tag>
                          {m.base_url && <Tag>{m.base_url}</Tag>}
                        </Space>
                      </div>
                    </Space>
                    <Space size="middle">
                      <Button
                        type="text"
                        icon={<LinkOutlined />}
                        loading={testingSavedId === m.id}
                        onClick={() => handleTestSaved(m)}
                      />
                      <Button
                        type="text"
                        icon={<EditOutlined />}
                        onClick={() => handleOpenEdit(m)}
                      />
                      <Popconfirm
                        title="确认删除该模型？"
                        onConfirm={() => handleDelete(m)}
                      >
                        <Button type="text" danger icon={<DeleteOutlined />} />
                      </Popconfirm>
                    </Space>
                  </div>
                </Card>
              )
            })}
          </Space>
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

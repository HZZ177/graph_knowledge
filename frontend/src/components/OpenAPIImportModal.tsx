import React, { useState, useMemo, useCallback } from 'react'
import {
  Modal,
  Select,
  Upload,
  Table,
  Input,
  Checkbox,
  Space,
  Typography,
  message,
  Button,
  Tag,
  Spin,
} from 'antd'
import { InboxOutlined, SearchOutlined } from '@ant-design/icons'
import type { UploadFile, UploadProps } from 'antd'
import type { ImplementationCreatePayload } from '../api/resourceNodes'

const { Dragger } = Upload
const { Text } = Typography

// OpenAPI 解析出的接口项
interface ParsedApiItem {
  key: string
  method: string
  path: string
  name: string  // method + path
  description: string
}

// OpenAPI JSON 结构（简化）
interface OpenAPISpec {
  openapi?: string
  info?: { title?: string; version?: string }
  servers?: Array<{ url?: string; description?: string }>
  paths?: Record<string, Record<string, {
    description?: string
    summary?: string
    operationId?: string
    tags?: string[]
  }>>
}

interface OpenAPIImportModalProps {
  open: boolean
  onCancel: () => void
  onImport: (items: ImplementationCreatePayload[]) => Promise<void>
}

const IMPL_SYSTEMS = [
  { value: 'admin-vehicle-owner', label: 'admin-vehicle-owner' },
  { value: 'owner-center', label: 'owner-center' },
  { value: 'vehicle-pay-center', label: 'vehicle-pay-center' },
]

const IMPL_TYPES = [
  { value: 'api', label: '接口' },
  // { value: 'function', label: '内部方法' },
  // { value: 'job', label: '定时任务' },
]

export default function OpenAPIImportModal({
  open,
  onCancel,
  onImport,
}: OpenAPIImportModalProps) {
  // 步骤：1 = 选择文件，2 = 预览选择
  const [step, setStep] = useState<1 | 2>(1)
  
  // 配置
  const [system, setSystem] = useState<string>('owner-center')
  const [implType, setImplType] = useState<string>('api')
  
  // 解析结果
  const [parsedItems, setParsedItems] = useState<ParsedApiItem[]>([])
  const [selectedKeys, setSelectedKeys] = useState<string[]>([])
  const [searchText, setSearchText] = useState('')
  const [pageSize, setPageSize] = useState(10)
  
  // 状态
  const [parsing, setParsing] = useState(false)
  const [importing, setImporting] = useState(false)

  // 重置状态
  const resetState = useCallback(() => {
    setStep(1)
    setParsedItems([])
    setSelectedKeys([])
    setSearchText('')
    setParsing(false)
    setImporting(false)
  }, [])

  // 关闭弹窗
  const handleCancel = useCallback(() => {
    resetState()
    onCancel()
  }, [resetState, onCancel])

  // 解析 OpenAPI JSON
  const parseOpenAPI = useCallback((content: string): ParsedApiItem[] => {
    try {
      const spec: OpenAPISpec = JSON.parse(content)
      const items: ParsedApiItem[] = []
      
      if (!spec.paths) {
        message.warning('OpenAPI 文件中没有找到 paths 定义')
        return []
      }
      
      // 从 servers[0].url 提取服务前缀（最后一节路径）
      let servicePrefix = ''
      if (spec.servers && spec.servers[0]?.url) {
        try {
          const url = new URL(spec.servers[0].url)
          // 获取路径部分，如 /vehicle-pay-center
          const pathname = url.pathname
          if (pathname && pathname !== '/') {
            // 移除开头的斜杠，保留路径如 vehicle-pay-center
            servicePrefix = pathname.startsWith('/') ? pathname.slice(1) : pathname
          }
        } catch {
          // URL 解析失败，尝试直接提取最后一节
          const urlStr = spec.servers[0].url
          const lastSlashIdx = urlStr.lastIndexOf('/')
          if (lastSlashIdx > 0 && lastSlashIdx < urlStr.length - 1) {
            servicePrefix = urlStr.slice(lastSlashIdx + 1)
          }
        }
      }
      
      // 遍历 paths
      Object.entries(spec.paths).forEach(([path, methods]) => {
        Object.entries(methods).forEach(([method, detail]) => {
          // 跳过非 HTTP 方法的字段（如 parameters）
          if (!['get', 'post', 'put', 'delete', 'patch', 'head', 'options'].includes(method.toLowerCase())) {
            return
          }
          
          const methodUpper = method.toUpperCase()
          // 拼接服务前缀和路径
          const fullPath = servicePrefix ? `${servicePrefix}${path}` : path
          const name = `${methodUpper} ${fullPath}`
          const description = detail.description || detail.summary || ''
          
          items.push({
            key: name,
            method: methodUpper,
            path: fullPath,
            name,
            description,
          })
        })
      })
      
      return items
    } catch (e) {
      message.error('JSON 解析失败，请检查文件格式')
      return []
    }
  }, [])

  // 文件上传处理
  const uploadProps: UploadProps = {
    name: 'file',
    multiple: false,
    accept: '.json',
    showUploadList: false,
    beforeUpload: (file) => {
      setParsing(true)
      
      const reader = new FileReader()
      reader.onload = (e) => {
        const content = e.target?.result as string
        const items = parseOpenAPI(content)
        
        if (items.length > 0) {
          setParsedItems(items)
          setSelectedKeys(items.map(i => i.key))  // 默认全选
          setStep(2)
          message.success(`成功解析 ${items.length} 个接口`)
        }
        
        setParsing(false)
      }
      reader.onerror = () => {
        message.error('文件读取失败')
        setParsing(false)
      }
      reader.readAsText(file)
      
      return false  // 阻止自动上传
    },
  }

  // 过滤后的列表
  const filteredItems = useMemo(() => {
    if (!searchText.trim()) return parsedItems
    const lower = searchText.toLowerCase()
    return parsedItems.filter(
      item => item.name.toLowerCase().includes(lower) || 
              item.description.toLowerCase().includes(lower)
    )
  }, [parsedItems, searchText])

  // 全选/取消全选（针对过滤后的列表）
  const handleSelectAll = useCallback((checked: boolean) => {
    if (checked) {
      const newKeys = new Set(selectedKeys)
      filteredItems.forEach(item => newKeys.add(item.key))
      setSelectedKeys(Array.from(newKeys))
    } else {
      const filteredKeys = new Set(filteredItems.map(i => i.key))
      setSelectedKeys(selectedKeys.filter(k => !filteredKeys.has(k)))
    }
  }, [filteredItems, selectedKeys])

  // 当前过滤列表的选中状态
  const filteredSelectedKeys = useMemo(() => {
    const filteredKeySet = new Set(filteredItems.map(i => i.key))
    return selectedKeys.filter(k => filteredKeySet.has(k))
  }, [filteredItems, selectedKeys])

  const isAllSelected = filteredItems.length > 0 && 
    filteredItems.every(item => selectedKeys.includes(item.key))
  const isIndeterminate = filteredSelectedKeys.length > 0 && 
    filteredSelectedKeys.length < filteredItems.length

  // 确认导入
  const handleImport = useCallback(async () => {
    if (selectedKeys.length === 0) {
      message.warning('请至少选择一个接口')
      return
    }
    
    setImporting(true)
    
    try {
      const selectedItems = parsedItems.filter(item => selectedKeys.includes(item.key))
      const payloads: ImplementationCreatePayload[] = selectedItems.map(item => ({
        name: item.name,
        type: implType,
        system: system,
        description: item.description || undefined,
      }))
      
      await onImport(payloads)
      handleCancel()
    } catch (e) {
      // 错误在外部处理
    } finally {
      setImporting(false)
    }
  }, [selectedKeys, parsedItems, system, implType, onImport, handleCancel])

  // 返回上一步
  const handleBack = useCallback(() => {
    setStep(1)
    setParsedItems([])
    setSelectedKeys([])
    setSearchText('')
  }, [])

  // 表格列定义
  const columns = [
    {
      title: '方法',
      dataIndex: 'method',
      width: 80,
      render: (method: string) => {
        const colors: Record<string, string> = {
          GET: 'green',
          POST: 'blue',
          PUT: 'orange',
          DELETE: 'red',
          PATCH: 'purple',
        }
        return <Tag color={colors[method] || 'default'}>{method}</Tag>
      },
    },
    {
      title: '路径',
      dataIndex: 'path',
      ellipsis: true,
    },
    {
      title: '描述',
      dataIndex: 'description',
      ellipsis: true,
      render: (desc: string) => desc || <Text type="secondary">无描述</Text>,
    },
  ]

  return (
    <Modal
      title="导入实现单元 - OpenAPI"
      open={open}
      onCancel={handleCancel}
      width={800}
      styles={{ body: { minHeight: 480 } }}
      footer={
        step === 1 ? null : (
          <Space>
            <Button onClick={handleBack}>返回</Button>
            <Button 
              type="primary" 
              onClick={handleImport}
              loading={importing}
              disabled={selectedKeys.length === 0}
            >
              导入选中 ({selectedKeys.length})
            </Button>
          </Space>
        )
      }
      destroyOnClose
    >
      {step === 1 ? (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {/* 配置区 */}
          <Space size="large">
            <Space>
              <Text>所属系统：</Text>
              <Select
                value={system}
                onChange={setSystem}
                options={IMPL_SYSTEMS}
                style={{ width: 150 }}
              />
            </Space>
            <Space>
              <Text>类型：</Text>
              <Select
                value={implType}
                onChange={setImplType}
                options={IMPL_TYPES}
                style={{ width: 120 }}
              />
            </Space>
          </Space>
          
          {/* 文件上传区 */}
          <Spin spinning={parsing} tip="解析中...">
            <Dragger {...uploadProps} style={{ padding: '20px 0' }}>
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">点击或拖拽 OpenAPI JSON 文件到此区域</p>
              <p className="ant-upload-hint">
                支持 OpenAPI 3.x 格式的 JSON 文件（如 openapi.json）
              </p>
            </Dragger>
          </Spin>
        </Space>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, height: '100%', minHeight: 460 }}>
          {/* 配置显示 */}
          <Space>
            <Tag>系统: {system}</Tag>
            <Tag>类型: 接口</Tag>
            <Tag color="blue">共解析 {parsedItems.length} 个接口</Tag>
          </Space>
          
          {/* 搜索和全选 */}
          <Space style={{ width: '100%', justifyContent: 'space-between' }}>
            <Checkbox
              checked={isAllSelected}
              indeterminate={isIndeterminate}
              onChange={(e) => handleSelectAll(e.target.checked)}
            >
              全选当前列表
            </Checkbox>
            <Input
              placeholder="搜索接口..."
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              style={{ width: 250 }}
              allowClear
            />
          </Space>
          
          {/* 接口列表 */}
          <Table
            rowSelection={{
              selectedRowKeys: selectedKeys,
              onChange: (keys) => setSelectedKeys(keys as string[]),
            }}
            columns={columns}
            dataSource={filteredItems}
            rowKey="key"
            size="small"
            pagination={{
              pageSize,
              showSizeChanger: true,
              showTotal: (t) => `共 ${t} 条`,
              onChange: (_, size) => setPageSize(size),
            }}
          />
        </div>
      )}
    </Modal>
  )
}

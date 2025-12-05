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
import type { UploadProps } from 'antd'
import type { DataResourceCreatePayload } from '../api/dataResources'

const { Dragger } = Upload
const { Text } = Typography

// 解析出的DDL项
interface ParsedDDLItem {
  key: string
  name: string
  type: string
  system: string
  location: string
  description: string
  ddl: string
}

interface DDLImportModalProps {
  open: boolean
  onCancel: () => void
  onImport: (items: DataResourceCreatePayload[]) => Promise<void>
}

const SYSTEM_OPTIONS = [
  { value: 'C端', label: 'C端' },
  { value: 'B端', label: 'B端' },
  { value: '路侧', label: '路侧' },
  { value: '封闭', label: '封闭' },
]

const TYPE_OPTIONS = [
  { value: 'table', label: '库表' },
  { value: 'redis', label: 'Redis' },
]

export default function DDLImportModal({
  open,
  onCancel,
  onImport,
}: DDLImportModalProps) {
  // 步骤：1 = 选择文件，2 = 预览选择
  const [step, setStep] = useState<1 | 2>(1)
  
  // 配置
  const [system, setSystem] = useState<string>('C端')
  const [resourceType, setResourceType] = useState<string>('table')
  
  // 解析结果
  const [parsedItems, setParsedItems] = useState<ParsedDDLItem[]>([])
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

  // 解析JSON格式的DDL文件
  const parseJSON = useCallback((content: string, defaultSystem: string, defaultType: string): ParsedDDLItem[] => {
    try {
      const data = JSON.parse(content)
      
      // 支持两种格式：
      // 1. 数组格式：[{name, ddl, ...}, ...]
      // 2. 对象格式：{tables: [{name, ddl, ...}, ...]}
      let items = Array.isArray(data) ? data : (data.tables || data.resources || [])
      
      if (!Array.isArray(items) || items.length === 0) {
        message.warning('JSON 文件中没有找到有效的数据资源定义')
        return []
      }
      
      return items.map((item: any, index: number) => {
        const name = item.name || item.table_name || `未命名_${index}`
        return {
          key: name,
          name,
          type: item.type || defaultType,
          system: item.system || item.table_schema || defaultSystem,
          location: item.location || (item.table_schema ? `${item.table_schema}.${name}` : ''),
          description: item.description || item.table_comment || '',
          ddl: item.ddl || '',
        }
      })
    } catch (e) {
      message.error('JSON 解析失败，请检查文件格式')
      return []
    }
  }, [])

  // 文件上传处理
  const uploadProps: UploadProps = {
    name: 'file',
    multiple: false,
    accept: '.json,.sql',
    showUploadList: false,
    beforeUpload: (file) => {
      setParsing(true)
      
      const reader = new FileReader()
      reader.onload = (e) => {
        const content = e.target?.result as string
        let items: ParsedDDLItem[] = []
        
        // 根据文件扩展名判断格式
        if (file.name.endsWith('.json')) {
          items = parseJSON(content, system, resourceType)
        } else {
          message.error('目前仅支持 JSON 格式文件')
        }
        
        if (items.length > 0) {
          setParsedItems(items)
          setSelectedKeys(items.map(i => i.key))  // 默认全选
          setStep(2)
          message.success(`成功解析 ${items.length} 个数据资源`)
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
              item.description.toLowerCase().includes(lower) ||
              item.location.toLowerCase().includes(lower)
    )
  }, [parsedItems, searchText])

  // 全选/取消全选
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

  // 选中状态
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
      message.warning('请至少选择一个数据资源')
      return
    }
    
    setImporting(true)
    
    try {
      const selectedItems = parsedItems.filter(item => selectedKeys.includes(item.key))
      const payloads: DataResourceCreatePayload[] = selectedItems.map(item => ({
        name: item.name,
        type: item.type,
        system: item.system,
        location: item.location || undefined,
        description: item.description || undefined,
        ddl: item.ddl || undefined,
      }))
      
      await onImport(payloads)
      handleCancel()
    } catch (e) {
      // 错误在外部处理
    } finally {
      setImporting(false)
    }
  }, [selectedKeys, parsedItems, onImport, handleCancel])

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
      title: '表名',
      dataIndex: 'name',
      width: 200,
      ellipsis: true,
    },
    {
      title: '位置',
      dataIndex: 'location',
      width: 180,
      ellipsis: true,
      render: (loc: string) => loc || <Text type="secondary">-</Text>,
    },
    {
      title: '描述',
      dataIndex: 'description',
      ellipsis: true,
      render: (desc: string) => desc || <Text type="secondary">无描述</Text>,
    },
    {
      title: 'DDL长度',
      dataIndex: 'ddl',
      width: 100,
      render: (ddl: string) => ddl ? `${ddl.length} 字符` : '-',
    },
  ]

  return (
    <Modal
      title="导入数据资源 - DDL"
      open={open}
      onCancel={handleCancel}
      width={900}
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
              <Text>默认系统：</Text>
              <Select
                value={system}
                onChange={setSystem}
                options={SYSTEM_OPTIONS}
                style={{ width: 120 }}
              />
            </Space>
            <Space>
              <Text>默认类型：</Text>
              <Select
                value={resourceType}
                onChange={setResourceType}
                options={TYPE_OPTIONS}
                style={{ width: 120 }}
              />
            </Space>
          </Space>
          
          {/* 说明文本 */}
          <div style={{ 
            padding: '12px 16px', 
            background: '#f0f9ff', 
            border: '1px solid #bae6fd',
            borderRadius: 6
          }}>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>支持的JSON格式：</Text>
            <pre style={{ margin: 0, fontSize: 12, color: '#666' }}>
{`[
  {
    "name": "t_user_card",
    "type": "table",
    "system": "C端",
    "location": "member_db.t_user_card",
    "description": "用户卡券表",
    "ddl": "CREATE TABLE t_user_card (...)"
  }
]`}
            </pre>
          </div>
          
          {/* 文件上传区 */}
          <Spin spinning={parsing} tip="解析中...">
            <Dragger {...uploadProps} style={{ padding: '20px 0' }}>
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">点击或拖拽 JSON 文件到此区域</p>
              <p className="ant-upload-hint">
                支持 JSON 格式的数据资源定义文件
              </p>
            </Dragger>
          </Spin>
        </Space>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, height: '100%', minHeight: 460 }}>
          {/* 配置显示 */}
          <Space>
            <Tag>系统: {system}</Tag>
            <Tag>类型: {resourceType === 'table' ? '库表' : 'Redis'}</Tag>
            <Tag color="blue">共解析 {parsedItems.length} 个资源</Tag>
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
              placeholder="搜索数据资源..."
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              style={{ width: 250 }}
              allowClear
            />
          </Space>
          
          {/* 资源列表 */}
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

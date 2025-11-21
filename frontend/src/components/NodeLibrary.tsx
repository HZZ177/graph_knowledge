import React, { useState, useEffect } from 'react'
import { Tabs, List, Input, Tag, Spin, Empty } from 'antd'
import { DatabaseOutlined, ApiOutlined, FolderOutlined } from '@ant-design/icons'
import { listStepsPaged, listImplementationsPaged } from '../api/resourceNodes'
import { listDataResources } from '../api/dataResources'

const { Search } = Input

interface NodeLibraryProps {
  onDragStart?: (event: React.DragEvent, nodeType: string, nodeData: any) => void
}

const NodeLibrary: React.FC<NodeLibraryProps> = ({ onDragStart }) => {
  const [activeTab, setActiveTab] = useState('steps')
  const [searchText, setSearchText] = useState('')
  
  const [steps, setSteps] = useState<any[]>([])
  const [implementations, setImplementations] = useState<any[]>([])
  const [dataResources, setDataResources] = useState<any[]>([])
  
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadNodes()
  }, [])

  const loadNodes = async () => {
    setLoading(true)
    try {
      const [stepsData, implsData, resourcesData] = await Promise.all([
        listStepsPaged('', 1, 1000),
        listImplementationsPaged('', 1, 1000),
        listDataResources({ page: 1, page_size: 1000 }),
      ])
      setSteps(stepsData.items)
      setImplementations(implsData.items)
      setDataResources(resourcesData.items)
    } catch (error) {
      console.error('加载节点库失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const filterNodes = (nodes: any[], searchText: string) => {
    if (!searchText) return nodes
    return nodes.filter(node =>
      node.name?.toLowerCase().includes(searchText.toLowerCase()) ||
      node.description?.toLowerCase().includes(searchText.toLowerCase())
    )
  }

  const handleDragStart = (event: React.DragEvent, nodeType: string, nodeData: any) => {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('application/reactflow', nodeType)
    event.dataTransfer.setData('nodeData', JSON.stringify(nodeData))
    if (onDragStart) {
      onDragStart(event, nodeType, nodeData)
    }
  }

  const renderNodeItem = (node: any, nodeType: string) => {
    let icon = <FolderOutlined />
    let color = '#1890ff'
    
    if (nodeType === 'implementation') {
      icon = <ApiOutlined />
      color = '#52c41a'
    } else if (nodeType === 'data') {
      icon = <DatabaseOutlined />
      color = '#faad14'
    }

    return (
      <List.Item
        draggable
        onDragStart={(e) => handleDragStart(e, nodeType, node)}
        style={{
          cursor: 'grab',
          padding: '8px 12px',
          borderRadius: 4,
          marginBottom: 4,
          background: '#fafafa',
          border: '1px solid #f0f0f0',
          transition: 'all 0.2s',
        }}
        onMouseDown={(e) => {
          (e.currentTarget as HTMLElement).style.cursor = 'grabbing'
        }}
        onMouseUp={(e) => {
          (e.currentTarget as HTMLElement).style.cursor = 'grab'
        }}
        onMouseEnter={(e) => {
          const el = e.currentTarget as HTMLElement
          el.style.background = '#e6f7ff'
          el.style.borderColor = '#1890ff'
        }}
        onMouseLeave={(e) => {
          const el = e.currentTarget as HTMLElement
          el.style.background = '#fafafa'
          el.style.borderColor = '#f0f0f0'
        }}
      >
        <div style={{ width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color }}>{icon}</span>
            <span style={{ fontWeight: 500, flex: 1, fontSize: 13 }}>{node.name}</span>
          </div>
          {node.description && (
            <div style={{ 
              fontSize: 12, 
              color: '#8c8c8c', 
              marginTop: 4,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}>
              {node.description}
            </div>
          )}
          {node.system && (
            <Tag style={{ marginTop: 4, fontSize: 11 }} color="blue">
              {node.system}
            </Tag>
          )}
        </div>
      </List.Item>
    )
  }

  const tabItems = [
    {
      key: 'steps',
      label: '步骤',
      children: (
        <div>
          <Search
            placeholder="搜索步骤..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ marginBottom: 12 }}
            size="small"
          />
          {loading ? (
            <div style={{ textAlign: 'center', padding: 20 }}>
              <Spin />
            </div>
          ) : (
            <List
              dataSource={filterNodes(steps, searchText)}
              renderItem={(item) => renderNodeItem(item, 'step')}
              locale={{ emptyText: <Empty description="暂无步骤" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
              style={{ maxHeight: 'calc(100vh - 300px)', overflow: 'auto' }}
            />
          )}
        </div>
      ),
    },
    {
      key: 'implementations',
      label: '实现',
      children: (
        <div>
          <Search
            placeholder="搜索实现..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ marginBottom: 12 }}
            size="small"
          />
          {loading ? (
            <div style={{ textAlign: 'center', padding: 20 }}>
              <Spin />
            </div>
          ) : (
            <List
              dataSource={filterNodes(implementations, searchText)}
              renderItem={(item) => renderNodeItem(item, 'implementation')}
              locale={{ emptyText: <Empty description="暂无实现" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
              style={{ maxHeight: 'calc(100vh - 300px)', overflow: 'auto' }}
            />
          )}
        </div>
      ),
    },
    {
      key: 'dataResources',
      label: '数据资源',
      children: (
        <div>
          <Search
            placeholder="搜索数据资源..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ marginBottom: 12 }}
            size="small"
          />
          {loading ? (
            <div style={{ textAlign: 'center', padding: 20 }}>
              <Spin />
            </div>
          ) : (
            <List
              dataSource={filterNodes(dataResources, searchText)}
              renderItem={(item) => renderNodeItem(item, 'data')}
              locale={{ emptyText: <Empty description="暂无数据资源" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
              style={{ maxHeight: 'calc(100vh - 300px)', overflow: 'auto' }}
            />
          )}
        </div>
      ),
    },
  ]

  return (
    <div style={{ height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column', background: '#fff' }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0' }}>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>组件库</h3>
        <p style={{ margin: '4px 0 0 0', fontSize: 12, color: '#8c8c8c' }}>拖拽节点到画布</p>
      </div>
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <Tabs
          activeKey={activeTab}
          onChange={(key) => {
            setActiveTab(key)
            setSearchText('')
          }}
          items={tabItems}
          style={{ padding: '0 16px' }}
          size="small"
        />
      </div>
    </div>
  )
}

export default NodeLibrary

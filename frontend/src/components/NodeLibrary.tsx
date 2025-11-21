import React, { useState, useEffect } from 'react'
import { Tabs, List, Input, Tag, Spin, Empty } from 'antd'
import { DatabaseOutlined, CodeOutlined, NodeIndexOutlined } from '@ant-design/icons'
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
    // 与 ResourceLibraryPage 中的图标保持同步
    let icon = <NodeIndexOutlined />
    let color = '#52c41a' // 步骤：绿色
    
    if (nodeType === 'implementation') {
      icon = <CodeOutlined />
      color = '#fa541c' // 实现：橙色
    } else if (nodeType === 'data') {
      icon = <DatabaseOutlined />
      color = '#722ed1' // 数据资源：紫色
    }

    return (
      <List.Item
        draggable
        onDragStart={(e) => handleDragStart(e, nodeType, node)}
        style={{
          cursor: 'grab',
          padding: '6px 10px',
          borderRadius: 6,
          marginBottom: 6,
          background: 'transparent',
          border: '1px solid #e5e7eb',
          transition: 'background 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease',
        }}
        onMouseDown={(e) => {
          (e.currentTarget as HTMLElement).style.cursor = 'grabbing'
        }}
        onMouseUp={(e) => {
          (e.currentTarget as HTMLElement).style.cursor = 'grab'
        }}
        onMouseEnter={(e) => {
          const el = e.currentTarget as HTMLElement
          el.style.background = '#f5f7ff'
          el.style.borderColor = '#d0e2ff'
          el.style.boxShadow = '0 2px 6px rgba(15, 23, 42, 0.12)'
        }}
        onMouseLeave={(e) => {
          const el = e.currentTarget as HTMLElement
          el.style.background = 'transparent'
          el.style.borderColor = '#e5e7eb'
          el.style.boxShadow = 'none'
        }}
      >
        <div style={{ width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color }}>{icon}</span>
            <span
              style={{
                fontWeight: 500,
                flex: 1,
                fontSize: 13,
                lineHeight: '18px',
                wordBreak: 'break-all',
              }}
            >
              {node.name}
            </span>
          </div>
          <div style={{ 
            fontSize: 12,
            color: '#8c8c8c',
            marginTop: 4,
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'normal',
            wordBreak: 'break-all',
          }}>
            {node.description || '暂无说明'}
          </div>
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
        <div
          style={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
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
              style={{ flex: 1, minHeight: 0, overflow: 'auto' }}
            />
          )}
        </div>
      ),
    },
    {
      key: 'implementations',
      label: '实现',
      children: (
        <div
          style={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
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
              style={{ flex: 1, minHeight: 0, overflow: 'auto' }}
            />
          )}
        </div>
      ),
    },
    {
      key: 'dataResources',
      label: '数据资源',
      children: (
        <div
          style={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
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
              style={{ flex: 1, minHeight: 0, overflow: 'auto' }}
            />
          )}
        </div>
      ),
    },
  ]

  return (
    <Tabs
      activeKey={activeTab}
      onChange={(key) => {
        setActiveTab(key)
        setSearchText('')
      }}
      items={tabItems}
      size="small"
      style={{ height: '100%' }}
    />
  )
}

export default NodeLibrary

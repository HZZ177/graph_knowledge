/**
 * 文档中心页面
 * 
 * 功能：
 * - 左侧：目录树 + 操作面板
 * - 右侧：文件列表 + 文档预览
 * - 支持文档同步和 LightRAG 索引
 */

import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  Layout,
  Tree,
  Table,
  Button,
  Space,
  Tag,
  Progress,
  message,
  Spin,
  Empty,
  Modal,
  Tabs,
  Card,
  Tooltip,
  Typography,
} from 'antd'
import {
  FolderOutlined,
  FileTextOutlined,
  SyncOutlined,
  CloudUploadOutlined,
  ReloadOutlined,
  EyeOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  LoadingOutlined,
} from '@ant-design/icons'
import type { DataNode } from 'antd/es/tree'
import type { ColumnsType } from 'antd/es/table'

import {
  syncFromHelpCenter,
  getDirectoryTree,
  getDocuments,
  syncDocumentContent,
  createIndexTasks,
  getDocumentContent,
  createDocCenterWS,
} from '../api/docCenter'
import type {
  TreeNode,
  LocalDocument,
  IndexProgressMessage,
} from '../types/docCenter'
import { MemoizedMarkdown } from '../components/chat'

import './DocCenterPage.css'

const { Sider, Content } = Layout
const { Text } = Typography

// ============== 状态标签组件 ==============

const SyncStatusTag: React.FC<{ status: string }> = ({ status }) => {
  const config: Record<string, { color: string; icon: React.ReactNode; text: string }> = {
    pending: { color: 'default', icon: <ClockCircleOutlined />, text: '待同步' },
    syncing: { color: 'processing', icon: <LoadingOutlined />, text: '同步中' },
    synced: { color: 'success', icon: <CheckCircleOutlined />, text: '已同步' },
    failed: { color: 'error', icon: <CloseCircleOutlined />, text: '同步失败' },
  }
  const cfg = config[status] || config.pending
  return <Tag color={cfg.color} icon={cfg.icon}>{cfg.text}</Tag>
}

const IndexStatusTag: React.FC<{ status: string; progress?: number; phase?: string | null }> = ({
  status,
  progress = 0,
  phase,
}) => {
  const config: Record<string, { color: string; icon: React.ReactNode; text: string }> = {
    pending: { color: 'default', icon: <ClockCircleOutlined />, text: '待索引' },
    queued: { color: 'warning', icon: <ClockCircleOutlined />, text: '排队中' },
    indexing: { color: 'processing', icon: <LoadingOutlined />, text: '索引中' },
    indexed: { color: 'success', icon: <CheckCircleOutlined />, text: '已索引' },
    failed: { color: 'error', icon: <CloseCircleOutlined />, text: '索引失败' },
  }
  const cfg = config[status] || config.pending

  if (status === 'indexing') {
    return (
      <Tooltip title={phase || '处理中'}>
        <Tag color={cfg.color} icon={cfg.icon}>
          {cfg.text} {progress}%
        </Tag>
      </Tooltip>
    )
  }

  return <Tag color={cfg.color} icon={cfg.icon}>{cfg.text}</Tag>
}

// ============== 主页面组件 ==============

const DocCenterPage: React.FC = () => {
  // 目录树状态
  const [treeData, setTreeData] = useState<DataNode[]>([])
  const [treeLoading, setTreeLoading] = useState(false)
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null)
  const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([])

  // 文档列表状态
  const [documents, setDocuments] = useState<LocalDocument[]>([])
  const [documentsLoading, setDocumentsLoading] = useState(false)
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [pagination, setPagination] = useState({ current: 1, pageSize: 50, total: 0 })

  // 文档预览状态
  const [previewDoc, setPreviewDoc] = useState<LocalDocument | null>(null)
  const [previewContent, setPreviewContent] = useState<string>('')
  const [previewLoading, setPreviewLoading] = useState(false)

  // 操作状态
  const [syncing, setSyncing] = useState(false)
  const [indexing, setIndexing] = useState(false)

  // WebSocket
  const wsRef = useRef<WebSocket | null>(null)

  // ============== 数据加载 ==============

  // 加载目录树（从本地数据库）
  const loadTree = useCallback(async () => {
    setTreeLoading(true)
    try {
      const tree = await getDirectoryTree()
      const convertToDataNode = (nodes: TreeNode[]): DataNode[] => {
        return nodes.map((node) => ({
          key: node.id,
          title: node.title,
          icon: node.is_folder ? <FolderOutlined /> : <FileTextOutlined />,
          isLeaf: !node.is_folder,
          children: node.children?.length ? convertToDataNode(node.children) : undefined,
        }))
      }
      setTreeData(convertToDataNode(tree))
    } catch (e: any) {
      // 首次可能没有数据，不报错
      console.log('加载目录树:', e.message)
    } finally {
      setTreeLoading(false)
    }
  }, [])

  // 加载文档列表（从本地数据库）
  const loadDocuments = useCallback(async (folderId?: string | null, page = 1) => {
    setDocumentsLoading(true)
    try {
      const result = await getDocuments({
        parent_id: folderId || undefined,
        page,
        page_size: pagination.pageSize,
      })

      setDocuments(result.items as LocalDocument[])
      setPagination((prev) => ({
        ...prev,
        current: page,
        total: result.total,
      }))
    } catch (e: any) {
      console.log('加载文档列表:', e.message)
    } finally {
      setDocumentsLoading(false)
    }
  }, [pagination.pageSize])

  // ============== 操作处理 ==============

  // 从帮助中心同步结构
  const handleSyncStructure = async () => {
    setSyncing(true)
    try {
      const result = await syncFromHelpCenter()
      message.success(`同步完成: ${result.folders_synced} 目录, ${result.documents_synced} 文档`)
      loadTree()
      loadDocuments(selectedFolderId)
    } catch (e: any) {
      message.error(`同步失败: ${e.message}`)
    } finally {
      setSyncing(false)
    }
  }

  // 同步单个文档内容
  const handleSyncContent = async (doc: LocalDocument) => {
    try {
      message.loading({ content: `正在同步: ${doc.title}`, key: doc.id })
      await syncDocumentContent(doc.id)
      message.success({ content: `同步成功: ${doc.title}`, key: doc.id })
      loadDocuments(selectedFolderId)
    } catch (e: any) {
      message.error({ content: `同步失败: ${e.message}`, key: doc.id })
    }
  }

  // 索引选中文档
  const handleIndex = async () => {
    const syncedDocs = documents.filter(
      (d) => selectedRowKeys.includes(d.id) && d.sync_status === 'synced'
    )

    if (syncedDocs.length === 0) {
      message.warning('请先选择已同步的文档进行索引')
      return
    }

    const docIds = syncedDocs.map((d) => d.id)

    setIndexing(true)
    try {
      const result = await createIndexTasks(docIds)
      const successCount = result.tasks.filter((t) => t.success).length
      message.success(`已创建 ${successCount} 个索引任务`)
      setSelectedRowKeys([])
      loadDocuments(selectedFolderId)
    } catch (e: any) {
      message.error(`创建索引任务失败: ${e.message}`)
    } finally {
      setIndexing(false)
    }
  }

  // 查看文档
  const handlePreview = async (doc: LocalDocument) => {
    if (doc.sync_status !== 'synced') {
      message.warning('请先同步文档内容')
      return
    }

    setPreviewLoading(true)
    try {
      const content = await getDocumentContent(doc.id)
      setPreviewDoc(doc)
      setPreviewContent(content)
    } catch (e: any) {
      message.error(`加载文档内容失败: ${e.message}`)
    } finally {
      setPreviewLoading(false)
    }
  }

  // ============== WebSocket ==============

  useEffect(() => {
    const ws = createDocCenterWS({
      onProgress: (msg: IndexProgressMessage) => {
        // 更新文档列表中的进度
        setDocuments((prev) =>
          prev.map((d) =>
            d.id === msg.document_id
              ? {
                  ...d,
                  index_status: 'indexing' as const,
                  index_progress: msg.overall_progress,
                  index_phase: msg.phase_name,
                }
              : d
          )
        )
      },
      onQueueStatus: (msg) => {
        console.log('[DocCenter] Queue status:', msg)
      },
      onError: (err) => {
        console.error('[DocCenter] WS error:', err)
      },
    })

    wsRef.current = ws

    return () => {
      ws.close()
    }
  }, [])

  // ============== 初始化 ==============

  useEffect(() => {
    loadTree()
    loadDocuments(null)
  }, [loadTree, loadDocuments])

  // ============== 表格列定义 ==============

  const columns: ColumnsType<LocalDocument> = [
    {
      title: '文档名称',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      render: (title) => (
        <Space>
          <FileTextOutlined />
          <Text ellipsis={{ tooltip: title }} style={{ maxWidth: 200 }}>
            {title}
          </Text>
        </Space>
      ),
    },
    {
      title: '同步状态',
      dataIndex: 'sync_status',
      key: 'sync_status',
      width: 100,
      render: (status) => <SyncStatusTag status={status} />,
    },
    {
      title: '索引状态',
      dataIndex: 'index_status',
      key: 'index_status',
      width: 120,
      render: (status, record) => (
        <IndexStatusTag
          status={status}
          progress={record.index_progress}
          phase={record.index_phase}
        />
      ),
    },
    {
      title: '进度',
      dataIndex: 'index_progress',
      key: 'index_progress',
      width: 100,
      render: (progress, record) =>
        record.index_status === 'indexing' ? (
          <Progress percent={progress} size="small" />
        ) : record.index_status === 'indexed' ? (
          <Progress percent={100} size="small" status="success" />
        ) : null,
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_, record) => (
        <Space size="small">
          {record.sync_status !== 'synced' && (
            <Button
              type="link"
              size="small"
              icon={<SyncOutlined />}
              onClick={() => handleSyncContent(record)}
            >
              同步
            </Button>
          )}
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            disabled={record.sync_status !== 'synced'}
            onClick={() => handlePreview(record)}
          >
            查看
          </Button>
        </Space>
      ),
    },
  ]

  // ============== 渲染 ==============

  return (
    <Layout className="doc-center-page">
      {/* 左侧：目录树 */}
      <Sider width={280} className="doc-center-sider">
        <div className="sider-header">
          <h3>文档中心</h3>
          <Button
            type="text"
            icon={<ReloadOutlined />}
            onClick={loadTree}
            loading={treeLoading}
          />
        </div>

        <div className="tree-container">
          <Spin spinning={treeLoading}>
            {treeData.length > 0 ? (
              <Tree
                showIcon
                treeData={treeData}
                expandedKeys={expandedKeys}
                onExpand={(keys) => setExpandedKeys(keys)}
                onSelect={(keys) => {
                  const key = keys[0] as string
                  setSelectedFolderId(key || null)
                  loadDocuments(key || null)
                }}
              />
            ) : (
              <Empty description="暂无数据" />
            )}
          </Spin>
        </div>

        <div className="action-panel">
          <Button
            type="primary"
            icon={<SyncOutlined />}
            block
            loading={syncing}
            onClick={handleSyncStructure}
          >
            从帮助中心同步
          </Button>
          <Button
            icon={<CloudUploadOutlined />}
            block
            style={{ marginTop: 8 }}
            loading={indexing}
            disabled={selectedRowKeys.length === 0}
            onClick={handleIndex}
          >
            索引选中 ({selectedRowKeys.length})
          </Button>
        </div>
      </Sider>

      {/* 右侧：文档列表 + 预览 */}
      <Content className="doc-center-content">
        {/* 文档列表 */}
        <Card
          title="文档列表"
          size="small"
          className="document-list-card"
          extra={
            <Button
              type="text"
              icon={<ReloadOutlined />}
              onClick={() => loadDocuments(selectedFolderId)}
            >
              刷新
            </Button>
          }
        >
          <Table
            rowKey="id"
            columns={columns}
            dataSource={documents}
            loading={documentsLoading}
            size="small"
            rowSelection={{
              selectedRowKeys,
              onChange: (keys) => setSelectedRowKeys(keys),
            }}
            pagination={{
              ...pagination,
              showSizeChanger: true,
              showTotal: (total) => `共 ${total} 条`,
              onChange: (page) => loadDocuments(selectedFolderId, page),
            }}
          />
        </Card>

        {/* 文档预览 */}
        {previewDoc && (
          <Card
            title={`预览: ${previewDoc.title}`}
            size="small"
            className="document-preview-card"
            extra={
              <Button type="text" onClick={() => setPreviewDoc(null)}>
                关闭
              </Button>
            }
          >
            <Spin spinning={previewLoading}>
              <div className="markdown-preview">
                <MemoizedMarkdown source={previewContent} />
              </div>
            </Spin>
          </Card>
        )}
      </Content>
    </Layout>
  )
}

export default DocCenterPage

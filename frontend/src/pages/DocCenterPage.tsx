/**
 * 文档中心页面
 * 
 * 两种模式：
 * - 阅读模式：左侧文件树 + 右侧文档阅读器
 * - 管理模式：左侧文件树 + 右侧文件列表（同步、索引等操作）
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
  Card,
  Tooltip,
  Typography,
  Segmented,
  Pagination,
  Input,
  Select,
} from 'antd'
import {
  FolderOutlined,
  FileTextOutlined,
  SyncOutlined,
  CloudUploadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  LoadingOutlined,
  ReadOutlined,
  SettingOutlined,
  SearchOutlined,
  EyeOutlined,
  StopOutlined,
} from '@ant-design/icons'
import type { DataNode } from 'antd/es/tree'
import type { ColumnsType } from 'antd/es/table'

import {
  syncFromHelpCenter,
  getDirectoryTree,
  getDocuments,
  syncDocumentContent,
  createIndexTasks,
  cancelIndexTask,
  getDocumentContent,
  createDocCenterWS,
  getIndexQueueStatus,
} from '../api/docCenter'
import type {
  TreeNode,
  LocalDocument,
  IndexProgressMessage,
  SyncProgressMessage,
} from '../types/docCenter'
import { MemoizedMarkdown } from '../components/chat'

import './DocCenterPage.css'

const { Sider, Content } = Layout
const { Text } = Typography

type ViewMode = 'read' | 'manage'

// ============== 状态标签组件 ==============

const SyncStatusTag: React.FC<{ status: string; progress?: { current: number; total: number } }> = ({ status, progress }) => {
  const config: Record<string, { icon: React.ReactNode; text: string }> = {
    pending: { icon: <ClockCircleOutlined />, text: '待同步' },
    syncing: { icon: <LoadingOutlined />, text: '同步中' },
    synced: { icon: <CheckCircleOutlined style={{ color: '#52c41a' }} />, text: '已同步' },
    failed: { icon: <CloseCircleOutlined />, text: '同步失败' },
  }
  const cfg = config[status] || config.pending

  // 同步中显示图片处理进度
  if (status === 'syncing' && progress && progress.total > 0) {
    return (
      <Tooltip title={`处理图片 ${progress.current}/${progress.total}`}>
        <Tag className={`doc-center-status-tag doc-center-status-tag--${status}`} icon={cfg.icon}>
          图片 {progress.current}/{progress.total}
        </Tag>
      </Tooltip>
    )
  }

  return (
    <Tag className={`doc-center-status-tag doc-center-status-tag--${status}`} icon={cfg.icon}>
      {cfg.text}
    </Tag>
  )
}

// 两阶段进度显示组件（提取 + 图谱构建）
interface TwoPhaseProgressProps {
  status: string
  extractionProgress: number
  graphBuildTotal: number
  graphBuildDone: number
  graphBuildProgress: number
  entitiesTotal: number
  relationsTotal: number
}

const TwoPhaseProgress: React.FC<TwoPhaseProgressProps> = ({
  status,
  extractionProgress,
  graphBuildTotal,
  graphBuildDone,
  graphBuildProgress,
  entitiesTotal,
  relationsTotal,
}) => {
  if (status !== 'indexing') return null

  return (
    <div className="two-phase-progress">
      <div className="phase-item">
        <span className="phase-label">提取</span>
        <Progress percent={extractionProgress} size="small" strokeColor="#1890ff" />
      </div>
      <div className="phase-item">
        <div className="phase-text">
          <span className="phase-label">图谱 {graphBuildTotal > 0 ? `${graphBuildDone}/${graphBuildTotal}` : ''}</span>
          {graphBuildTotal > 0 && (
            <span className="phase-detail">({entitiesTotal}实体+{relationsTotal}关系)</span>
          )}
        </div>
        <Progress percent={graphBuildProgress} size="small" strokeColor="#52c41a" />
      </div>
    </div>
  )
}

const IndexStatusTag: React.FC<{ status: string }> = ({ status }) => {
  const config: Record<string, { icon: React.ReactNode; text: string }> = {
    pending: { icon: <ClockCircleOutlined />, text: '待索引' },
    queued: { icon: <ClockCircleOutlined style={{ color: '#faad14' }} />, text: '排队中' },
    indexing: { icon: <LoadingOutlined />, text: '索引中' },
    indexed: { icon: <CheckCircleOutlined style={{ color: '#52c41a' }} />, text: '已索引' },
    failed: { icon: <CloseCircleOutlined style={{ color: '#ff4d4f' }} />, text: '索引失败' },
  }
  const cfg = config[status] || config.pending

  return (
    <Tag className={`doc-center-status-tag doc-center-status-tag--${status}`} icon={cfg.icon}>
      {cfg.text}
    </Tag>
  )
}

// ============== 主页面组件 ==============

const DocCenterPage: React.FC = () => {
  // 模式状态
  const [viewMode, setViewMode] = useState<ViewMode>('read')

  // 目录树状态
  const [treeData, setTreeData] = useState<DataNode[]>([])
  const [treeLoading, setTreeLoading] = useState(false)
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([])
  
  // 搜索状态
  const [searchValue, setSearchValue] = useState('')
  const [autoExpandParent, setAutoExpandParent] = useState(true)

  // 阅读模式：当前文档
  const [currentDoc, setCurrentDoc] = useState<LocalDocument | null>(null)
  const [currentContent, setCurrentContent] = useState<string>('')
  const [contentLoading, setContentLoading] = useState(false)

  // 管理模式：文档列表状态
  const [documents, setDocuments] = useState<LocalDocument[]>([])
  const [documentsLoading, setDocumentsLoading] = useState(false)
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [pagination, setPagination] = useState({ current: 1, pageSize: 50, total: 0 })

  // 筛选状态
  const [filterKeyword, setFilterKeyword] = useState('')
  const [filterSyncStatus, setFilterSyncStatus] = useState<string[]>([])
  const [filterIndexStatus, setFilterIndexStatus] = useState<string[]>([])

  // 操作状态
  const [syncing, setSyncing] = useState(false)
  const [indexing, setIndexing] = useState(false)

  // 同步进度状态 { docId: { current, total } }
  const [syncProgress, setSyncProgress] = useState<Record<string, { current: number; total: number }>>({})

  // WebSocket
  const wsRef = useRef<WebSocket | null>(null)

  // 保存树节点信息用于查找文档
  const treeNodesRef = useRef<Map<string, TreeNode>>(new Map())
  const rawTreeRef = useRef<TreeNode[]>([])
  const didInitExpandRef = useRef(false)

  // ============== 搜索功能 ==============

  // 获取节点的所有父节点 key
  const getParentKeys = useCallback((key: string, tree: TreeNode[]): string[] => {
    const parentKeys: string[] = []
    const findParent = (nodes: TreeNode[], targetKey: string, path: string[]): boolean => {
      for (const node of nodes) {
        if (node.id === targetKey) {
          parentKeys.push(...path)
          return true
        }
        if (node.children?.length) {
          if (findParent(node.children, targetKey, [...path, node.id])) {
            return true
          }
        }
      }
      return false
    }
    findParent(tree, key, [])
    return parentKeys
  }, [])

  // 搜索处理
  const handleSearch = useCallback((value: string) => {
    setSearchValue(value)
    if (!value) {
      setAutoExpandParent(false)
      return
    }

    // 找到所有匹配节点的父节点
    const allParentKeys: Set<string> = new Set()
    const rawTree: TreeNode[] = []
    
    // 从 treeNodesRef 重建树结构
    treeNodesRef.current.forEach((node) => {
      if (!node.parent_id || node.parent_id === '0') {
        rawTree.push(node)
      }
    })

    treeNodesRef.current.forEach((node) => {
      if (node.title.toLowerCase().includes(value.toLowerCase())) {
        const parents = getParentKeys(node.id, rawTree)
        parents.forEach((k) => allParentKeys.add(k))
      }
    })

    setExpandedKeys(Array.from(allParentKeys))
    setAutoExpandParent(true)
  }, [getParentKeys])

  // ============== 数据加载 ==============

  // 将树节点转换为 Ant Design Tree 的 DataNode 格式
  const convertToDataNode = useCallback((nodes: TreeNode[], search: string): DataNode[] => {
    return nodes.map((node) => {
      const index = node.title.toLowerCase().indexOf(search.toLowerCase())
      const beforeStr = node.title.substring(0, index)
      const matchStr = node.title.substring(index, index + search.length)
      const afterStr = node.title.substring(index + search.length)
      
      const titleNode = search && index > -1 ? (
        <span>
          {beforeStr}
          <span className="tree-search-highlight">{matchStr}</span>
          {afterStr}
        </span>
      ) : (
        <span>{node.title}</span>
      )
      
      // 文件图标改为圆点，根据同步状态显示不同颜色
      let nodeIcon: React.ReactNode
      if (node.is_folder) {
        nodeIcon = <FolderOutlined />
      } else {
        // 根据 sync_status 决定圆点颜色（从 treeNodesRef 获取最新状态）
        const latestNode = treeNodesRef.current.get(node.id)
        const syncStatus = latestNode?.sync_status || node.sync_status || 'pending'
        let dotClass = 'doc-tree-dot'
        if (syncStatus === 'synced') {
          dotClass += ' doc-tree-dot--synced'
        } else if (syncStatus === 'syncing') {
          dotClass += ' doc-tree-dot--syncing'
        } else {
          dotClass += ' doc-tree-dot--pending'
        }
        nodeIcon = <span className={dotClass} />
      }
      
      return {
        key: node.id,
        title: titleNode,
        icon: nodeIcon,
        isLeaf: !node.is_folder,
        children: node.children?.length ? convertToDataNode(node.children, search) : undefined,
      }
    })
  }, [])

  // 刷新树数据（不重新请求，只根据当前状态重新渲染）
  const refreshTreeData = useCallback((search: string = searchValue) => {
    if (rawTreeRef.current.length > 0) {
      setTreeData(convertToDataNode(rawTreeRef.current, search))
    }
  }, [convertToDataNode, searchValue])

  // 更新树节点的同步状态（使用 ref 以便在 WebSocket 回调中调用）
  const refreshTreeDataRef = useRef(refreshTreeData)
  useEffect(() => {
    refreshTreeDataRef.current = refreshTreeData
  }, [refreshTreeData])

  const updateTreeNodeSyncStatus = useCallback((documentId: string, syncStatus: string) => {
    // 根据 document_id（本地ID）找到对应的树节点并更新
    treeNodesRef.current.forEach((node) => {
      if (node.local_id === documentId) {
        node.sync_status = syncStatus
      }
    })
    // 刷新树数据
    refreshTreeDataRef.current()
  }, [])

  // 保存 updateTreeNodeSyncStatus 的引用，以便在 WebSocket 回调中使用
  const updateTreeNodeSyncStatusRef = useRef(updateTreeNodeSyncStatus)
  useEffect(() => {
    updateTreeNodeSyncStatusRef.current = updateTreeNodeSyncStatus
  }, [updateTreeNodeSyncStatus])

  // 加载目录树（从本地数据库）
  const loadTree = useCallback(async () => {
    setTreeLoading(true)
    try {
      const tree = await getDirectoryTree()
      // 保存原始树结构
      rawTreeRef.current = tree
      // 保存节点信息到ref
      const saveNodes = (nodes: TreeNode[]) => {
        nodes.forEach((node) => {
          treeNodesRef.current.set(node.id, node)
          if (node.children) saveNodes(node.children)
        })
      }
      treeNodesRef.current.clear()
      saveNodes(tree)

      // 默认展开两层（仅首次加载生效）
      if (!didInitExpandRef.current) {
        const keys: React.Key[] = []
        const collectFolderKeys = (nodes: TreeNode[], depth: number) => {
          nodes.forEach((node) => {
            if (node.is_folder && depth < 2) {
              keys.push(node.id)
            }
            if (node.children && node.children.length > 0) {
              collectFolderKeys(node.children, depth + 1)
            }
          })
        }
        collectFolderKeys(tree, 0)
        setExpandedKeys(keys)
        didInitExpandRef.current = true
      }

      setTreeData(convertToDataNode(tree, searchValue))
    } catch (e: any) {
      console.log('加载目录树:', e.message)
    } finally {
      setTreeLoading(false)
    }
  }, [searchValue, convertToDataNode])

  // 加载文档列表（管理模式）
  const loadDocuments = useCallback(async (
    page = 1,
    keyword?: string,
    syncStatus?: string[],
    indexStatus?: string[]
  ) => {
    setDocumentsLoading(true)
    try {
      const result = await getDocuments({
        page,
        page_size: pagination.pageSize,
        keyword: keyword || undefined,
        sync_status: syncStatus && syncStatus.length > 0 ? syncStatus : undefined,
        index_status: indexStatus && indexStatus.length > 0 ? indexStatus : undefined,
      })
      setDocuments(result.items as LocalDocument[])
      setPagination((prev) => ({ ...prev, current: page, total: result.total }))
    } catch (e: any) {
      console.log('加载文档列表:', e.message)
    } finally {
      setDocumentsLoading(false)
    }
  }, [pagination.pageSize])

  // 刷新正在索引的文档进度（从队列状态获取）
  const refreshIndexingProgress = useCallback(async () => {
    try {
      const status = await getIndexQueueStatus()
      if (status.current_task && status.is_running) {
        const { document_id, phase, progress } = status.current_task
        setDocuments((prev) =>
          prev.map((d) =>
            d.id === document_id
              ? {
                  ...d,
                  index_status: 'indexing' as const,
                  extraction_progress: progress,
                }
              : d
          )
        )
      }
    } catch (e) {
      // 静默失败，不影响主流程
    }
  }, [])

  // 查询按钮处理
  const handleFilter = useCallback(async () => {
    await loadDocuments(1, filterKeyword, filterSyncStatus.length > 0 ? filterSyncStatus : undefined, filterIndexStatus.length > 0 ? filterIndexStatus : undefined)
    await refreshIndexingProgress()
  }, [loadDocuments, filterKeyword, filterSyncStatus, filterIndexStatus, refreshIndexingProgress])

  // 重置按钮处理
  const handleResetFilter = useCallback(async () => {
    setFilterKeyword('')
    setFilterSyncStatus([])
    setFilterIndexStatus([])
    await loadDocuments(1, '', undefined, undefined)
    await refreshIndexingProgress()
  }, [loadDocuments, refreshIndexingProgress])

  // 加载单个文档内容（阅读模式）
  const loadDocumentContent = useCallback(async (docId: string) => {
    setContentLoading(true)
    try {
      const content = await getDocumentContent(docId)
      setCurrentContent(content || '')
    } catch (e: any) {
      message.error(`加载文档失败: ${e.message}`)
      setCurrentContent('')
    } finally {
      setContentLoading(false)
    }
  }, [])

  // ============== 操作处理 ==============

  // 从帮助中心同步结构
  const handleSyncStructure = async () => {
    setSyncing(true)
    try {
      const result = await syncFromHelpCenter()
      message.success(`同步完成: ${result.folders_synced} 目录, ${result.documents_synced} 文档`)
      loadTree()
      loadDocuments()
    } catch (e: any) {
      message.error(`同步失败: ${e.message}`)
    } finally {
      setSyncing(false)
    }
  }

  // 同步单个文档内容（进度由 WebSocket 推送到表格状态列显示）
  const handleSyncContent = async (doc: LocalDocument) => {
    // 立即更新状态为 syncing
    setDocuments((prev) =>
      prev.map((d) => (d.id === doc.id ? { ...d, sync_status: 'syncing' as const } : d))
    )
    updateTreeNodeSyncStatus(doc.id, 'syncing')
    
    try {
      await syncDocumentContent(doc.id)
      // 同步完成后刷新列表
      loadDocuments()
    } catch (e: any) {
      console.error(`同步失败: ${doc.title}`, e)
      // 失败时也刷新列表获取最新状态
      loadDocuments()
    }
  }

  // 重新同步（带确认弹窗，确认后弹窗立即消失，进度由表格状态列显示）
  const handleResync = (doc: LocalDocument) => {
    Modal.confirm({
      centered: true,
      title: '重新同步确认',
      content: `重新同步会覆盖「${doc.title}」的文档内容，是否执行？`,
      okText: '确认同步',
      cancelText: '取消',
      onOk: () => {
        // 不返回 Promise，让弹窗立即关闭
        handleSyncContent(doc)
      },
    })
  }

  // 查看文档（跳转阅读模式，自动选中并加载内容）
  const handleViewDocument = async (doc: LocalDocument) => {
    // 切换到阅读模式
    setViewMode('read')
    // 设置当前文档
    setCurrentDoc(doc)
    // 选中左侧树节点（使用 source_doc_id）
    setSelectedKey(doc.source_doc_id)
    // 展开父节点路径
    const node = treeNodesRef.current.get(doc.source_doc_id)
    if (node?.parent_id && node.parent_id !== '0') {
      const parentId = node.parent_id
      setExpandedKeys((prev) => {
        const newKeys = new Set(prev)
        newKeys.add(parentId)
        return Array.from(newKeys)
      })
    }
    // 加载文档内容
    await loadDocumentContent(doc.id)
  }

  // 批量同步选中文档（进度由 WebSocket 推送到表格状态列显示）
  const [batchSyncing, setBatchSyncing] = useState(false)
  const handleBatchSync = async () => {
    const selectedDocs = documents.filter((d) => selectedRowKeys.includes(d.id))
    if (selectedDocs.length === 0) {
      message.warning('请先选择文档')
      return
    }
    setBatchSyncing(true)
    
    // 立即更新所有选中文档的状态为 syncing，让用户看到状态变化
    const selectedIds = selectedDocs.map((d) => d.id)
    setDocuments((prev) =>
      prev.map((d) =>
        selectedIds.includes(d.id) ? { ...d, sync_status: 'syncing' as const } : d
      )
    )
    // 清除多选状态
    setSelectedRowKeys([])
    
    try {
      // 并行发起所有同步请求，每个文档的进度由 WebSocket 实时推送
      await Promise.all(
        selectedDocs.map((doc) =>
          syncDocumentContent(doc.id).catch((e) => {
            console.error(`同步失败: ${doc.title}`, e)
          })
        )
      )
      // 批量同步完成后刷新列表获取最新状态
      loadDocuments()
    } finally {
      setBatchSyncing(false)
    }
  }

  // 索引文档（支持批量和单个）
  const handleIndex = async (docIds?: string[]) => {
    let idsToIndex: string[]
    if (docIds && docIds.length > 0) {
      // 单个文档索引
      idsToIndex = docIds
    } else {
      // 批量索引：从选中的行中筛选已同步的
      const syncedDocs = documents.filter(
        (d) => selectedRowKeys.includes(d.id) && d.sync_status === 'synced'
      )
      if (syncedDocs.length === 0) {
        message.warning('请先选择已同步的文档进行索引')
        return
      }
      idsToIndex = syncedDocs.map((d) => d.id)
    }
    setIndexing(true)
    
    // 立即更新状态为 queued，让用户看到状态变化
    setDocuments((prev) =>
      prev.map((d) =>
        idsToIndex.includes(d.id)
          ? { ...d, index_status: 'queued' as const, extraction_progress: 0, graph_build_progress: 0 }
          : d
      )
    )
    
    try {
      const result = await createIndexTasks(idsToIndex)
      const successCount = result.tasks.filter((t) => t.success).length
      message.success(`已创建 ${successCount} 个索引任务`)
      if (!docIds) setSelectedRowKeys([])
      // 不立即刷新列表，避免覆盖 WS 推送的状态更新
      // WS 会持续更新进度，任务完成后状态会自动更新
    } catch (e: any) {
      message.error(`创建索引任务失败: ${e.message}`)
      // 失败时恢复状态
      loadDocuments()
    } finally {
      setIndexing(false)
    }
  }

  // 取消索引任务（排队中）
  const handleCancelIndex = async (docId: string) => {
    try {
      await cancelIndexTask(docId)
      message.success('已取消索引任务')
      loadDocuments()
    } catch (e: any) {
      message.error(`取消失败: ${e.message}`)
    }
  }

  // 停止索引任务（正在运行）
  const handleStopIndex = async (docId: string) => {
    try {
      const res = await fetch(`/api/v1/doc-center/index/stop/${docId}`, { method: 'POST' })
      const data = await res.json()
      if (data.code !== 0) throw new Error(data.message)
      message.success('已请求停止索引')
    } catch (e: any) {
      message.error(`停止失败: ${e.message}`)
    }
  }

  // 树节点选择处理
  const handleTreeSelect = async (keys: React.Key[], info: any) => {
    // 使用 info.node.key 获取被点击的节点，避免取消选中时 keys 为空
    const key = (info.node?.key ?? keys[0]) as string
    if (!key) return

    const node = treeNodesRef.current.get(key)

    // 文件夹：展开/收起（两种模式都支持）
    if (node?.is_folder) {
      setExpandedKeys((prev) =>
        prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
      )
      return
    }

    // 文件：阅读模式下显示内容
    if (viewMode === 'read') {
      if (node?.local_id) {
        setSelectedKey(key)
        const docForRead = {
          id: node.local_id,
          source_doc_id: node.id,
          title: node.title,
          path: null,
          sync_status: (node.sync_status as any) || 'pending',
          synced_at: null,
          index_status: (node.index_status as any) || 'pending',
          extraction_progress: 0,
          graph_build_total: 0,
          graph_build_done: 0,
          graph_build_progress: 0,
          entities_total: 0,
          relations_total: 0,
          created_at: null,
        } as LocalDocument
        setCurrentDoc(docForRead)
        await loadDocumentContent(node.local_id)
      } else {
        setCurrentDoc(null)
        setCurrentContent('')
        message.info('暂时无法读取该节点')
      }
    }
  }

  // ============== WebSocket ==============

  useEffect(() => {
    const ws = createDocCenterWS({
      onProgress: (msg: IndexProgressMessage) => {
        // 更新文档列表中的两阶段进度
        setDocuments((prev) =>
          prev.map((d) =>
            d.id === msg.document_id
              ? {
                  ...d,
                  index_status:
                    msg.current_phase === 'completed'
                      ? ('indexed' as const)
                      : msg.current_phase === 'failed'
                        ? ('failed' as const)
                        : ('indexing' as const),
                  extraction_progress: msg.extraction_progress,
                  graph_build_total: msg.graph_build_total,
                  graph_build_done: msg.graph_build_done,
                  graph_build_progress: msg.graph_build_progress,
                  entities_total: msg.entities_total,
                  relations_total: msg.relations_total,
                }
              : d
          )
        )
      },
      onSyncProgress: (msg) => {
        if (msg.phase === 'image_processing') {
          // 更新同步进度
          setSyncProgress((prev) => ({
            ...prev,
            [msg.document_id]: { current: msg.current, total: msg.total },
          }))
          // 更新文档状态为 syncing
          setDocuments((prev) =>
            prev.map((d) =>
              d.id === msg.document_id
                ? { ...d, sync_status: 'syncing' as const }
                : d
            )
          )
          // 更新树节点状态
          updateTreeNodeSyncStatusRef.current(msg.document_id, 'syncing')
        } else if (msg.phase === 'completed') {
          // 同步完成，清除进度并更新状态
          setSyncProgress((prev) => {
            const newProgress = { ...prev }
            delete newProgress[msg.document_id]
            return newProgress
          })
          setDocuments((prev) =>
            prev.map((d) =>
              d.id === msg.document_id
                ? { ...d, sync_status: 'synced' as const }
                : d
            )
          )
          // 更新树节点状态
          updateTreeNodeSyncStatusRef.current(msg.document_id, 'synced')
        } else if (msg.phase === 'failed') {
          // 同步失败
          setSyncProgress((prev) => {
            const newProgress = { ...prev }
            delete newProgress[msg.document_id]
            return newProgress
          })
          setDocuments((prev) =>
            prev.map((d) =>
              d.id === msg.document_id
                ? { ...d, sync_status: 'failed' as const }
                : d
            )
          )
          // 更新树节点状态
          updateTreeNodeSyncStatusRef.current(msg.document_id, 'failed')
        }
      },
      onQueueStatus: (msg) => {
        void msg
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
    loadDocuments()
  }, [loadTree, loadDocuments])

  // ============== 表格列定义（管理模式）==============

  const columns: ColumnsType<LocalDocument> = [
    {
      title: '文档名称',
      dataIndex: 'title',
      key: 'title',
      width: 200,
      ellipsis: true,
      render: (title) => (
        <Space style={{ maxWidth: '100%' }}>
          <FileTextOutlined style={{ flexShrink: 0 }} />
          <Text ellipsis={{ tooltip: title }} style={{ flex: 1, minWidth: 0 }}>
            {title}
          </Text>
        </Space>
      ),
    },
    {
      title: '同步状态',
      dataIndex: 'sync_status',
      key: 'sync_status',
      width: 120,
      render: (status, record) => (
        <SyncStatusTag status={status} progress={syncProgress[record.id]} />
      ),
    },
    {
      title: '索引状态',
      dataIndex: 'index_status',
      key: 'index_status',
      width: 100,
      render: (status) => <IndexStatusTag status={status} />,
    },
    {
      title: '索引进度',
      key: 'index_progress',
      width: 200,
      render: (_, record) => (
        <TwoPhaseProgress
          status={record.index_status}
          extractionProgress={record.extraction_progress}
          graphBuildTotal={record.graph_build_total || 0}
          graphBuildDone={record.graph_build_done || 0}
          graphBuildProgress={record.graph_build_progress || 0}
          entitiesTotal={record.entities_total}
          relationsTotal={record.relations_total}
        />
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 280,
      render: (_, record) => (
        <Space size="small">
          <Button
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewDocument(record)}
          >
            查看
          </Button>
          {record.sync_status !== 'synced' ? (
            <Button
              size="small"
              icon={<SyncOutlined />}
              onClick={() => handleSyncContent(record)}
            >
              同步
            </Button>
          ) : (
            <Button
              size="small"
              icon={<SyncOutlined />}
              onClick={() => handleResync(record)}
            >
              重新同步
            </Button>
          )}
          {record.index_status === 'queued' ? (
            <Button
              size="small"
              danger
              onClick={() => handleCancelIndex(record.id)}
            >
              取消索引
            </Button>
          ) : record.index_status === 'indexing' ? (
            <Button
              size="small"
              danger
              icon={<StopOutlined />}
              onClick={() => handleStopIndex(record.id)}
            >
              停止
            </Button>
          ) : (
            <Button
              size="small"
              icon={<CloudUploadOutlined />}
              disabled={record.sync_status !== 'synced'}
              onClick={() => handleIndex([record.id])}
            >
              索引
            </Button>
          )}
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
          <Space>
            <Segmented
              size="small"
              value={viewMode}
              onChange={(v) => setViewMode(v as ViewMode)}
              options={[
                { value: 'read', icon: <ReadOutlined />, label: '阅读' },
                { value: 'manage', icon: <SettingOutlined />, label: '管理' },
              ]}
            />
          </Space>
        </div>

        {/* 搜索框 */}
        <div className="tree-search">
          <Input
            placeholder="搜索文档..."
            prefix={<SearchOutlined style={{ color: '#999' }} />}
            allowClear
            value={searchValue}
            onChange={(e) => handleSearch(e.target.value)}
          />
        </div>

        <div className="tree-container">
          <Spin spinning={treeLoading}>
            {treeData.length > 0 ? (
              <Tree
                showIcon
                blockNode
                selectedKeys={selectedKey ? [selectedKey] : []}
                treeData={treeData}
                expandedKeys={expandedKeys}
                autoExpandParent={autoExpandParent}
                onExpand={(keys) => {
                  setExpandedKeys(keys)
                  setAutoExpandParent(false)
                }}
                onSelect={handleTreeSelect}
              />
            ) : (
              <Empty description="请先同步文档" />
            )}
          </Spin>
        </div>

        {/* 管理模式下显示操作按钮 */}
        {viewMode === 'manage' && (
          <div className="action-panel">
            <Button
              type="primary"
              icon={<SyncOutlined />}
              block
              loading={syncing}
              onClick={handleSyncStructure}
            >
              从帮助中心同步结构
            </Button>
          </div>
        )}
      </Sider>

      {/* 右侧内容区 */}
      <Content className="doc-center-content">
        {viewMode === 'read' ? (
          /* 阅读模式：文档阅读器 */
          <Card
            bordered={false}
            title={
              <div className="doc-center-card-title">
                <FileTextOutlined />
                <span>{currentDoc ? currentDoc.title : '请选择文档'}</span>
              </div>
            }
            size="small"
            className="doc-center-card document-reader-card"
          >
            <Spin spinning={contentLoading}>
              {currentContent ? (
                <div className="markdown-body doc-center-markdown">
                  <MemoizedMarkdown source={currentContent} />
                </div>
              ) : (
                <div className="doc-reader-empty">
                  {currentDoc ? (
                    <Empty description="暂无内容，请切换管理模式同步文档" />
                  ) : (
                    <Empty description="点击左侧文件树中的文档查看内容" />
                  )}
                </div>
              )}
            </Spin>
          </Card>
        ) : (
          /* 管理模式：文档列表 */
          <Card
            bordered={false}
            title={
              <div className="doc-center-card-title">
                <SettingOutlined />
                <span>文档列表</span>
              </div>
            }
            size="small"
            className="doc-center-card document-list-card"
          >
            {/* 筛选区域 */}
            <div className="document-filter-bar">
              <div className="filter-bar-left">
                <Space size={12} wrap>
                  <Input
                    placeholder="搜索文档标题"
                    value={filterKeyword}
                    onChange={(e) => setFilterKeyword(e.target.value)}
                    onPressEnter={handleFilter}
                    style={{ width: 180 }}
                    allowClear
                  />
                  <Select
                    mode="multiple"
                    placeholder="同步状态"
                    value={filterSyncStatus}
                    onChange={(v) => setFilterSyncStatus(v)}
                    style={{ minWidth: 200 }}
                    allowClear
                    maxTagCount={2}
                    options={[
                      { value: 'pending', label: '待同步' },
                      { value: 'syncing', label: '同步中' },
                      { value: 'synced', label: '已同步' },
                      { value: 'failed', label: '同步失败' },
                    ]}
                  />
                  <Select
                    mode="multiple"
                    placeholder="索引状态"
                    value={filterIndexStatus}
                    onChange={(v) => setFilterIndexStatus(v)}
                    style={{ minWidth: 200 }}
                    allowClear
                    maxTagCount={2}
                    options={[
                      { value: 'pending', label: '待索引' },
                      { value: 'queued', label: '排队中' },
                      { value: 'indexing', label: '索引中' },
                      { value: 'indexed', label: '已索引' },
                      { value: 'failed', label: '索引失败' },
                    ]}
                  />
                  <Button type="primary" onClick={handleFilter}>
                    查询
                  </Button>
                  <Button onClick={handleResetFilter}>
                    重置
                  </Button>
                </Space>
              </div>
              <div className="filter-bar-right">
                <Space size={8}>
                  <Button
                    loading={batchSyncing}
                    disabled={selectedRowKeys.length === 0}
                    onClick={handleBatchSync}
                  >
                    批量同步 ({selectedRowKeys.length})
                  </Button>
                  <Button
                    loading={indexing}
                    disabled={selectedRowKeys.length === 0}
                    onClick={() => handleIndex()}
                  >
                    批量索引 ({selectedRowKeys.length})
                  </Button>
                </Space>
              </div>
            </div>
            <div className="document-list-scroll">
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
                pagination={false}
              />
            </div>
            <div className="document-list-pagination">
              <Pagination
                size="small"
                current={pagination.current}
                pageSize={pagination.pageSize}
                total={pagination.total}
                showSizeChanger
                showTotal={(total) => `共 ${total} 条`}
                onChange={(page, pageSize) => {
                  setPagination((prev) => ({ ...prev, pageSize: pageSize || prev.pageSize }))
                  loadDocuments(page, filterKeyword, filterSyncStatus, filterIndexStatus)
                }}
              />
            </div>
          </Card>
        )}
      </Content>
    </Layout>
  )
}

export default DocCenterPage

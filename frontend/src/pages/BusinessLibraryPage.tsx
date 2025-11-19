import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Card, Typography, List, Spin, Empty, Space, Tag, Input, Button } from 'antd'
import ReactFlow, {
  Background,
  Controls,
  Edge,
  Node,
  applyNodeChanges,
  applyEdgeChanges,
  type NodeChange,
  type EdgeChange,
  type Connection,
} from 'reactflow'
import 'reactflow/dist/style.css'

import {
  listProcesses,
  type ProcessItem,
  getProcessSteps,
  type ProcessStep,
  saveProcessSteps,
  deleteProcessStep,
  type ProcessEdge,
  listProcessEdges,
  createProcessEdge,
  updateProcessEdge,
  deleteProcessEdge,
} from '../api/processes'
import {
  getProcessContext,
  type GraphProcessContext,
  type GraphStepEntry,
} from '../api/graph'
import { createStepImplementationLink, deleteStepImplementationLink } from '../api/resourceNodes'
import {
  createImplementationDataLink,
  deleteImplementationDataLink,
  type ImplementationDataLink,
} from '../api/dataResources'

const { Title, Paragraph, Text } = Typography

type SelectedNode =
  | {
      type: 'process'
      data: ProcessItem
    }
  | {
      type: 'step'
      data: GraphStepEntry['step']
      implementations: any[]
      dataResources: any[]
    }
  | {
      type: 'implementation'
      data: any
      dataResources: any[]
      step?: GraphStepEntry['step']
    }
  | {
      type: 'data'
      data: any
      implementations: any[]
      step?: GraphStepEntry['step']
    }

const BusinessLibraryPage: React.FC = () => {
  const [processes, setProcesses] = useState<ProcessItem[]>([])
  const [loadingProcesses, setLoadingProcesses] = useState(false)
  const [selectedProcessId, setSelectedProcessId] = useState<string | null>(null)

  const [context, setContext] = useState<GraphProcessContext | null>(null)
  const [loadingContext, setLoadingContext] = useState(false)

  const [selectedNode, setSelectedNode] = useState<SelectedNode | null>(null)

  const [steps, setSteps] = useState<ProcessStep[]>([])
  const [nodes, setNodes] = useState<Node[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [stepNameDraft, setStepNameDraft] = useState<string>('')
  const [saving, setSaving] = useState(false)

  const fetchProcesses = useCallback(async () => {
    setLoadingProcesses(true)
    try {
      const data = await listProcesses()
      setProcesses(data)
      if (!selectedProcessId && data.length > 0) {
        setSelectedProcessId(data[0].process_id)
      }
    } catch (e) {
      setProcesses([])
    } finally {
      setLoadingProcesses(false)
    }
  }, [selectedProcessId])

  useEffect(() => {
    fetchProcesses()
  }, [fetchProcesses])

  const buildGraph = useCallback(
    (stepList: ProcessStep[], ctx: GraphProcessContext | null, edgeList: ProcessEdge[]) => {
      if (!ctx) {
        setNodes([])
        setEdges([])
        return
      }

      const detailByCap = new Map<string, GraphStepEntry>()
      ctx.steps.forEach((entry) => {
        if (entry.step.step_id) {
          detailByCap.set(entry.step.step_id, entry)
        }
      })

      // 步骤横向排布
      const sorted = [...stepList].slice().sort((a, b) => a.order_no - b.order_no)
      const gapX = 220
      const stepY = 0
      const implBaseY = 140
      const dataBaseY = 260

      const stepNodes: Node[] = []
      const implNodes = new Map<string, Node>()
      const drNodes = new Map<string, Node>()

      sorted.forEach((s, index) => {
        const detail = s.capability_id ? detailByCap.get(s.capability_id) : undefined
        const stepId = s.capability_id || detail?.step.step_id || String(s.step_id)
        const displayName = s.name || detail?.step.name || stepId
        const x = index * gapX

        // Step 节点
        stepNodes.push({
          id: `step:${stepId}`,
          data: {
            label: `${index + 1}. ${displayName}`,
            capabilityId: stepId,
          },
          position: { x, y: stepY },
          type: 'default',
        })

        const entry = detail
        if (!entry) {
          return
        }

        // Implementation 节点：以 impl_id 作为唯一标识
        ;(entry.implementations || []).forEach((impl: any, implIndex: number) => {
          const implId = impl.impl_id as string | undefined
          if (!implId || implNodes.has(implId)) {
            return
          }
          const implLabel = impl.name || impl.entry_name || implId
          implNodes.set(implId, {
            id: `impl:${implId}`,
            data: {
              label: implLabel,
              implId,
            },
            position: { x, y: implBaseY + implIndex * 80 },
            type: 'default',
          })
        })

        // DataResource 节点：以 resource_id 作为唯一标识
        ;(entry.data_resources || []).forEach((dr: any, drIndex: number) => {
          const resId = dr.resource_id as string | undefined
          if (!resId || drNodes.has(resId)) {
            return
          }
          const drLabel = dr.name || dr.resource_id || resId
          drNodes.set(resId, {
            id: `dr:${resId}`,
            data: {
              label: drLabel,
              resource: dr,
            },
            position: { x, y: dataBaseY + drIndex * 80 },
            type: 'default',
          })
        })
      })

      const allNodes: Node[] = [
        ...stepNodes,
        ...Array.from(implNodes.values()),
        ...Array.from(drNodes.values()),
      ]

      // 1) 步骤之间的可编辑边（基于 ProcessStepEdge）
      const stepEdges: Edge[] = edgeList.map((edge) => ({
        id: `edge:process:${edge.id}`,
        source: `step:${edge.from_step_id}`,
        target: `step:${edge.to_step_id}`,
        label: edge.label,
        data: {
          kind: 'process',
          dbId: edge.id,
          edge_type: edge.edge_type,
          condition: edge.condition,
          label: edge.label,
        },
      }))

      // 2) Step → Implementation 边（基于 step_impl_links）
      const stepImplEdges: Edge[] = (ctx.step_impl_links || []).map((link) => ({
        id: `edge:step-impl:${link.id}`,
        source: `step:${link.step_id}`,
        target: `impl:${link.impl_id}`,
        data: {
          kind: 'step-impl',
          dbId: link.id,
        },
      }))

      // 3) Implementation → DataResource 边（基于 impl_data_links）
      const implDrEdges: Edge[] = (ctx.impl_data_links || []).map((link) => ({
        id: `edge:impl-dr:${link.id}`,
        source: `impl:${link.impl_id}`,
        target: `dr:${link.resource_id}`,
        data: {
          kind: 'impl-dr',
          dbId: link.id,
          access_type: link.access_type,
          access_pattern: link.access_pattern,
        },
      }))

      setNodes(allNodes)
      setEdges([...stepEdges, ...stepImplEdges, ...implDrEdges])
    },
    [],
  )

  useEffect(() => {
    if (!selectedProcessId) {
      setContext(null)
      setSteps([])
      setNodes([])
      setEdges([])
      setSelectedNode(null)
      return
    }

    setLoadingContext(true)
    setSelectedNode(null)

    ;(async () => {
      try {
        const [ctx, stepItems, edgeItems] = await Promise.all([
          getProcessContext(selectedProcessId),
          getProcessSteps(selectedProcessId),
          listProcessEdges(selectedProcessId),
        ])
        setContext(ctx)
        setSteps(stepItems)
        buildGraph(stepItems, ctx, edgeItems)
      } catch (e) {
        setContext(null)
        setSteps([])
        setNodes([])
        setEdges([])
      } finally {
        setLoadingContext(false)
      }
    })()
  }, [buildGraph, selectedProcessId])

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      setNodes((nds) => applyNodeChanges(changes, nds))
    },
    [],
  )

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      // 查找需要删除的边并同步到后端
      const removedIds = changes
        .filter((c) => c.type === 'remove')
        .map((c) => c.id)

      if (removedIds.length && selectedProcessId) {
        removedIds.forEach((id) => {
          const edge = edges.find((e) => e.id === id)
          const data = edge?.data as any
          const kind = data?.kind as string | undefined
          const dbId = data?.dbId as number | undefined
          if (!dbId) {
            return
          }
          if (kind === 'process') {
            deleteProcessEdge(selectedProcessId, dbId).catch(() => undefined)
          } else if (kind === 'step-impl') {
            deleteStepImplementationLink(dbId).catch(() => undefined)
          } else if (kind === 'impl-dr') {
            deleteImplementationDataLink(dbId).catch(() => undefined)
          }
        })
      }

      setEdges((eds) => applyEdgeChanges(changes, eds))
    },
    [edges, selectedProcessId],
  )

  const flowNodes: Node[] = useMemo(() => {
    if (!context || !context.steps || context.steps.length === 0) {
      return []
    }

    const gapX = 220
    const baseY = 0

    return context.steps.map((entry, index) => {
      const id = entry.step.step_id
      const label = entry.step.name || id
      return {
        id: `step:${id}`,
        data: { label: `${index + 1}. ${label}` },
        position: { x: index * gapX, y: baseY },
        type: 'default',
      }
    })
  }, [context])

  const flowEdges: Edge[] = useMemo(() => {
    if (!context || !context.steps || context.steps.length < 2) {
      return []
    }

    const edges: Edge[] = []

    context.steps.forEach((entry, index) => {
      const next = context.steps[index + 1]
      if (!next) {
        return
      }
      const currentId = `step:${entry.step.step_id}`
      const nextId = `step:${next.step.step_id}`
      edges.push({
        id: `e:${currentId}->${nextId}`,
        source: currentId,
        target: nextId,
      })
    })

    return edges
  }, [context])

  const currentProcess: ProcessItem | null = useMemo(() => {
    if (!selectedProcessId) {
      return null
    }
    const found = processes.find((p) => p.process_id === selectedProcessId)
    if (found) {
      return found
    }
    const raw = context?.process as ProcessItem | undefined
    return raw || null
  }, [context, processes, selectedProcessId])

  const handleSelectProcess = (item: ProcessItem) => {
    setSelectedProcessId(item.process_id)
    setSelectedNode({
      type: 'process',
      data: item,
    })
    setStepNameDraft('')
  }

  const handleNodeClick = (_: React.MouseEvent, node: Node) => {
    if (!context || !context.steps) {
      return
    }

    // Step 节点：与之前逻辑相同
    if (node.id.startsWith('step:')) {
      const stepId = node.id.slice('step:'.length)
      const entry = context.steps.find((s) => s.step.step_id === stepId)
      const row = steps.find((s) => s.capability_id === stepId)

      const baseStep = entry?.step
      const mergedStep: any = {
        ...(baseStep || {}),
        step_id: stepId,
        order_no: row?.order_no ?? baseStep?.order_no,
        name: row?.name ?? baseStep?.name ?? stepId,
      }

      setSelectedNode({
        type: 'step',
        data: mergedStep,
        implementations: entry?.implementations || [],
        dataResources: entry?.data_resources || [],
      })
      setStepNameDraft(mergedStep.name || '')
      return
    }

    // Implementation 节点：id = impl:{impl_id}
    if (node.id.startsWith('impl:')) {
      const implId = node.id.slice('impl:'.length)
      if (!implId) {
        return
      }

      // 找到该实现所属的 Step（优先使用 step_impl_links）
      const link = (context.step_impl_links || []).find((l) => l.impl_id === implId)
      let entry: GraphStepEntry | undefined
      if (link) {
        entry = context.steps.find((s) => s.step.step_id === link.step_id)
      }
      if (!entry) {
        entry = context.steps.find((s) =>
          (s.implementations || []).some((impl: any) => impl.impl_id === implId),
        )
      }
      if (!entry) {
        return
      }

      const impl = (entry.implementations || []).find((i: any) => i.impl_id === implId)
      if (!impl) {
        return
      }

      setSelectedNode({
        type: 'implementation',
        data: impl,
        dataResources: entry.data_resources || [],
        step: entry.step,
      })
      return
    }

    // DataResource 节点：id = dr:{resource_id}
    if (node.id.startsWith('dr:')) {
      const resourceId = node.id.slice('dr:'.length)
      if (!resourceId) {
        return
      }

      // 找到包含该数据资源的 Step
      let entry: GraphStepEntry | undefined
      let dr: any | undefined
      for (const s of context.steps) {
        const found = (s.data_resources || []).find(
          (r: any) => r.resource_id === resourceId,
        )
        if (found) {
          entry = s
          dr = found
          break
        }
      }
      if (!entry || !dr) {
        return
      }

      // 构建 impl_id -> impl 对象的索引
      const implById = new Map<string, any>()
      context.steps.forEach((s) => {
        ;(s.implementations || []).forEach((impl: any) => {
          if (impl.impl_id) {
            implById.set(impl.impl_id, impl)
          }
        })
      })

      // 根据 impl_data_links 找到访问该资源的实现列表
      const impls: any[] = []
      ;(context.impl_data_links || []).forEach((link) => {
        if (link.resource_id === resourceId) {
          const impl = implById.get(link.impl_id)
          if (impl) {
            impls.push(impl)
          }
        }
      })

      setSelectedNode({
        type: 'data',
        data: dr,
        implementations: impls,
        step: entry.step,
      })
    }
  }

  const handleStepNameChange = useCallback(
    (value: string) => {
      setStepNameDraft(value)

      const current = selectedNode
      if (!current || current.type !== 'step') {
        return
      }
      const capabilityId = current.data.step_id

      // 更新步骤列表中的名称
      setSteps((prev) =>
        prev.map((s) =>
          s.capability_id === capabilityId ? { ...s, name: value } : s,
        ),
      )

      // 更新画布节点上的 label 文本
      setNodes((prev) =>
        prev.map((node) => {
          const nodeCapId = (node.data as any)?.capabilityId as string | undefined
          if (nodeCapId !== capabilityId) {
            return node
          }
          const oldLabel = String((node.data as any)?.label ?? '')
          const dotIndex = oldLabel.indexOf('.')
          const prefix = dotIndex >= 0 ? oldLabel.slice(0, dotIndex) : ''
          const newLabel = prefix ? `${prefix}. ${value}` : value
          return {
            ...node,
            data: {
              ...(node.data as any),
              label: newLabel,
            },
          }
        }),
      )

      // 更新右侧已选节点的名称
      setSelectedNode((prev) =>
        prev && prev.type === 'step'
          ? { ...prev, data: { ...prev.data, name: value } }
          : prev,
      )
    },
    [selectedNode],
  )

  const handleSaveSteps = useCallback(async () => {
    if (!selectedProcessId || steps.length === 0) {
      return
    }
    setSaving(true)
    try {
      const payload = steps.map((s) => ({ ...s, name: s.name }))
      const saved = await saveProcessSteps(selectedProcessId, payload)
      setSteps(saved)
    } finally {
      setSaving(false)
    }
  }, [selectedProcessId, steps])

  const handleDeleteStepClick = useCallback(async () => {
    if (!selectedProcessId || !selectedNode || selectedNode.type !== 'step') {
      return
    }
    const ok = window.confirm('确认删除该步骤？')
    if (!ok) {
      return
    }
    const capabilityId = selectedNode.data.step_id
    const row = steps.find((s) => s.capability_id === capabilityId)
    if (!row) {
      return
    }

    setSaving(true)
    try {
      await deleteProcessStep(selectedProcessId, row.step_id)
      const remaining = steps.filter((s) => s.step_id !== row.step_id)
      setSteps(remaining)

      // 同步移除画布上的节点和相关连线
      setNodes((prev) =>
        prev.filter((node) => {
          const nodeCapId = (node.data as any)?.capabilityId as string | undefined
          return nodeCapId !== capabilityId
        }),
      )
      setEdges((prev) =>
        prev.filter(
          (edge) =>
            !edge.source.endsWith(`:${capabilityId}`) &&
            !edge.target.endsWith(`:${capabilityId}`),
        ),
      )

      setSelectedNode(null)
      setStepNameDraft('')
    } finally {
      setSaving(false)
    }
  }, [selectedNode, selectedProcessId, steps])

  const handleConnect = useCallback(
    async (connection: Connection) => {
      if (!selectedProcessId) {
        return
      }

      const rawSource = connection.source || ''
      const rawTarget = connection.target || ''
      if (!rawSource || !rawTarget) {
        return
      }

      const sourceIsStep = rawSource.startsWith('step:')
      const sourceIsImpl = rawSource.startsWith('impl:')
      const sourceIsDr = rawSource.startsWith('dr:')
      const targetIsStep = rawTarget.startsWith('step:')
      const targetIsImpl = rawTarget.startsWith('impl:')
      const targetIsDr = rawTarget.startsWith('dr:')

      // 1) Step ↔ Step：流程边
      if (sourceIsStep && targetIsStep) {
        const fromStepId = rawSource.slice('step:'.length)
        const toStepId = rawTarget.slice('step:'.length)
        if (!fromStepId || !toStepId) {
          return
        }
        try {
          const created = await createProcessEdge(selectedProcessId, {
            from_step_id: fromStepId,
            to_step_id: toStepId,
            edge_type: undefined,
            condition: undefined,
            label: undefined,
          })
          setEdges((prev) => [
            ...prev,
            {
              id: `edge:process:${created.id}`,
              source: `step:${created.from_step_id}`,
              target: `step:${created.to_step_id}`,
              label: created.label,
              data: {
                kind: 'process',
                dbId: created.id,
                edge_type: created.edge_type,
                condition: created.condition,
                label: created.label,
              },
            },
          ])
        } catch (e) {
          // ignore
        }
        return
      }

      // 2) Step ↔ Implementation：Step-Implementation 关系
      if (
        (sourceIsStep && targetIsImpl) ||
        (sourceIsImpl && targetIsStep)
      ) {
        const stepId = (sourceIsStep ? rawSource : rawTarget).slice('step:'.length)
        const implId = (sourceIsImpl ? rawSource : rawTarget).slice('impl:'.length)
        if (!stepId || !implId) {
          return
        }
        try {
          const link = await createStepImplementationLink(stepId, implId)
          setEdges((prev) => [
            ...prev,
            {
              id: `edge:step-impl:${link.id}`,
              source: `step:${link.step_id}`,
              target: `impl:${link.impl_id}`,
              data: {
                kind: 'step-impl',
                dbId: link.id,
              },
            },
          ])
        } catch (e) {
          // ignore
        }
        return
      }

      // 3) Implementation ↔ DataResource：Implementation-DataResource 关系
      if (
        (sourceIsImpl && targetIsDr) ||
        (sourceIsDr && targetIsImpl)
      ) {
        const implId = (sourceIsImpl ? rawSource : rawTarget).slice('impl:'.length)
        const resId = (sourceIsDr ? rawSource : rawTarget).slice('dr:'.length)
        if (!implId || !resId) {
          return
        }
        try {
          const link = await createImplementationDataLink({
            impl_id: implId,
            resource_id: resId,
            access_type: undefined,
            access_pattern: undefined,
          })
          setEdges((prev) => [
            ...prev,
            {
              id: `edge:impl-dr:${link.id}`,
              source: `impl:${link.impl_id}`,
              target: `dr:${link.resource_id}`,
              data: {
                kind: 'impl-dr',
                dbId: link.id,
                access_type: link.access_type,
                access_pattern: link.access_pattern,
              },
            },
          ])
        } catch (e) {
          // ignore
        }
        return
      }

      // 其它组合不允许
    },
    [selectedProcessId],
  )

  const handleEdgeUpdate = useCallback(
    async (oldEdge: Edge, connection: Connection) => {
      if (!selectedProcessId) {
        return
      }
      const data = oldEdge.data as any
      const kind = data?.kind as string | undefined
      const dbId = data?.dbId as number | undefined
      const rawSource = connection.source || ''
      const rawTarget = connection.target || ''

      if (!dbId) {
        return
      }

      // 1) 流程边：Step ↔ Step
      if (kind === 'process') {
        if (!rawSource.startsWith('step:') || !rawTarget.startsWith('step:')) {
          return
        }
        const fromStepId = rawSource.slice('step:'.length)
        const toStepId = rawTarget.slice('step:'.length)
        if (!fromStepId || !toStepId) {
          return
        }
        try {
          const updated = await updateProcessEdge(selectedProcessId, dbId, {
            from_step_id: fromStepId,
            to_step_id: toStepId,
          })
          setEdges((prev) =>
            prev.map((e) =>
              e.id === oldEdge.id
                ? {
                    ...e,
                    id: `edge:process:${updated.id}`,
                    source: `step:${updated.from_step_id}`,
                    target: `step:${updated.to_step_id}`,
                    label: updated.label,
                    data: {
                      kind: 'process',
                      dbId: updated.id,
                      edge_type: updated.edge_type,
                      condition: updated.condition,
                      label: updated.label,
                    },
                  }
                : e,
            ),
          )
        } catch (e) {
          // ignore
        }
        return
      }

      // 2) Step-Implementation：通过删旧建新实现拖动修改
      if (kind === 'step-impl') {
        const sourceIsStep = rawSource.startsWith('step:')
        const sourceIsImpl = rawSource.startsWith('impl:')
        const targetIsStep = rawTarget.startsWith('step:')
        const targetIsImpl = rawTarget.startsWith('impl:')
        if (
          !(
            (sourceIsStep && targetIsImpl) ||
            (sourceIsImpl && targetIsStep)
          )
        ) {
          return
        }
        const stepId = (sourceIsStep ? rawSource : rawTarget).slice('step:'.length)
        const implId = (sourceIsImpl ? rawSource : rawTarget).slice('impl:'.length)
        if (!stepId || !implId) {
          return
        }
        try {
          await deleteStepImplementationLink(dbId)
          const link = await createStepImplementationLink(stepId, implId)
          setEdges((prev) =>
            prev.map((e) =>
              e.id === oldEdge.id
                ? {
                    ...e,
                    id: `edge:step-impl:${link.id}`,
                    source: `step:${link.step_id}`,
                    target: `impl:${link.impl_id}`,
                    data: {
                      kind: 'step-impl',
                      dbId: link.id,
                    },
                  }
                : e,
            ),
          )
        } catch (e) {
          // ignore
        }
        return
      }

      // 3) Implementation-DataResource：同样通过删旧建新
      if (kind === 'impl-dr') {
        const sourceIsImpl = rawSource.startsWith('impl:')
        const sourceIsDr = rawSource.startsWith('dr:')
        const targetIsImpl = rawTarget.startsWith('impl:')
        const targetIsDr = rawTarget.startsWith('dr:')
        if (
          !(
            (sourceIsImpl && targetIsDr) ||
            (sourceIsDr && targetIsImpl)
          )
        ) {
          return
        }
        const implId = (sourceIsImpl ? rawSource : rawTarget).slice('impl:'.length)
        const resId = (sourceIsDr ? rawSource : rawTarget).slice('dr:'.length)
        if (!implId || !resId) {
          return
        }
        try {
          await deleteImplementationDataLink(dbId)
          const link: ImplementationDataLink = await createImplementationDataLink({
            impl_id: implId,
            resource_id: resId,
            access_type: data?.access_type,
            access_pattern: data?.access_pattern,
          })
          setEdges((prev) =>
            prev.map((e) =>
              e.id === oldEdge.id
                ? {
                    ...e,
                    id: `edge:impl-dr:${link.id}`,
                    source: `impl:${link.impl_id}`,
                    target: `dr:${link.resource_id}`,
                    data: {
                      kind: 'impl-dr',
                      dbId: link.id,
                      access_type: link.access_type,
                      access_pattern: link.access_pattern,
                    },
                  }
                : e,
            ),
          )
        } catch (e) {
          // ignore
        }
      }
    },
    [selectedProcessId],
  )

  const showSidebar = !!selectedNode

  return (
    <div
      style={{
        display: 'flex',
        height: '100%',
        minHeight: 480,
      }}
    >
      <div
        style={{
          width: 280,
          borderRight: '1px solid #f0f0f0',
          padding: 16,
          overflow: 'auto',
        }}
      >
        <Title level={3} style={{ marginBottom: 16 }}>
          业务库
        </Title>
        <Paragraph type="secondary" style={{ marginBottom: 12 }}>
          左侧选择业务，中心查看流程画布，点击步骤查看右侧详情。
        </Paragraph>
        {loadingProcesses ? (
          <div
            style={{
              paddingTop: 40,
              textAlign: 'center',
            }}
          >
            <Spin />
          </div>
        ) : processes.length === 0 ? (
          <Empty description="暂无业务流程" />
        ) : (
          <List<ProcessItem>
            size="small"
            dataSource={processes}
            rowKey={(item) => item.process_id}
            renderItem={(item) => (
              <List.Item
                style={{
                  cursor: 'pointer',
                  borderRadius: 4,
                  marginBottom: 4,
                  paddingLeft: 8,
                  paddingRight: 8,
                  backgroundColor:
                    item.process_id === selectedProcessId ? '#e6f4ff' : undefined,
                }}
                onClick={() => handleSelectProcess(item)}
              >
                <List.Item.Meta
                  title={
                    <Space size={8}>
                      <span>{item.name}</span>
                      <Tag color="blue">{item.process_id}</Tag>
                    </Space>
                  }
                  description={
                    item.description ? (
                      <span style={{ fontSize: 12 }}>{item.description}</span>
                    ) : null
                  }
                />
              </List.Item>
            )}
          />
        )}
      </div>

      <div
        style={{
          flex: 1,
          padding: 16,
          overflow: 'hidden',
          transition: 'padding-right 0.25s ease',
        }}
      >
        <Card
          size="small"
          title={currentProcess?.name || '业务流程画布'}
          extra={
            currentProcess?.channel ? (
              <Tag color="geekblue">{currentProcess.channel}</Tag>
            ) : null
          }
          style={{ height: '100%' }}
          bodyStyle={{ height: '100%' }}
        >
          {loadingContext ? (
            <div
              style={{
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Spin />
            </div>
          ) : !nodes.length ? (
            <div
              style={{
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Empty description="暂无流程步骤" />
            </div>
          ) : (
            <div style={{ width: '100%', height: '100%' }}>
              <ReactFlow
                nodes={nodes}
                edges={edges}
                fitView
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={handleConnect}
                onEdgeUpdate={handleEdgeUpdate}
                onNodeClick={handleNodeClick}
                onPaneClick={() => setSelectedNode(null)}
              >
                <Background />
                <Controls />
              </ReactFlow>
            </div>
          )}
        </Card>
      </div>

      <div
        style={{
          width: showSidebar ? 360 : 0,
          transition: 'width 0.25s ease',
          borderLeft: showSidebar ? '1px solid #f0f0f0' : 'none',
          backgroundColor: showSidebar ? '#fff' : 'transparent',
          overflow: 'hidden',
        }}
      >
        {showSidebar && selectedNode && (
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
              <Title level={5} style={{ margin: 0 }}>
                {selectedNode.type === 'process' ? '业务信息' : '步骤详情'}
              </Title>
            </Space>

            {selectedNode.type === 'process' && (
              <div>
                <Paragraph>
                  <Text strong>流程ID：</Text>
                  <Text>{selectedNode.data.process_id}</Text>
                </Paragraph>
                {selectedNode.data.channel && (
                  <Paragraph>
                    <Text strong>渠道：</Text>
                    <Text>{selectedNode.data.channel}</Text>
                  </Paragraph>
                )}
                {selectedNode.data.entrypoints &&
                  selectedNode.data.entrypoints.length > 0 && (
                    <Paragraph>
                      <Text strong>入口：</Text>
                      <Text>{selectedNode.data.entrypoints.join(', ')}</Text>
                    </Paragraph>
                  )}
                {selectedNode.data.description && (
                  <Paragraph>
                    <Text strong>描述：</Text>
                    <Text>{selectedNode.data.description}</Text>
                  </Paragraph>
                )}
              </div>
            )}

            {selectedNode.type === 'step' && (
              <div>
                <Paragraph>
                  <Text strong>步骤ID：</Text>
                  <Text>{selectedNode.data.step_id}</Text>
                </Paragraph>
                <Paragraph>
                  <Text strong>名称：</Text>
                  <Input
                    size="small"
                    value={stepNameDraft}
                    onChange={(e) => handleStepNameChange(e.target.value)}
                    style={{ marginTop: 4 }}
                  />
                </Paragraph>
                {typeof selectedNode.data.order_no !== 'undefined' && (
                  <Paragraph>
                    <Text strong>顺序：</Text>
                    <Text>{String(selectedNode.data.order_no)}</Text>
                  </Paragraph>
                )}
                {selectedNode.data.step_type && (
                  <Paragraph>
                    <Text strong>类型：</Text>
                    <Text>{selectedNode.data.step_type}</Text>
                  </Paragraph>
                )}
                {selectedNode.data.description && (
                  <Paragraph>
                    <Text strong>描述：</Text>
                    <Text>{selectedNode.data.description}</Text>
                  </Paragraph>
                )}

                <div style={{ marginTop: 16 }}>
                  <Text strong>相关实现</Text>
                  {selectedNode.implementations.length === 0 ? (
                    <Paragraph type="secondary" style={{ marginTop: 4 }}>
                      暂无实现信息
                    </Paragraph>
                  ) : (
                    <List
                      size="small"
                      style={{ marginTop: 8 }}
                      dataSource={selectedNode.implementations}
                      rowKey={(impl: any) => impl.impl_id || impl.name || ''}
                      renderItem={(impl: any) => (
                        <List.Item>
                          <Space direction="vertical" size={2}>
                            <span>
                              {impl.name}
                              {impl.system ? (
                                <Tag style={{ marginLeft: 8 }}>{impl.system}</Tag>
                              ) : null}
                            </span>
                            {impl.type && (
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                类型：{impl.type}
                              </Text>
                            )}
                            {impl.code_ref && (
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                代码位置：{impl.code_ref}
                              </Text>
                            )}
                          </Space>
                        </List.Item>
                      )}
                    />
                  )}
                </div>

                <div style={{ marginTop: 16 }}>
                  <Text strong>相关数据资源</Text>
                  {selectedNode.dataResources.length === 0 ? (
                    <Paragraph type="secondary" style={{ marginTop: 4 }}>
                      暂无数据资源信息
                    </Paragraph>
                  ) : (
                    <List
                      size="small"
                      style={{ marginTop: 8 }}
                      dataSource={selectedNode.dataResources}
                      rowKey={(dr: any) => dr.resource_id || dr.name || ''}
                      renderItem={(dr: any) => (
                        <List.Item>
                          <Space direction="vertical" size={2}>
                            <span>
                              {dr.name}
                              {dr.type ? (
                                <Tag style={{ marginLeft: 8 }}>{dr.type}</Tag>
                              ) : null}
                            </span>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              ID：{dr.resource_id}
                            </Text>
                            {dr.system && (
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                系统：{dr.system}
                              </Text>
                            )}
                            {dr.access_type && (
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                访问类型：{dr.access_type}
                              </Text>
                            )}
                            {dr.access_pattern && (
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                访问模式：{dr.access_pattern}
                              </Text>
                            )}
                            {dr.description && (
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                描述：{dr.description}
                              </Text>
                            )}
                          </Space>
                        </List.Item>
                      )}
                    />
                  )}
                </div>
              </div>
            )}

            {selectedNode.type === 'implementation' && (
              <div>
                <Paragraph>
                  <Text strong>所属能力：</Text>
                  <Text>{selectedNode.step?.name || selectedNode.step?.step_id}</Text>
                </Paragraph>
                <Paragraph>
                  <Text strong>实现名称：</Text>
                  <Text>{selectedNode.data.name || selectedNode.data.entry_name}</Text>
                </Paragraph>
                {selectedNode.data.system && (
                  <Paragraph>
                    <Text strong>系统：</Text>
                    <Text>{selectedNode.data.system}</Text>
                  </Paragraph>
                )}
                {selectedNode.data.type && (
                  <Paragraph>
                    <Text strong>类型：</Text>
                    <Text>{selectedNode.data.type}</Text>
                  </Paragraph>
                )}
                {selectedNode.data.code_ref && (
                  <Paragraph>
                    <Text strong>代码位置：</Text>
                    <Text>{selectedNode.data.code_ref}</Text>
                  </Paragraph>
                )}

                <div style={{ marginTop: 16 }}>
                  <Text strong>访问的数据资源</Text>
                  {selectedNode.dataResources.length === 0 ? (
                    <Paragraph type="secondary" style={{ marginTop: 4 }}>
                      暂无数据资源信息
                    </Paragraph>
                  ) : (
                    <List
                      size="small"
                      style={{ marginTop: 8 }}
                      dataSource={selectedNode.dataResources}
                      rowKey={(dr: any) => dr.resource_id || dr.name || ''}
                      renderItem={(dr: any) => (
                        <List.Item>
                          <Space direction="vertical" size={2}>
                            <span>
                              {dr.name}
                              {dr.type ? (
                                <Tag style={{ marginLeft: 8 }}>{dr.type}</Tag>
                              ) : null}
                            </span>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              ID：{dr.resource_id}
                            </Text>
                            {dr.system && (
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                系统：{dr.system}
                              </Text>
                            )}
                            {dr.access_type && (
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                访问类型：{dr.access_type}
                              </Text>
                            )}
                            {dr.access_pattern && (
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                访问模式：{dr.access_pattern}
                              </Text>
                            )}
                          </Space>
                        </List.Item>
                      )}
                    />
                  )}
                </div>
              </div>
            )}

            {selectedNode.type === 'data' && (
              <div>
                <Paragraph>
                  <Text strong>资源ID：</Text>
                  <Text>{selectedNode.data.resource_id}</Text>
                </Paragraph>
                <Paragraph>
                  <Text strong>名称：</Text>
                  <Text>{selectedNode.data.name}</Text>
                </Paragraph>
                {selectedNode.data.type && (
                  <Paragraph>
                    <Text strong>类型：</Text>
                    <Text>{selectedNode.data.type}</Text>
                  </Paragraph>
                )}
                {selectedNode.data.system && (
                  <Paragraph>
                    <Text strong>系统：</Text>
                    <Text>{selectedNode.data.system}</Text>
                  </Paragraph>
                )}
                {selectedNode.data.description && (
                  <Paragraph>
                    <Text strong>描述：</Text>
                    <Text>{selectedNode.data.description}</Text>
                  </Paragraph>
                )}
                {selectedNode.data.access_type && (
                  <Paragraph>
                    <Text strong>访问类型：</Text>
                    <Text>{selectedNode.data.access_type}</Text>
                  </Paragraph>
                )}
                {selectedNode.data.access_pattern && (
                  <Paragraph>
                    <Text strong>访问模式：</Text>
                    <Text>{selectedNode.data.access_pattern}</Text>
                  </Paragraph>
                )}

                <div style={{ marginTop: 16 }}>
                  <Text strong>相关实现</Text>
                  {selectedNode.implementations.length === 0 ? (
                    <Paragraph type="secondary" style={{ marginTop: 4 }}>
                      暂无实现信息
                    </Paragraph>
                  ) : (
                    <List
                      size="small"
                      style={{ marginTop: 8 }}
                      dataSource={selectedNode.implementations}
                      rowKey={(impl: any) => impl.impl_id || impl.name || ''}
                      renderItem={(impl: any) => (
                        <List.Item>
                          <Space direction="vertical" size={2}>
                            <span>
                              {impl.name}
                              {impl.system ? (
                                <Tag style={{ marginLeft: 8 }}>{impl.system}</Tag>
                              ) : null}
                            </span>
                            {impl.type && (
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                类型：{impl.type}
                              </Text>
                            )}
                            {impl.code_ref && (
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                代码位置：{impl.code_ref}
                              </Text>
                            )}
                          </Space>
                        </List.Item>
                      )}
                    />
                  )}
                </div>
              </div>
            )}

            <div style={{ marginTop: 24 }}>
              <Space>
                <Button
                  type="primary"
                  size="small"
                  loading={saving}
                  onClick={handleSaveSteps}
                >
                  保存步骤
                </Button>
                {selectedNode.type === 'step' && (
                  <Button
                    danger
                    size="small"
                    loading={saving}
                    onClick={handleDeleteStepClick}
                  >
                    删除该步骤
                  </Button>
                )}
              </Space>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default BusinessLibraryPage

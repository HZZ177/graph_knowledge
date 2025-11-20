import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Card, Typography, List, Spin, Empty, Space, Tag, Button } from 'antd'
import {
  ReactFlow,
  Background,
  Controls,
  Edge,
  Node,
  MarkerType,
  Position,
  Handle,
  NodeResizer,
  applyNodeChanges,
  applyEdgeChanges,
  reconnectEdge,
  type NodeChange,
  type EdgeChange,
  type Connection,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import {
  listProcesses,
  type ProcessItem,
} from '../api/processes'
import {
  getProcessCanvas,
  saveProcessCanvas,
  type ProcessCanvas,
} from '../api/canvas'

const { Title, Paragraph, Text } = Typography

const layoutGraph = (nodes: Node[], edges: Edge[]) => {
  const layoutedNodes: Node[] = nodes.map((node) => ({
    ...node,
  }))

  const layoutedEdges: Edge[] = edges.map((edge) => ({
    ...edge,
    type: edge.type || 'simplebezier',
    markerEnd: { type: MarkerType.ArrowClosed },
  }))

  return { nodes: layoutedNodes, edges: layoutedEdges }
}

const AllSidesNode = React.memo(({ data, selected }: any) => {
  const [hovered, setHovered] = useState(false)
  const baseHandleStyle = {
    width: 4,
    height: 4,
    background: '#bfbfbf',
    border: '1px solid #d9d9d9',
    borderRadius: '50%',
  } as const

  const nodeType = data?.nodeType as 'step' | 'implementation' | 'data' | undefined
  let headerBg = '#f5f5f5'
  let headerColor = '#595959'

  if (nodeType === 'step') {
    headerBg = '#e6f4ff'
    headerColor = '#0958d9'
  } else if (nodeType === 'implementation') {
    headerBg = '#f6ffed'
    headerColor = '#237804'
  } else if (nodeType === 'data') {
    headerBg = '#fff7e6'
    headerColor = '#ad6800'
  }

  return (
    <>
      <NodeResizer
        isVisible={selected}
        minWidth={120}
        minHeight={40}
        lineStyle={{ border: 'none' }}
        handleStyle={{
          width: 6,
          height: 6,
          borderRadius: 2,
          border: '1px solid #d9d9d9',
          background: '#ffffff',
        }}
      />
      <Handle
        type="target"
        position={Position.Top}
        id="t-in"
        style={{ ...baseHandleStyle, top: -1 }}
      />
      <Handle
        type="source"
        position={Position.Top}
        id="t-out"
        style={{ ...baseHandleStyle, top: -1 }}
      />
      <Handle
        type="target"
        position={Position.Bottom}
        id="b-in"
        style={{ ...baseHandleStyle, bottom: -1 }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="b-out"
        style={{ ...baseHandleStyle, bottom:-1 }}
      />
      <Handle
        type="target"
        position={Position.Left}
        id="l-in"
        style={{ ...baseHandleStyle, left: -1 }}
      />
      <Handle
        type="source"
        position={Position.Left}
        id="l-out"
        style={{ ...baseHandleStyle, left: -1 }}
      />
      <Handle
        type="target"
        position={Position.Right}
        id="r-in"
        style={{ ...baseHandleStyle, right: -1 }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="r-out"
        style={{ ...baseHandleStyle, right: -1 }}
      />
      <div
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{
          borderRadius: 14,
          background: '#ffffff',
          overflow: 'hidden',
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: selected
            ? '0 6px 16px rgba(0, 0, 0, 0.25)'
            : hovered
            ? '0 4px 12px rgba(0, 0, 0, 0.2)'
            : '0 2px 8px rgba(0, 0, 0, 0.15)',
          border: selected ? '1px solid #1677ff' : '1px solid transparent',
          transform: hovered && !selected ? 'translateY(-1px)' : 'translateY(0)',
          transition: 'box-shadow 0.15s ease, transform 0.15s ease, border-color 0.15s ease',
        }}
      >
        {data?.typeLabel && (
          <div
            style={{
              padding: '4px 8px',
              background: headerBg,
              color: headerColor,
              borderBottom: '1px solid #f0f0f0',
              fontWeight: 500,
              fontSize: 11,
              borderTopLeftRadius: 12,
              borderTopRightRadius: 12,
            }}
          >
            {data.typeLabel}
          </div>
        )}
        <div
          style={{
            padding: 8,
            fontSize: 12,
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {data?.label}
        </div>
      </div>
    </>
  )
})

type SelectedNode =
  | {
      type: 'process'
      data: ProcessItem
    }
  | {
      type: 'step'
      data: any
      implementations: any[]
      dataResources: any[]
    }
  | {
      type: 'implementation'
      data: any
      dataResources: any[]
      step?: any
    }
  | {
      type: 'data'
      data: any
      implementations: any[]
      step?: any
    }

const BusinessLibraryPage: React.FC = () => {
  const [processes, setProcesses] = useState<ProcessItem[]>([])
  const [loadingProcesses, setLoadingProcesses] = useState(false)
  const [selectedProcessId, setSelectedProcessId] = useState<string | null>(null)

  const [canvas, setCanvas] = useState<ProcessCanvas | null>(null)
  const [loadingCanvas, setLoadingCanvas] = useState(false)

  const [selectedNode, setSelectedNode] = useState<SelectedNode | null>(null)

  const [nodes, setNodes] = useState<Node[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [highlightNodeId, setHighlightNodeId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [hasChanges, setHasChanges] = useState(false)

  const nodeTypes = useMemo(
    () => ({
      allSides: AllSidesNode,
    }),
    [],
  )

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
    (canvasData: ProcessCanvas) => {
      if (!canvasData) {
        setNodes([])
        setEdges([])
        return
      }

      const stepById = new Map(canvasData.steps.map((s) => [s.step_id, s]))
      const implById = new Map(canvasData.implementations.map((i) => [i.impl_id, i]))
      const drById = new Map(canvasData.data_resources.map((d) => [d.resource_id, d]))

      const stepImplMap = new Map<string, string[]>()
      canvasData.step_impl_links.forEach((link) => {
        if (!stepImplMap.has(link.step_id)) {
          stepImplMap.set(link.step_id, [])
        }
        stepImplMap.get(link.step_id)!.push(link.impl_id)
      })

      const implDataMap = new Map<string, Array<{ resource_id: string; access_type?: string | null; access_pattern?: string | null }>>()
      canvasData.impl_data_links.forEach((link) => {
        if (!implDataMap.has(link.impl_id)) {
          implDataMap.set(link.impl_id, [])
        }
        implDataMap.get(link.impl_id)!.push({
          resource_id: link.resource_id,
          access_type: link.access_type,
          access_pattern: link.access_pattern,
        })
      })

      const edgeStepIds = new Set<string>()
      canvasData.edges.forEach((e) => {
        edgeStepIds.add(e.from_step_id)
        edgeStepIds.add(e.to_step_id)
      })

      // 拓扑排序：根据边关系确定步骤顺序
      const inDegree = new Map<string, number>()
      const outEdges = new Map<string, string[]>()
      
      edgeStepIds.forEach((id) => {
        inDegree.set(id, 0)
        outEdges.set(id, [])
      })
      
      canvasData.edges.forEach((e) => {
        inDegree.set(e.to_step_id, (inDegree.get(e.to_step_id) || 0) + 1)
        outEdges.get(e.from_step_id)?.push(e.to_step_id)
      })
      
      // BFS 拓扑排序
      const queue: string[] = []
      inDegree.forEach((degree, stepId) => {
        if (degree === 0) queue.push(stepId)
      })
      
      const sortedStepIds: string[] = []
      while (queue.length > 0) {
        const current = queue.shift()!
        sortedStepIds.push(current)
        
        outEdges.get(current)?.forEach((next) => {
          const newDegree = (inDegree.get(next) || 0) - 1
          inDegree.set(next, newDegree)
          if (newDegree === 0) {
            queue.push(next)
          }
        })
      }
      
      const sorted = sortedStepIds
        .map((id) => canvasData.steps.find((s) => s.step_id === id))
        .filter((s): s is NonNullable<typeof s> => s !== undefined)

      const stepGapX = 260
      const stepY = 0
      const implY = 180
      const dataY = 360

      const stepNodes: Node[] = []
      const implNodes = new Map<string, Node>()
      const drNodes = new Map<string, Node>()
      const implXMap = new Map<string, number>()

      sorted.forEach((s, index) => {
        const stepId = s.step_id
        const displayName = s.name || stepId
        const stepX = index * stepGapX

        stepNodes.push({
          id: `step:${stepId}`,
          data: {
            label: `${index + 1}. ${displayName}`,
            stepId,
            nodeType: 'step',
            typeLabel: '步骤',
          },
          position: { x: stepX, y: stepY },
          type: 'allSides',
          style: {
            padding: 0,
            border: 'none',
            background: 'transparent',
            boxShadow: 'none',
          },
        })

        const implIds = stepImplMap.get(stepId) || []
        const implCount = implIds.length
        implIds.forEach((implId, implIndex) => {
          if (implNodes.has(implId)) return
          const impl = implById.get(implId)
          if (!impl) return
          const implLabel = impl.name || implId
          const implOffsetX =
            implCount > 1 ? (implIndex - (implCount - 1) / 2) * 120 : 0
          const implX = stepX + implOffsetX

          implNodes.set(implId, {
            id: `impl:${implId}`,
            data: {
              label: implLabel,
              implId,
              nodeType: 'implementation',
              typeLabel: '实现',
            },
            position: {
              x: implX,
              y: implY,
            },
            type: 'allSides',
            style: {
              padding: 0,
              border: 'none',
              background: 'transparent',
              boxShadow: 'none',
            },
          })
          implXMap.set(implId, implX)
        })

        implIds.forEach((implId) => {
          const dataLinks = implDataMap.get(implId) || []
          const dataCount = dataLinks.length
          dataLinks.forEach((link, drIndex) => {
            const resId = link.resource_id
            if (drNodes.has(resId)) return
            const dr = drById.get(resId)
            if (!dr) return
            const drLabel = dr.name || resId
            const baseImplX = implXMap.get(implId) ?? stepX
            const drOffsetX =
              dataCount > 1 ? (drIndex - (dataCount - 1) / 2) * 120 : 0
            const drX = baseImplX + drOffsetX

            drNodes.set(resId, {
              id: `dr:${resId}`,
              data: {
                label: drLabel,
                resource: dr,
                nodeType: 'data',
                typeLabel: '数据资源',
              },
              position: {
                x: drX,
                y: dataY,
              },
              type: 'allSides',
              style: {
                padding: 0,
                border: 'none',
                background: 'transparent',
                boxShadow: 'none',
              },
            })
          })
        })
      })

      const allNodes: Node[] = [
        ...stepNodes,
        ...Array.from(implNodes.values()),
        ...Array.from(drNodes.values()),
      ]

      const stepEdges: Edge[] = canvasData.edges.map((edge, idx) => ({
        id: `edge:process:${edge.id || idx}`,
        source: `step:${edge.from_step_id}`,
        target: `step:${edge.to_step_id}`,
        sourceHandle: edge.from_handle || undefined,
        targetHandle: edge.to_handle || undefined,
        label: edge.label || undefined,
        style: {
          stroke: '#1677ff',
        },
        data: {
          kind: 'process',
          edge_type: edge.edge_type,
          condition: edge.condition,
          label: edge.label,
        },
      }))

      const stepImplEdges: Edge[] = canvasData.step_impl_links.map((link, idx) => ({
        id: `edge:step-impl:${link.id || idx}`,
        source: `step:${link.step_id}`,
        target: `impl:${link.impl_id}`,
        sourceHandle: link.step_handle || undefined,
        targetHandle: link.impl_handle || undefined,
        style: {
          stroke: '#52c41a',
        },
        data: {
          kind: 'step-impl',
        },
      }))

      const implDrEdges: Edge[] = canvasData.impl_data_links.map((link, idx) => ({
        id: `edge:impl-dr:${link.id || idx}`,
        source: `impl:${link.impl_id}`,
        target: `dr:${link.resource_id}`,
        sourceHandle: link.impl_handle || undefined,
        targetHandle: link.resource_handle || undefined,
        style: {
          stroke: '#faad14',
        },
        data: {
          kind: 'impl-dr',
          access_type: link.access_type,
          access_pattern: link.access_pattern,
        },
      }))

      const allEdges: Edge[] = [...stepEdges, ...stepImplEdges, ...implDrEdges]
      const { nodes: layoutedNodes, edges: layoutedEdges } = layoutGraph(allNodes, allEdges)

      setNodes(layoutedNodes)
      setEdges(layoutedEdges)
    },
    [],
  )

  const loadCanvas = useCallback(async () => {
    if (!selectedProcessId) {
      setCanvas(null)
      setNodes([])
      setEdges([])
      setSelectedNode(null)
      setHasChanges(false)
      return
    }

    setLoadingCanvas(true)
    setSelectedNode(null)

    try {
      const canvasData = await getProcessCanvas(selectedProcessId)
      setCanvas(canvasData)
      buildGraph(canvasData)
      setHasChanges(false)
    } catch (e) {
      setCanvas(null)
      setNodes([])
      setEdges([])
    } finally {
      setLoadingCanvas(false)
    }
  }, [buildGraph, selectedProcessId])

  useEffect(() => {
    loadCanvas()
  }, [loadCanvas])

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      setNodes((nds) => applyNodeChanges(changes, nds))
    },
    [],
  )

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      setEdges((eds) => applyEdgeChanges(changes, eds))
      setHasChanges(true)
    },
    [],
  )

  const displayEdges: Edge[] = useMemo(() => {
    return edges.map((edge) => {
      const isSelected = !!edge.selected
      const isConnected =
        !!highlightNodeId &&
        (edge.source === highlightNodeId || edge.target === highlightNodeId)

      const baseStyle = edge.style || {}

      let stroke = baseStyle.stroke
      let strokeWidth = (baseStyle as any).strokeWidth ?? 1.5
      let opacity = (baseStyle as any).opacity ?? 1
      let strokeDasharray = baseStyle.strokeDasharray as string | undefined

      if (highlightNodeId) {
        opacity = isConnected ? 1 : 0.15
        strokeDasharray = isConnected ? '6 3' : undefined
      }

      if (isSelected) {
        stroke = '#40a9ff'
        strokeWidth = 2.5
        opacity = 1
        strokeDasharray = undefined
      }

      return {
        ...edge,
        animated: isConnected || isSelected,
        style: {
          ...baseStyle,
          stroke,
          strokeWidth,
          opacity,
          strokeDasharray,
        },
      }
    })
  }, [edges, highlightNodeId])

  const displayNodes: Node[] = useMemo(() => {
    if (!highlightNodeId) {
      return nodes
    }

    const connectedIds = new Set<string>()
    connectedIds.add(highlightNodeId)
    edges.forEach((edge) => {
      if (edge.source === highlightNodeId || edge.target === highlightNodeId) {
        connectedIds.add(edge.source)
        connectedIds.add(edge.target)
      }
    })

    return nodes.map((node) => {
      const isConnected = connectedIds.has(node.id)
      return {
        ...node,
        style: {
          ...(node.style || {}),
          opacity: isConnected ? 1 : 0.3,
        },
      }
    })
  }, [nodes, edges, highlightNodeId])

  const currentProcess: ProcessItem | null = useMemo(() => {
    if (!selectedProcessId) {
      return null
    }
    const found = processes.find((p) => p.process_id === selectedProcessId)
    if (found) {
      return found
    }
    if (canvas?.process) {
      return {
        process_id: canvas.process.process_id,
        name: canvas.process.name,
        channel: canvas.process.channel || undefined,
        description: canvas.process.description || undefined,
        entrypoints: canvas.process.entrypoints,
      }
    }
    return null
  }, [canvas, processes, selectedProcessId])

  const handleSelectProcess = (item: ProcessItem) => {
    if (hasChanges) {
      const ok = window.confirm('有未保存的更改，是否放弃？')
      if (!ok) return
    }
    setSelectedProcessId(item.process_id)
    setSelectedNode({
      type: 'process',
      data: item,
    })
  }

  const handleNodeClick = (_: React.MouseEvent, node: Node) => {
    setHighlightNodeId(node.id)
    if (!canvas) return

    if (node.id.startsWith('step:')) {
      const stepId = node.id.slice('step:'.length)
      const step = canvas.steps.find((s) => s.step_id === stepId)
      if (!step) return

      const implIds = canvas.step_impl_links
        .filter((l) => l.step_id === stepId)
        .map((l) => l.impl_id)
      const implementations = canvas.implementations.filter((i) =>
        implIds.includes(i.impl_id),
      )

      const dataResourceIds = new Set<string>()
      implIds.forEach((implId) => {
        canvas.impl_data_links
          .filter((l) => l.impl_id === implId)
          .forEach((l) => dataResourceIds.add(l.resource_id))
      })
      const dataResources = canvas.data_resources.filter((d) =>
        dataResourceIds.has(d.resource_id),
      )

      setSelectedNode({
        type: 'step',
        data: step,
        implementations,
        dataResources,
      })
      return
    }

    if (node.id.startsWith('impl:')) {
      const implId = node.id.slice('impl:'.length)
      const impl = canvas.implementations.find((i) => i.impl_id === implId)
      if (!impl) return

      const link = canvas.step_impl_links.find((l) => l.impl_id === implId)
      const step = link ? canvas.steps.find((s) => s.step_id === link.step_id) : undefined

      const dataResourceIds = canvas.impl_data_links
        .filter((l) => l.impl_id === implId)
        .map((l) => l.resource_id)
      const dataResources = canvas.data_resources.filter((d) =>
        dataResourceIds.includes(d.resource_id),
      )

      setSelectedNode({
        type: 'implementation',
        data: impl,
        dataResources,
        step,
      })
      return
    }

    if (node.id.startsWith('dr:')) {
      const resourceId = node.id.slice('dr:'.length)
      const dr = canvas.data_resources.find((d) => d.resource_id === resourceId)
      if (!dr) return

      const implIds = canvas.impl_data_links
        .filter((l) => l.resource_id === resourceId)
        .map((l) => l.impl_id)
      const implementations = canvas.implementations.filter((i) =>
        implIds.includes(i.impl_id),
      )

      const stepId = canvas.step_impl_links.find((l) =>
        implIds.includes(l.impl_id),
      )?.step_id
      const step = stepId ? canvas.steps.find((s) => s.step_id === stepId) : undefined

      setSelectedNode({
        type: 'data',
        data: dr,
        implementations,
        step,
      })
    }
  }

  const handleSaveCanvas = useCallback(async () => {
    if (!selectedProcessId || !canvas) return

    const edgesByKind = {
      process: [] as any[],
      stepImpl: [] as any[],
      implDr: [] as any[],
    }

    edges.forEach((edge) => {
      const kind = (edge.data as any)?.kind
      if (kind === 'process') {
        const fromStepId = edge.source.slice('step:'.length)
        const toStepId = edge.target.slice('step:'.length)
        edgesByKind.process.push({
          from_step_id: fromStepId,
          to_step_id: toStepId,
          from_handle: (edge as any).sourceHandle || null,
          to_handle: (edge as any).targetHandle || null,
          edge_type: (edge.data as any)?.edge_type,
          condition: (edge.data as any)?.condition,
          label: edge.label || (edge.data as any)?.label,
        })
      } else if (kind === 'step-impl') {
        const sourceIsStep = edge.source.startsWith('step:')
        const sourceIsImpl = edge.source.startsWith('impl:')

        const stepId = sourceIsStep
          ? edge.source.slice('step:'.length)
          : edge.target.slice('step:'.length)
        const implId = sourceIsImpl
          ? edge.source.slice('impl:'.length)
          : edge.target.slice('impl:'.length)

        const sourceHandle = (edge as any).sourceHandle || null
        const targetHandle = (edge as any).targetHandle || null

        const stepHandle = sourceIsStep ? sourceHandle : targetHandle
        const implHandle = sourceIsImpl ? sourceHandle : targetHandle

        edgesByKind.stepImpl.push({
          step_id: stepId,
          impl_id: implId,
          step_handle: stepHandle,
          impl_handle: implHandle,
        })
      } else if (kind === 'impl-dr') {
        const sourceIsImpl = edge.source.startsWith('impl:')
        const sourceIsDr = edge.source.startsWith('dr:')

        const implId = sourceIsImpl
          ? edge.source.slice('impl:'.length)
          : edge.target.slice('impl:'.length)
        const resourceId = sourceIsDr
          ? edge.source.slice('dr:'.length)
          : edge.target.slice('dr:'.length)

        const sourceHandle = (edge as any).sourceHandle || null
        const targetHandle = (edge as any).targetHandle || null

        const implHandle = sourceIsImpl ? sourceHandle : targetHandle
        const resourceHandle = sourceIsDr ? sourceHandle : targetHandle

        edgesByKind.implDr.push({
          impl_id: implId,
          resource_id: resourceId,
          impl_handle: implHandle,
          resource_handle: resourceHandle,
          access_type: (edge.data as any)?.access_type,
          access_pattern: (edge.data as any)?.access_pattern,
        })
      }
    })

    const payload: ProcessCanvas = {
      process: canvas.process,
      steps: canvas.steps,
      edges: edgesByKind.process,
      implementations: canvas.implementations,
      step_impl_links: edgesByKind.stepImpl,
      data_resources: canvas.data_resources,
      impl_data_links: edgesByKind.implDr,
    }

    setSaving(true)
    try {
      const saved = await saveProcessCanvas(selectedProcessId, payload)
      setCanvas(saved)
      setHasChanges(false)
    } finally {
      setSaving(false)
    }
  }, [selectedProcessId, canvas, edges])

  const handleCancelChanges = useCallback(() => {
    if (!hasChanges) return
    const ok = window.confirm('确认放弃所有更改？')
    if (!ok) return
    loadCanvas()
  }, [hasChanges, loadCanvas])

  const handleConnect = useCallback(
    (connection: Connection) => {
      const rawSource = connection.source || ''
      const rawTarget = connection.target || ''
      if (!rawSource || !rawTarget) return

      const sourceIsStep = rawSource.startsWith('step:')
      const sourceIsImpl = rawSource.startsWith('impl:')
      const sourceIsDr = rawSource.startsWith('dr:')
      const targetIsStep = rawTarget.startsWith('step:')
      const targetIsImpl = rawTarget.startsWith('impl:')
      const targetIsDr = rawTarget.startsWith('dr:')

      let newEdge: Edge | null = null

      if (sourceIsStep && targetIsStep) {
        newEdge = {
          id: `edge:process:${Date.now()}`,
          source: rawSource,
          target: rawTarget,
          sourceHandle: connection.sourceHandle || undefined,
          targetHandle: connection.targetHandle || undefined,
          type: 'simplebezier',
          markerEnd: { type: MarkerType.ArrowClosed },
          data: {
            kind: 'process',
            edge_type: undefined,
            condition: undefined,
            label: undefined,
          },
        }
      } else if (
        (sourceIsStep && targetIsImpl) ||
        (sourceIsImpl && targetIsStep)
      ) {
        newEdge = {
          id: `edge:step-impl:${Date.now()}`,
          source: rawSource,
          target: rawTarget,
          sourceHandle: connection.sourceHandle || undefined,
          targetHandle: connection.targetHandle || undefined,
          type: 'simplebezier',
          markerEnd: { type: MarkerType.ArrowClosed },
          style: { stroke: '#52c41a' },
          data: { kind: 'step-impl' },
        }
      } else if (
        (sourceIsImpl && targetIsDr) ||
        (sourceIsDr && targetIsImpl)
      ) {
        newEdge = {
          id: `edge:impl-dr:${Date.now()}`,
          source: rawSource,
          target: rawTarget,
          sourceHandle: connection.sourceHandle || undefined,
          targetHandle: connection.targetHandle || undefined,
          type: 'simplebezier',
          markerEnd: { type: MarkerType.ArrowClosed },
          style: { stroke: '#faad14' },
          data: { kind: 'impl-dr' },
        }
      }

      if (newEdge) {
        setEdges((prev) => [...prev, newEdge!])
        setHasChanges(true)
      }
    },
    [],
  )

  const handleReconnect = useCallback(
    (oldEdge: Edge, connection: Connection) => {
      const rawSource = connection.source || ''
      const rawTarget = connection.target || ''
      if (!rawSource || !rawTarget) return

      const kind = (oldEdge.data as any)?.kind
      if (!kind) return

      const sourceIsStep = rawSource.startsWith('step:')
      const sourceIsImpl = rawSource.startsWith('impl:')
      const sourceIsDr = rawSource.startsWith('dr:')
      const targetIsStep = rawTarget.startsWith('step:')
      const targetIsImpl = rawTarget.startsWith('impl:')
      const targetIsDr = rawTarget.startsWith('dr:')

      let valid = false
      if (kind === 'process' && sourceIsStep && targetIsStep) {
        valid = true
      } else if (
        kind === 'step-impl' &&
        ((sourceIsStep && targetIsImpl) || (sourceIsImpl && targetIsStep))
      ) {
        valid = true
      } else if (
        kind === 'impl-dr' &&
        ((sourceIsImpl && targetIsDr) || (sourceIsDr && targetIsImpl))
      ) {
        valid = true
      }

      if (!valid) return

      setEdges((prev) => reconnectEdge(oldEdge, connection, prev))
      setHasChanges(true)
    },
    [],
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
            <Space>
              {hasChanges && <Tag color="orange">未保存</Tag>}
              {currentProcess?.channel ? (
                <Tag color="geekblue">{currentProcess.channel}</Tag>
              ) : null}
              <Button
                type="primary"
                size="small"
                loading={saving}
                disabled={!hasChanges}
                onClick={handleSaveCanvas}
              >
                保存画布
              </Button>
              <Button
                size="small"
                disabled={!hasChanges}
                onClick={handleCancelChanges}
              >
                取消
              </Button>
            </Space>
          }
          style={{ height: '100%' }}
          bodyStyle={{ height: '100%' }}
        >
          {loadingCanvas ? (
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
                nodes={displayNodes}
                edges={displayEdges}
                fitView
                nodeTypes={nodeTypes}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={handleConnect}
                onReconnect={handleReconnect}
                onNodeClick={handleNodeClick}
                onPaneClick={() => {
                  setSelectedNode(null)
                  setHighlightNodeId(null)
                }}
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
                  <Text>{selectedNode.data.name}</Text>
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
                              <Text
                                type="secondary"
                                style={{
                                  fontSize: 12,
                                  wordBreak: 'break-all',
                                  overflowWrap: 'break-word',
                                }}
                              >
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
                    <Text
                      style={{
                        wordBreak: 'break-all',
                        overflowWrap: 'break-word',
                      }}
                    >
                      {selectedNode.data.code_ref}
                    </Text>
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
                              <Text
                                type="secondary"
                                style={{
                                  fontSize: 12,
                                  wordBreak: 'break-all',
                                  overflowWrap: 'break-word',
                                }}
                              >
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
          </div>
        )}
      </div>
    </div>
  )
}

export default BusinessLibraryPage

/**
 * Chat 工具函数
 * 包含消息解析、转换、分组等纯函数
 */

import {
  ToolSummaryInfo,
  DisplayMessage,
  RawHistoryMessage,
  ConversationSummary,
  ConversationGroup,
  ContentSegment,
  RenderItem,
  ActiveToolInfo,
  BatchToolItemInfo,
  ToolProgressStep,
} from '../types/chat'

/**
 * 根据工具名称生成输入摘要和输出摘要（与后端 _generate_tool_summaries 保持一致）
 */
export const generateToolSummary = (
  toolName: string, 
  toolInput: Record<string, unknown>, 
  toolOutput: string
): { input: string; output: string } => {
  let inputSummary = ''
  let outputSummary = ''
  
  // 尝试解析输出为 JSON
  let outputData: Record<string, unknown> | null = null
  try {
    outputData = JSON.parse(toolOutput)
  } catch {
    // 解析失败，保持 null
  }
  
  // ========== 搜索类工具 ==========
  if (['search_businesses', 'search_steps', 'search_implementations', 'search_data_resources'].includes(toolName)) {
    const query = String(toolInput.query || '')
    if (query) {
      inputSummary = `关键词: ${query}`
    }
    
    if (outputData) {
      if (Array.isArray(outputData.candidates)) {
        const count = outputData.candidates.length
        const total = typeof outputData.total_count === 'number' ? outputData.total_count : count
        if (count > 0) {
          outputSummary = `找到 ${count} 个结果` + (total > count ? ` (共 ${total} 个)` : '')
        } else {
          outputSummary = String(outputData.message || '未找到结果')
        }
      } else if (Array.isArray(outputData.results)) {
        const count = outputData.results.length
        outputSummary = count > 0 ? `找到 ${count} 个相关代码片段` : '未找到相关代码'
      } else if (outputData.error) {
        outputSummary = '查询失败'
      }
    }
  }
  
  // ========== 代码上下文搜索 ==========
  else if (toolName === 'search_code_context') {
    const workspace = String(toolInput.workspace || '')
    const query = String(toolInput.query || '')
    const parts: string[] = []
    if (workspace) {
      parts.push(`代码库: ${workspace}`)
    }
    if (query) {
      const displayQuery = query.length > 40 ? query.slice(0, 40) + '...' : query
      parts.push(`查询: ${displayQuery}`)
    }
    inputSummary = parts.join(' | ')
    
    if (outputData) {
      if (Array.isArray(outputData.content)) {
        const count = outputData.content.length
        outputSummary = count > 0 ? `找到 ${count} 个相关代码片段` : '未找到相关代码'
      } else if (outputData.error) {
        outputSummary = '查询失败'
      } else if (outputData.text) {
        outputSummary = '找到相关代码'
      } else {
        outputSummary = '执行完成'
      }
    }
  }
  
  // ========== 文件读取类工具 ==========
  else if (toolName === 'read_file') {
    const path = String(toolInput.path || '')
    if (path) {
      const filename = path.split('/').pop()?.split('\\').pop() || path
      inputSummary = `文件: ${filename}`
    }
    
    if (outputData) {
      if (typeof outputData.content === 'string') {
        const lines = outputData.content.split('\n').length
        outputSummary = `读取成功 (${lines} 行)`
      } else if (outputData.error) {
        outputSummary = '读取失败'
      }
    } else if (toolOutput && !toolOutput.startsWith('{')) {
      const lines = toolOutput.split('\n').length
      outputSummary = `读取成功 (${lines} 行)`
    }
  }
  
  else if (toolName === 'read_file_range') {
    const path = String(toolInput.path || '')
    const startLine = Number(toolInput.start_line || 0)
    const endLine = Number(toolInput.end_line || 0)
    if (path) {
      const filename = path.split('/').pop()?.split('\\').pop() || path
      inputSummary = `文件: ${filename} (L${startLine}-${endLine})`
    }
    
    if (toolOutput && !toolOutput.toLowerCase().includes('error')) {
      outputSummary = `读取成功 (${endLine - startLine + 1} 行)`
    } else {
      outputSummary = '读取失败'
    }
  }
  
  else if (toolName === 'list_directory') {
    const path = String(toolInput.path || '/')
    const depth = Number(toolInput.max_depth || 2)
    inputSummary = `目录: ${path}` + (depth !== 2 ? ` (深度 ${depth})` : '')
    
    if (outputData) {
      if (Array.isArray(outputData.entries)) {
        outputSummary = `列出 ${outputData.entries.length} 个条目`
      } else if (outputData.error) {
        outputSummary = '列出失败'
      }
    }
  }
  
  // ========== 上下文获取类工具 ==========
  else if (toolName === 'get_business_context') {
    const processIds = Array.isArray(toolInput.process_ids) ? toolInput.process_ids : []
    const count = processIds.length
    inputSummary = count > 1 ? `批量查询 ${count} 个业务` : `业务ID: ${String(processIds[0] || '').slice(0, 20)}`
    
    if (outputData?.results) {
      const total = typeof outputData.total === 'number' ? outputData.total : 0
      outputSummary = `获取 ${total} 个业务上下文`
    } else if (outputData?.error) {
      outputSummary = '获取失败'
    }
  }
  
  else if (toolName === 'get_implementation_context') {
    const implIds = Array.isArray(toolInput.impl_ids) ? toolInput.impl_ids : []
    const count = implIds.length
    inputSummary = count > 1 ? `批量查询 ${count} 个接口` : `接口ID: ${String(implIds[0] || '').slice(0, 20)}`
    
    if (outputData?.results) {
      const total = typeof outputData.total === 'number' ? outputData.total : 0
      outputSummary = `获取 ${total} 个接口上下文`
    } else if (outputData?.error) {
      outputSummary = '获取失败'
    }
  }
  
  else if (toolName === 'get_implementation_business_usages') {
    const implIds = Array.isArray(toolInput.impl_ids) ? toolInput.impl_ids : []
    const count = implIds.length
    inputSummary = count > 1 ? `批量查询 ${count} 个接口使用情况` : `接口ID: ${String(implIds[0] || '').slice(0, 20)}`
    
    if (outputData?.results) {
      const total = typeof outputData.total === 'number' ? outputData.total : 0
      outputSummary = `获取 ${total} 个接口的业务使用`
    } else if (outputData?.error) {
      outputSummary = '查询失败'
    }
  }
  
  else if (toolName === 'get_resource_context') {
    const resourceIds = Array.isArray(toolInput.resource_ids) ? toolInput.resource_ids : []
    const count = resourceIds.length
    inputSummary = count > 1 ? `批量查询 ${count} 个资源` : `资源ID: ${String(resourceIds[0] || '').slice(0, 20)}`
    
    if (outputData?.results) {
      const total = typeof outputData.total === 'number' ? outputData.total : 0
      outputSummary = `获取 ${total} 个资源上下文`
    } else if (outputData?.error) {
      outputSummary = '获取失败'
    }
  }
  
  else if (toolName === 'get_resource_business_usages') {
    const resourceIds = Array.isArray(toolInput.resource_ids) ? toolInput.resource_ids : []
    const count = resourceIds.length
    inputSummary = count > 1 ? `批量查询 ${count} 个资源使用情况` : `资源ID: ${String(resourceIds[0] || '').slice(0, 20)}`
    
    if (outputData?.results) {
      const total = typeof outputData.total === 'number' ? outputData.total : 0
      outputSummary = `获取 ${total} 个资源的业务使用`
    } else if (outputData?.error) {
      outputSummary = '查询失败'
    }
  }
  
  // ========== 图遍历类工具 ==========
  else if (toolName === 'get_neighbors') {
    const nodeIds = Array.isArray(toolInput.node_ids) ? toolInput.node_ids : []
    const depth = Number(toolInput.depth || 1)
    const count = nodeIds.length
    inputSummary = count > 1 ? `批量查询 ${count} 个节点邻居` : `节点: ${String(nodeIds[0] || '').slice(0, 20)}`
    if (depth > 1) {
      inputSummary += ` (深度 ${depth})`
    }
    
    if (outputData?.neighbors) {
      const neighborCount = Array.isArray(outputData.neighbors) ? outputData.neighbors.length : 0
      outputSummary = `找到 ${neighborCount} 个邻居节点`
    } else if (outputData?.error) {
      outputSummary = '查询失败'
    }
  }
  
  else if (toolName === 'get_path_between_entities') {
    inputSummary = '路径查询'
    
    if (outputData) {
      if (Array.isArray(outputData.path)) {
        outputSummary = `找到路径 (${outputData.path.length} 跳)`
      } else if (outputData.error || outputData.path === null) {
        outputSummary = '未找到路径'
      }
    }
  }
  
  // ========== 代码精确搜索 ==========
  else if (toolName === 'grep_code') {
    const pattern = String(toolInput.pattern || '')
    const workspace = String(toolInput.workspace || '')
    const filePattern = String(toolInput.file_pattern || '')
    
    const parts: string[] = []
    if (workspace) {
      parts.push(`代码库: ${workspace}`)
    }
    if (pattern) {
      const displayPattern = pattern.length > 30 ? pattern.slice(0, 30) + '...' : pattern
      parts.push(`搜索: ${displayPattern}`)
    }
    if (filePattern) {
      parts.push(`文件: ${filePattern}`)
    }
    inputSummary = parts.join(' | ')
    
    if (outputData) {
      if (Array.isArray(outputData.matches)) {
        const count = outputData.matches.length
        outputSummary = count > 0 ? `找到 ${count} 处匹配` : '未找到匹配'
      } else if (outputData.error) {
        outputSummary = '搜索失败'
      }
    }
  }
  
  // 默认处理
  if (!inputSummary && toolInput) {
    const firstKey = Object.keys(toolInput)[0]
    if (firstKey) {
      const firstVal = String(toolInput[firstKey])
      inputSummary = firstVal.length > 30 ? `${firstKey}: ${firstVal.slice(0, 30)}...` : `${firstKey}: ${firstVal}`
    }
  }
  
  if (!outputSummary) {
    if (outputData?.error) {
      outputSummary = '执行失败'
    } else if (toolOutput.length > 0) {
      outputSummary = '执行完成'
    } else {
      outputSummary = '无结果'
    }
  }
  
  return { input: inputSummary, output: outputSummary }
}

/**
 * 统一的消息转换函数：将后端原始消息转换为前端显示格式
 * 处理逻辑：
 * 1. 合并连续的assistant消息（模拟流式输出的累积效果）
 * 2. 在content中插入工具占位符（保持原始顺序）
 * 3. 生成toolSummaries（包含batch信息）
 */
export const convertRawMessagesToDisplay = (
  rawMessages: RawHistoryMessage[],
  threadId: string
): { 
  messages: DisplayMessage[], 
  toolSummaries: Map<string, ToolSummaryInfo> 
} => {
  const display: DisplayMessage[] = []
  const globalToolSummaries = new Map<string, ToolSummaryInfo>()
  
  let globalToolId = 0
  let globalBatchId = 0
  let accumulatedContent = ''
  let accumulatedToolCalls: { name: string; output_length: number }[] = []
  let accumulatedToolSummaries = new Map<string, ToolSummaryInfo>() // 当前消息的工具摘要
  let aiMessageStartIndex = -1

  const flushAIMessage = () => {
    if (aiMessageStartIndex === -1) return
    
    display.push({
      id: `assistant-${aiMessageStartIndex}-${threadId}`,
      role: 'assistant',
      content: accumulatedContent,
      toolCalls: accumulatedToolCalls.length > 0 ? accumulatedToolCalls : undefined,
      toolSummaries: accumulatedToolSummaries.size > 0 ? new Map(accumulatedToolSummaries) : undefined,
    })
    
    accumulatedContent = ''
    accumulatedToolCalls = []
    accumulatedToolSummaries = new Map()
    aiMessageStartIndex = -1
  }

  rawMessages.forEach((m, i) => {
    if (m.role === 'user') {
      flushAIMessage()
      
      display.push({
        id: `user-${i}-${threadId}`,
        role: 'user',
        content: m.content,
        attachments: m.attachments,  // 保留附件信息
      })
    } else if (m.role === 'assistant') {
      if (aiMessageStartIndex === -1) {
        aiMessageStartIndex = i
      }
      
      // 添加content
      if (m.content) {
        accumulatedContent += m.content
      }
      
      // 如果有工具调用，生成占位符并追加
      if (m.tool_calls && m.tool_calls.length > 0) {
        globalBatchId++
        const batchSize = m.tool_calls.length
        
        for (let idx = 0; idx < m.tool_calls.length; idx++) {
          const tc = m.tool_calls[idx]
          globalToolId++
          
          // 查找对应的 tool 返回消息
          let toolOutput = ''
          for (let j = i + 1; j < rawMessages.length; j++) {
            if (rawMessages[j].role === 'tool' && rawMessages[j].tool_name === tc.name) {
              toolOutput = rawMessages[j].content
              break
            }
          }
          
          // 使用与后端一致的摘要生成函数
          const { input: inputSummary, output: outputSummary } = generateToolSummary(
            tc.name,
            tc.args || {},
            toolOutput
          )
          
          const toolKey = `${tc.name}:${globalToolId}`
          const summaryInfo: ToolSummaryInfo = {
            input: inputSummary,
            output: outputSummary,
            batchId: batchSize > 1 ? globalBatchId : undefined,
            batchSize: batchSize > 1 ? batchSize : undefined,
            batchIndex: batchSize > 1 ? idx : undefined,
          }
          
          // 存入当前消息的摘要Map
          accumulatedToolSummaries.set(toolKey, summaryInfo)
          // 同时存入全局Map（保持向后兼容）
          globalToolSummaries.set(toolKey, summaryInfo)
          
          // 追加工具占位符（保持原始顺序）
          accumulatedContent += `<!--TOOL:${tc.name}:${globalToolId}-->`
          
          // 记录到toolCalls
          accumulatedToolCalls.push({
            name: tc.name,
            output_length: toolOutput.length,
          })
        }
      }
    }
    // tool消息跳过，已通过占位符展示
  })
  
  flushAIMessage()
  
  return { messages: display, toolSummaries: globalToolSummaries }
}

/**
 * 解析消息内容，分割为不同类型的段落
 */
export const parseContentSegments = (
  content: string, 
  currentToolName?: string,
  toolSummaries?: Map<string, {input: string, output: string}>
): ContentSegment[] => {
  const segments: ContentSegment[] = []
  const str = content || ''
  const len = str.length

  let i = 0
  let buffer = ''
  let bufferStart = 0
  let inThink = false
  let thinkStartPos = -1

  const flushTextBuffer = (endPos: number) => {
    if (!buffer) return
    const text = buffer.trim()
    if (text) {
      segments.push({
        type: 'text',
        content: text,
        startPos: bufferStart,
        endPos,
      })
    }
    buffer = ''
  }

  while (i < len) {
    // 工具占位符：无论是否在 think 块内，都将其视为一个硬边界
    if (str.startsWith('<!--TOOL:', i)) {
      // 如果当前在 think 中，先结束未闭合的 think 段
      // 遇到工具调用说明思考阶段已结束，标记为已完成（避免一直显示加载动画）
      if (inThink) {
        const raw = buffer
        const trimmed = raw.trim()
        if (trimmed) {
          segments.push({
            type: 'think',
            content: trimmed,
            startPos: thinkStartPos >= 0 ? thinkStartPos : bufferStart,
            endPos: i,
            isComplete: true,  // 工具调用开始 = 思考结束
          })
        }
        inThink = false
        buffer = ''
      } else {
        // 不在 think 中则先 flush 之前累积的正文
        flushTextBuffer(i)
      }

      const end = str.indexOf('-->', i)
      if (end === -1) {
        // 工具标签尚未完整输出，作为普通文本暂存，等待后续内容
        bufferStart = i
        buffer += str.slice(i)
        break
      }

      const markerStart = i
      const markerEnd = end + 3
      const inner = str.slice(i + '<!--TOOL:'.length, end)

      let toolName = ''
      let toolId = ''
      const firstColon = inner.indexOf(':')
      if (firstColon === -1) {
        toolName = inner.trim()
      } else {
        toolName = inner.slice(0, firstColon).trim()
        toolId = inner.slice(firstColon + 1).trim()
      }

      const toolIdNum = toolId ? parseInt(toolId, 10) : undefined
      const toolKey = toolName && toolId ? `${toolName}:${toolId}` : undefined
      const summary = toolKey ? toolSummaries?.get(toolKey) : undefined

      segments.push({
        type: 'tool',
        content: toolName,
        startPos: markerStart,
        endPos: markerEnd,
        isToolActive: false, // 稍后根据 currentToolName 单独标记
        inputSummary: summary?.input,
        outputSummary: summary?.output,
        toolId: toolIdNum,
      })

      i = markerEnd
      bufferStart = i
      buffer = ''
      continue
    }

    // 解析 <think> 开始标签
    if (!inThink && str.startsWith('<think>', i)) {
      // 先 flush 之前的正文
      flushTextBuffer(i)

      inThink = true
      thinkStartPos = i
      i += '<think>'.length
      bufferStart = i
      buffer = ''
      continue
    }

    // 解析 </think> 结束标签
    if (inThink && str.startsWith('</think>', i)) {
      const raw = buffer
      const trimmed = raw.trim()
      if (trimmed) {
        segments.push({
          type: 'think',
          content: trimmed,
          startPos: thinkStartPos,
          endPos: i + '</think>'.length,
          isComplete: true,
        })
      }

      inThink = false
      i += '</think>'.length
      bufferStart = i
      buffer = ''
      continue
    }

    // 普通字符累积到 buffer
    if (!buffer) {
      bufferStart = i
    }
    buffer += str[i]
    i += 1
  }

  // 处理剩余缓冲区内容
  if (buffer) {
    if (inThink) {
      const trimmed = buffer.trim()
      if (trimmed) {
        segments.push({
          type: 'think',
          content: trimmed,
          startPos: thinkStartPos >= 0 ? thinkStartPos : bufferStart,
          endPos: len,
          isComplete: false,
        })
      }
    } else {
      flushTextBuffer(len)
    }
  }

  // 第二遍：根据 currentToolName 标记当前正在执行的工具
  if (currentToolName) {
    let activeIndex = -1
    for (let idx = 0; idx < segments.length; idx++) {
      const seg = segments[idx]
      if (seg.type === 'tool' && seg.content === currentToolName) {
        const hasSummary = !!(seg.inputSummary || seg.outputSummary)
        if (!hasSummary) {
          activeIndex = idx
        }
      }
    }
    if (activeIndex !== -1) {
      segments[activeIndex].isToolActive = true
    }
  }

  return segments
}

/**
 * 构建交错渲染列表
 * 直接从 parseContentSegments 的结果构建，工具占位符已嵌入 content
 * 支持将同一批次的工具调用合并为 batch_tool 类型
 */
export const buildRenderItems = (
  content: string,
  currentToolName?: string,
  toolSummaries?: Map<string, ToolSummaryInfo>,
  activeTools?: Map<number, ActiveToolInfo>,  // toolId -> 活跃工具信息
  activeToolsRef?: React.MutableRefObject<Map<number, ActiveToolInfo>>,  // ref版本，用于同步获取最新值
  toolProgress?: Map<number, ToolProgressStep[]>  // 工具内部进度步骤
): RenderItem[] => {
  const segments = parseContentSegments(content, currentToolName, toolSummaries)
  
  const result: RenderItem[] = []
  let i = 0
  
  while (i < segments.length) {
    const seg = segments[i]
    
    if (seg.type === 'think') {
      result.push({
        type: 'think' as const,
        key: `think-${i}-${seg.startPos}`,
        thinkContent: seg.content,
        isThinkStreaming: !seg.isComplete,
        isThinkComplete: seg.isComplete
      })
      i++
    } else if (seg.type === 'tool') {
      // 获取该工具的批次信息（优先从ref获取，确保最新）
      const toolKey = seg.toolId ? `${seg.content}:${seg.toolId}` : undefined
      const summary = toolKey ? toolSummaries?.get(toolKey) : undefined
      const activeInfo = seg.toolId ? (activeToolsRef?.current.get(seg.toolId) || activeTools?.get(seg.toolId)) : undefined
      
      const batchId = summary?.batchId ?? activeInfo?.batchId
      const batchSize = summary?.batchSize ?? activeInfo?.batchSize ?? 1
      
      // 如果是批量调用（batchSize > 1），收集同一批次的所有工具
      if (batchSize > 1 && batchId !== undefined) {
        const batchTools: BatchToolItemInfo[] = []
        const batchStartIdx = i
        
        // 收集连续的同批次工具
        while (i < segments.length && segments[i].type === 'tool') {
          const toolSeg = segments[i]
          const tk = toolSeg.toolId ? `${toolSeg.content}:${toolSeg.toolId}` : undefined
          const ts = tk ? toolSummaries?.get(tk) : undefined
          const ai = toolSeg.toolId ? activeTools?.get(toolSeg.toolId) : undefined
          
          const thisBatchId = ts?.batchId ?? ai?.batchId
          
          // 如果不是同一批次，停止收集
          if (thisBatchId !== batchId) break
          
          // 判断是否活跃：activeTools 中存在则为活跃，或者 toolSummaries 中无 output 也视为活跃
          const isToolActive = ai !== undefined || (!!toolSeg.isToolActive && !ts?.output)
          
          batchTools.push({
            toolId: toolSeg.toolId || 0,
            name: toolSeg.content,
            isActive: isToolActive,
            inputSummary: ts?.input || toolSeg.inputSummary,
            outputSummary: ts?.output || toolSeg.outputSummary,
            elapsed: ts?.elapsed,
          })
          i++
        }
        
        result.push({
          type: 'batch_tool' as const,
          key: `batch-${batchId}-${batchStartIdx}`,
          batchId,
          batchTools,
        })
      } else {
        // 单个工具调用 - 使用与批量工具相同的活跃状态判断逻辑
        const singleToolActive = activeInfo !== undefined || (!!seg.isToolActive && !summary?.output)
        
        // 获取工具进度步骤
        const progressSteps = seg.toolId ? toolProgress?.get(seg.toolId) : undefined
        
        result.push({
          type: 'tool' as const,
          key: `tool-${i}-${seg.content}-${seg.toolId}`,
          toolName: seg.content,
          toolId: seg.toolId,
          toolIsActive: singleToolActive,
          toolInputSummary: summary?.input || seg.inputSummary,
          toolOutputSummary: summary?.output || seg.outputSummary,
          toolElapsed: summary?.elapsed,
          toolProgressSteps: progressSteps,
        })
        i++
      }
    } else {
      result.push({
        type: 'text' as const,
        key: `text-${i}-${seg.startPos}`,
        textContent: seg.content
      })
      i++
    }
  }
  
  return result
}

/**
 * 将对话按时间分组
 */
export const groupConversations = (conversations: ConversationSummary[]): ConversationGroup[] => {
  const groups: { [key: string]: ConversationSummary[] } = {
    '今天': [],
    '本周': [],
  }
  
  // 用于存储月份的动态键
  const monthGroups: { [key: string]: ConversationSummary[] } = {}
  const monthOrder: string[] = [] // 保持月份顺序

  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const weekStart = todayStart - 6 * 24 * 60 * 60 * 1000 // 简单定义：过去7天内但不是今天

  conversations.forEach(conv => {
    const d = new Date(conv.updatedAt)
    const t = d.getTime()

    if (t >= todayStart) {
      groups['今天'].push(conv)
    } else if (t >= weekStart) {
      groups['本周'].push(conv)
    } else {
      // 使用英文月份名，如 November, October
      const monthName = d.toLocaleString('en-US', { month: 'long' })
      if (!monthGroups[monthName]) {
        monthGroups[monthName] = []
        // 如果是新出现的月份，记录顺序（其实应该按时间排序，这里简化处理，假设输入已经是倒序的）
        if (!monthOrder.includes(monthName)) {
          monthOrder.push(monthName)
        }
      }
      monthGroups[monthName].push(conv)
    }
  })

  // 构建最终数组
  const result: ConversationGroup[] = []
  
  if (groups['今天'].length > 0) result.push({ label: '今天', conversations: groups['今天'] })
  if (groups['本周'].length > 0) result.push({ label: '本周', conversations: groups['本周'] })
  
  monthOrder.forEach(m => {
    if (monthGroups[m].length > 0) {
      result.push({ label: m, conversations: monthGroups[m] })
    }
  })

  return result
}

/**
 * Chat 模块类型定义
 */

import { FileAttachment, ToolCallInfo } from '../api/llm'

// 工具摘要信息（包含批次信息）
export interface ToolSummaryInfo {
  input: string
  output: string
  elapsed?: number    // 耗时（秒）
  batchId?: number    // 批次 ID
  batchSize?: number  // 批次大小
  batchIndex?: number // 批次内索引
}

export interface DisplayMessage {
  id: string
  role: 'user' | 'assistant' | 'phase_divider'  // 新增 phase_divider 类型
  content: string
  toolCalls?: ToolCallInfo[]
  isThinking?: boolean // 是否正在思考（等待工具返回）
  currentToolName?: string // 当前正在调用的工具名称
  toolSummaries?: Map<string, ToolSummaryInfo> // 该消息关联的工具摘要，key 为 "toolName:toolId"
  attachments?: FileAttachment[] // 用户消息的附件（图片、文档等）
  phaseName?: string // 阶段名称（仅 phase_divider）
  phaseIndex?: number // 阶段序号（仅 phase_divider）
}

// 后端返回的原始消息格式
export interface RawHistoryMessage {
  role: 'user' | 'assistant' | 'tool'
  content: string
  tool_calls?: Array<{ name: string; args?: Record<string, unknown> }>
  tool_name?: string
  attachments?: FileAttachment[]  // 用户消息的附件
}

export interface ConversationSummary {
  threadId: string
  title: string
  agentType?: string  // Agent 类型，用于恢复历史会话时切换 Agent
  updatedAt: string
}

// 历史记录分组接口
export interface ConversationGroup {
  label: string
  conversations: ConversationSummary[]
}

// 内容段落类型定义
// 工具占位符格式: <!--TOOL:toolName--> 或 <!--TOOL:toolName|inputSummary|outputSummary-->
export interface ContentSegment {
  type: 'think' | 'text' | 'tool'
  content: string  // think/text 的内容，或 tool 的名称
  startPos: number
  endPos: number
  isComplete?: boolean  // 仅 think 类型：标签是否已闭合
  isToolActive?: boolean  // 仅 tool 类型：是否正在执行
  inputSummary?: string   // 仅 tool 类型：输入摘要
  outputSummary?: string  // 仅 tool 类型：输出摘要
  toolId?: number         // 仅 tool 类型：工具占位符 ID
}

// 批量工具调用项信息
export interface BatchToolItemInfo {
  toolId: number
  name: string
  isActive: boolean
  inputSummary?: string
  outputSummary?: string
  elapsed?: number
}

// 工具内部进度步骤（如 LightRAG 的检索阶段）
export interface ToolProgressStep {
  phase: string    // 阶段名称，如 "local_query" | "global_query" | "rerank" | "finalize"
  detail: string   // 阶段详情，如 "40 实体, 100 关系"
  timestamp: number // 时间戳
}

// 活跃工具信息（包含批次信息）
export interface ActiveToolInfo {
  toolId: number
  batchId?: number
  batchSize?: number
  batchIndex?: number
}

// 渲染项类型：用于交错排列思考、工具、正文、批量工具
export interface RenderItem {
  type: 'think' | 'tool' | 'text' | 'batch_tool'
  key: string
  // think 类型
  thinkContent?: string
  isThinkStreaming?: boolean
  isThinkComplete?: boolean
  // tool 类型（单个工具）
  toolName?: string
  toolId?: number
  toolIsActive?: boolean
  toolInputSummary?: string
  toolOutputSummary?: string
  toolElapsed?: number
  toolProgressSteps?: ToolProgressStep[]  // 工具内部进度步骤
  // batch_tool 类型（批量工具）
  batchId?: number
  batchTools?: BatchToolItemInfo[]
  // text 类型
  textContent?: string
}

// Agent 欢迎配置
export interface AgentWelcomeConfig {
  icon: string
  title: string
  subtitle: string
  suggestions: string[]
}

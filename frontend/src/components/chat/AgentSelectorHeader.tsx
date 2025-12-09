/**
 * Agent 选择器头部组件
 * 包含 Agent 切换、日志查询配置、智能测试配置等
 */

import React from 'react'
import {
  DownOutlined,
  CheckCircleOutlined,
  SearchOutlined,
  LockOutlined,
} from '@ant-design/icons'
import { AgentType, LogQueryOption } from '../../api/llm'
import { IterationInfo, IssueInfo } from '../../api/coding'
import { TestingSessionStatus } from '../../api/llm'

interface AgentSelectorHeaderProps {
  // Agent 选择
  agentTypes: AgentType[]
  currentAgentType: string
  setCurrentAgentType: (type: string) => void
  isAgentDropdownOpen: boolean
  setIsAgentDropdownOpen: (open: boolean) => void
  hasConversationContent: boolean
  
  // 日志排查配置
  businessLines: LogQueryOption[]
  privateServers: LogQueryOption[]
  businessLine: string
  setBusinessLine: (value: string) => void
  privateServer: string | null
  setPrivateServer: (value: string | null) => void
  isBusinessLineOpen: boolean
  setIsBusinessLineOpen: (open: boolean) => void
  isPrivateServerOpen: boolean
  setIsPrivateServerOpen: (open: boolean) => void
  
  // 智能测试配置
  iterations: IterationInfo[]
  issues: IssueInfo[]
  selectedIteration: IterationInfo | null
  setSelectedIteration: (iteration: IterationInfo | null) => void
  selectedIssue: IssueInfo | null
  setSelectedIssue: (issue: IssueInfo | null) => void
  iterationSearchText: string
  setIterationSearchText: (text: string) => void
  issueSearchText: string
  setIssueSearchText: (text: string) => void
  isIterationLoading: boolean
  isIssueLoading: boolean
  isIterationOpen: boolean
  setIsIterationOpen: (open: boolean) => void
  isIssueOpen: boolean
  setIsIssueOpen: (open: boolean) => void
  onSearchIterations: () => void
  onSearchIssues: () => void
  testingSessionId: string | null
  testingSessionStatus: TestingSessionStatus | null
}

export const AgentSelectorHeader: React.FC<AgentSelectorHeaderProps> = ({
  agentTypes,
  currentAgentType,
  setCurrentAgentType,
  isAgentDropdownOpen,
  setIsAgentDropdownOpen,
  hasConversationContent,
  businessLines,
  privateServers,
  businessLine,
  setBusinessLine,
  privateServer,
  setPrivateServer,
  isBusinessLineOpen,
  setIsBusinessLineOpen,
  isPrivateServerOpen,
  setIsPrivateServerOpen,
  iterations,
  issues,
  selectedIteration,
  setSelectedIteration,
  selectedIssue,
  setSelectedIssue,
  iterationSearchText,
  setIterationSearchText,
  issueSearchText,
  setIssueSearchText,
  isIterationLoading,
  isIssueLoading,
  isIterationOpen,
  setIsIterationOpen,
  isIssueOpen,
  setIsIssueOpen,
  onSearchIterations,
  onSearchIssues,
  testingSessionId,
  testingSessionStatus,
}) => {
  const handleBusinessLineChange = (value: string) => {
    setBusinessLine(value)
    setIsBusinessLineOpen(false)
    if (value !== '私有化') {
      setPrivateServer(null)
    }
  }

  const handlePrivateServerChange = (value: string | null) => {
    setPrivateServer(value)
    setIsPrivateServerOpen(false)
  }

  if (agentTypes.length === 0) return null

  return (
    <div className="agent-selector-header">
      <div className="agent-dropdown-wrapper">
        {/* 有对话内容时显示锁定状态 */}
        {hasConversationContent ? (
          <div className="agent-locked-info">
            <LockOutlined className="locked-icon" />
            <span className="locked-value">
              {agentTypes.find(a => a.agent_type === currentAgentType)?.name || 'Agent'}
            </span>
          </div>
        ) : (
          <>
            <button 
              className="agent-dropdown-trigger"
              onClick={() => setIsAgentDropdownOpen(!isAgentDropdownOpen)}
            >
              <span className="agent-trigger-name">
                {agentTypes.find(a => a.agent_type === currentAgentType)?.name || 'Agent'}
              </span>
              <DownOutlined className={`agent-trigger-arrow ${isAgentDropdownOpen ? 'open' : ''}`} />
            </button>
            
            {isAgentDropdownOpen && (
              <div className="agent-dropdown-menu">
                {agentTypes.map(agent => {
                  const isSelected = currentAgentType === agent.agent_type
                  return (
                    <div
                      key={agent.agent_type}
                      className={`agent-dropdown-item ${isSelected ? 'selected' : ''}`}
                      onClick={() => {
                        setCurrentAgentType(agent.agent_type)
                        setIsAgentDropdownOpen(false)
                      }}
                    >
                      <div className="agent-item-content">
                        <span className="agent-item-name">{agent.name}</span>
                        <span className="agent-item-desc">{agent.description}</span>
                      </div>
                      {isSelected && <CheckCircleOutlined className="agent-item-check" />}
                    </div>
                  )
                })}
              </div>
            )}
          </>
        )}
      </div>
      
      {/* 日志排查配置选择器 - 仅 log_troubleshoot Agent 显示 */}
      {currentAgentType === 'log_troubleshoot' && businessLines.length > 0 && (
        <div className="log-query-selectors">
          {/* 有对话内容时显示锁定状态 */}
          {hasConversationContent ? (
            <div className="log-locked-info">
              <LockOutlined className="locked-icon" />
              <span className="locked-value">{businessLine}</span>
              {businessLine === '私有化' && privateServer && (
                <>
                  <span className="locked-separator">·</span>
                  <span className="locked-value">{privateServer}</span>
                </>
              )}
            </div>
          ) : (
            <>
              {/* 业务线选择器 */}
              <div className="log-dropdown-wrapper">
                <button
                  className="log-dropdown-trigger"
                  onClick={() => {
                    setIsBusinessLineOpen(!isBusinessLineOpen)
                    setIsPrivateServerOpen(false)
                  }}
                >
                  <span className="log-trigger-name">{businessLine || '选择业务线'}</span>
                  <DownOutlined className={`log-trigger-arrow ${isBusinessLineOpen ? 'open' : ''}`} />
                </button>
                {isBusinessLineOpen && (
                  <div className="log-dropdown-menu">
                    {businessLines.map(opt => (
                      <div
                        key={opt.value}
                        className={`log-dropdown-item ${businessLine === opt.value ? 'selected' : ''}`}
                        onClick={() => handleBusinessLineChange(opt.value)}
                      >
                        <span>{opt.label}</span>
                        {businessLine === opt.value && <CheckCircleOutlined className="log-item-check" />}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              
              {/* 私有化集团选择器 - 仅私有化业务线显示 */}
              {businessLine === '私有化' && privateServers.length > 0 && (
                <div className="log-dropdown-wrapper">
                  <button
                    className="log-dropdown-trigger"
                    onClick={() => {
                      setIsPrivateServerOpen(!isPrivateServerOpen)
                      setIsBusinessLineOpen(false)
                    }}
                  >
                    <span className="log-trigger-name">{privateServer || '选择集团'}</span>
                    <DownOutlined className={`log-trigger-arrow ${isPrivateServerOpen ? 'open' : ''}`} />
                  </button>
                  {isPrivateServerOpen && (
                    <div className="log-dropdown-menu">
                      {privateServers.map(opt => (
                        <div
                          key={opt.value}
                          className={`log-dropdown-item ${privateServer === opt.value ? 'selected' : ''}`}
                          onClick={() => handlePrivateServerChange(opt.value)}
                        >
                          <span>{opt.label}</span>
                          {privateServer === opt.value && <CheckCircleOutlined className="log-item-check" />}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}
      
      {/* 智能测试配置选择器 - 仅 intelligent_testing Agent 显示 */}
      {currentAgentType === 'intelligent_testing' && (
        <div className="log-query-selectors">
          {/* 有 sessionId 时显示锁定的需求信息 */}
          {testingSessionId && testingSessionStatus ? (
            <div className="testing-locked-info">
              <LockOutlined className="locked-icon" />
              <span className="locked-value">
                {testingSessionStatus.requirement_name || `#${testingSessionStatus.requirement_id}`}
              </span>
              <span className="locked-badge">已锁定</span>
            </div>
          ) : (
            <>
              {/* 迭代选择器 */}
              <div className="testing-dropdown-wrapper log-dropdown-wrapper">
                <button
                  className="log-dropdown-trigger"
                  onClick={() => {
                    setIsIterationOpen(!isIterationOpen)
                    setIsIssueOpen(false)
                  }}
                >
                  <span className="log-trigger-name">
                    {selectedIteration ? selectedIteration.name : (isIterationLoading ? '加载中...' : '选择迭代')}
                  </span>
                  <DownOutlined className={`log-trigger-arrow ${isIterationOpen ? 'open' : ''}`} />
                </button>
                {isIterationOpen && (
                  <div className="log-dropdown-menu" style={{ maxHeight: '300px', overflowY: 'auto', overflowX: 'hidden' }}>
                    {/* 搜索框 + 搜索按钮 */}
                    <div style={{ padding: '8px', borderBottom: '1px solid #f0f0f0', display: 'flex', gap: '6px' }}>
                      <input
                        type="text"
                        placeholder="输入关键词搜索..."
                        value={iterationSearchText}
                        onChange={(e) => setIterationSearchText(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') onSearchIterations() }}
                        onClick={(e) => e.stopPropagation()}
                        style={{
                          flex: 1,
                          padding: '6px 10px',
                          border: '1px solid #d9d9d9',
                          borderRadius: '6px',
                          fontSize: '13px',
                          outline: 'none',
                        }}
                      />
                      <button
                        onClick={(e) => { e.stopPropagation(); onSearchIterations() }}
                        disabled={isIterationLoading}
                        style={{
                          padding: '6px 12px',
                          border: '1px solid #1890ff',
                          borderRadius: '6px',
                          background: '#1890ff',
                          color: '#fff',
                          cursor: isIterationLoading ? 'not-allowed' : 'pointer',
                          fontSize: '13px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                        }}
                      >
                        <SearchOutlined />
                      </button>
                    </div>
                    {isIterationLoading && (
                      <div style={{ padding: '12px', color: '#999', textAlign: 'center' }}>搜索中...</div>
                    )}
                    {!isIterationLoading && iterations.map(iteration => (
                      <div
                        key={iteration.code}
                        className={`log-dropdown-item ${selectedIteration?.code === iteration.code ? 'selected' : ''}`}
                        onClick={() => {
                          setSelectedIteration(iteration)
                          setIsIterationOpen(false)
                          setIterationSearchText('')
                        }}
                      >
                        <span>{iteration.name}</span>
                        {selectedIteration?.code === iteration.code && <CheckCircleOutlined className="log-item-check" />}
                      </div>
                    ))}
                    {!isIterationLoading && iterations.length === 0 && (
                      <div style={{ padding: '12px', color: '#999', textAlign: 'center' }}>暂无匹配迭代</div>
                    )}
                  </div>
                )}
              </div>
              
              {/* 需求选择器 - 仅选择迭代后显示 */}
              {selectedIteration && (
                <div className="testing-dropdown-wrapper log-dropdown-wrapper">
                  <button
                    className="log-dropdown-trigger"
                    onClick={() => {
                      setIsIssueOpen(!isIssueOpen)
                      setIsIterationOpen(false)
                    }}
                  >
                    <span className="log-trigger-name">
                      {selectedIssue ? `#${selectedIssue.code} ${selectedIssue.name}`.slice(0, 30) + (selectedIssue.name.length > 20 ? '...' : '') : (isIssueLoading ? '加载中...' : '选择需求')}
                    </span>
                    <DownOutlined className={`log-trigger-arrow ${isIssueOpen ? 'open' : ''}`} />
                  </button>
                  {isIssueOpen && (
                    <div className="log-dropdown-menu" style={{ maxHeight: '300px', overflow: 'auto', minWidth: '350px' }}>
                      {/* 搜索框 + 搜索按钮 */}
                      <div style={{ padding: '8px', borderBottom: '1px solid #f0f0f0', display: 'flex', gap: '6px' }}>
                        <input
                          type="text"
                          placeholder="输入关键词搜索..."
                          value={issueSearchText}
                          onChange={(e) => setIssueSearchText(e.target.value)}
                          onKeyDown={(e) => { if (e.key === 'Enter') onSearchIssues() }}
                          onClick={(e) => e.stopPropagation()}
                          style={{
                            flex: 1,
                            padding: '6px 10px',
                            border: '1px solid #d9d9d9',
                            borderRadius: '6px',
                            fontSize: '13px',
                            outline: 'none',
                          }}
                        />
                        <button
                          onClick={(e) => { e.stopPropagation(); onSearchIssues() }}
                          disabled={isIssueLoading}
                          style={{
                            padding: '6px 12px',
                            border: '1px solid #1890ff',
                            borderRadius: '6px',
                            background: '#1890ff',
                            color: '#fff',
                            cursor: isIssueLoading ? 'not-allowed' : 'pointer',
                            fontSize: '13px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                          }}
                        >
                          <SearchOutlined />
                        </button>
                      </div>
                      {isIssueLoading && (
                        <div style={{ padding: '12px', color: '#999', textAlign: 'center' }}>搜索中...</div>
                      )}
                      {!isIssueLoading && issues.map(issue => (
                        <div
                          key={issue.code}
                          className={`log-dropdown-item ${selectedIssue?.code === issue.code ? 'selected' : ''}`}
                          onClick={() => {
                            setSelectedIssue(issue)
                            setIsIssueOpen(false)
                            setIssueSearchText('')
                          }}
                          style={{ flexDirection: 'column', alignItems: 'flex-start' }}
                        >
                          <span style={{ fontWeight: 500 }}>#{issue.code} {issue.name}</span>
                          <span style={{ fontSize: '12px', color: '#999', marginTop: '2px' }}>
                            {issue.status_name} · {issue.assignee_names.join(', ') || '未指派'}
                          </span>
                          {selectedIssue?.code === issue.code && (
                            <CheckCircleOutlined className="log-item-check" style={{ position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)' }} />
                          )}
                        </div>
                      ))}
                      {!isIssueLoading && issues.length === 0 && (
                        <div style={{ padding: '12px', color: '#999', textAlign: 'center' }}>暂无匹配需求</div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default AgentSelectorHeader

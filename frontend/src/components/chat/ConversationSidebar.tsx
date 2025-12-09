/**
 * 会话历史侧边栏组件
 */

import React from 'react'
import {
  EditOutlined,
  DeleteOutlined,
  HistoryOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  LoadingOutlined,
} from '@ant-design/icons'
import { ConversationSummary, ConversationGroup } from '../../types/chat'

interface ConversationSidebarProps {
  isSidebarCollapsed: boolean
  setIsSidebarCollapsed: (collapsed: boolean) => void
  isConversationsLoading: boolean
  conversations: ConversationSummary[]
  groupedConversations: ConversationGroup[]
  activeConversationId: string | null
  isHistoryLoading: boolean
  onNewChat: () => void
  onSelectConversation: (conv: ConversationSummary) => void
  onDeleteConversation: (e: React.MouseEvent, conv: ConversationSummary) => void
}

export const ConversationSidebar: React.FC<ConversationSidebarProps> = ({
  isSidebarCollapsed,
  setIsSidebarCollapsed,
  isConversationsLoading,
  conversations,
  groupedConversations,
  activeConversationId,
  isHistoryLoading,
  onNewChat,
  onSelectConversation,
  onDeleteConversation,
}) => {
  return (
    <div className={`chat-sidebar ${isSidebarCollapsed ? 'collapsed' : ''}`}>
      {/* 导航菜单 */}
      <div className="sidebar-menu">
        <div 
          className="menu-item active"
          onClick={onNewChat}
          title="新建聊天"
        >
          <EditOutlined className="menu-icon" />
          {!isSidebarCollapsed && <span className="menu-text">新建聊天</span>}
        </div>
      </div>

      {/* 历史记录列表 */}
      <div className="conversation-history-container">
        {isSidebarCollapsed ? (
          <div 
            className="menu-item" 
            onClick={() => setIsSidebarCollapsed(false)}
            title="查看历史记录"
          >
            <HistoryOutlined className="menu-icon" />
          </div>
        ) : (
          <>
            <div className="history-header">
              <HistoryOutlined className="history-icon" />
              <span className="history-title">历史记录</span>
            </div>
            
            <div className="conversation-list">
              {isConversationsLoading ? (
                <div className="conversation-list-loading">
                  <LoadingOutlined spin />
                  <span>加载中...</span>
                </div>
              ) : conversations.length === 0 ? (
                <div className="conversation-list-empty">暂无历史</div>
              ) : (
                groupedConversations.map(group => (
                  <div key={group.label} className="history-group">
                    <div className="history-group-label">{group.label}</div>
                    {group.conversations.map(conv => (
                      <div
                        key={conv.threadId}
                        className={`conversation-item ${conv.threadId === activeConversationId ? 'active' : ''} ${isHistoryLoading && conv.threadId === activeConversationId ? 'loading' : ''}`}
                        onClick={() => onSelectConversation(conv)}
                        title={conv.title || '新对话'}
                      >
                        <div className="conversation-item-title">{conv.title || '新对话'}</div>
                        {isHistoryLoading && conv.threadId === activeConversationId ? (
                          <LoadingOutlined spin className="conversation-item-loading" />
                        ) : (
                          <div 
                             className="conversation-item-delete"
                             onClick={(e) => onDeleteConversation(e, conv)}
                             title="删除对话"
                          >
                             <DeleteOutlined />
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ))
              )}
              
              {!isConversationsLoading && conversations.length > 0 && (
                 <div className="view-all-history">查看全部</div>
              )}
            </div>
          </>
        )}
      </div>
      
      {/* 底部折叠按钮 */}
      <div className="sidebar-footer">
        <div 
          className="sidebar-collapse-btn" 
          onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
          title={isSidebarCollapsed ? "展开侧边栏" : "收起侧边栏"}
        >
          {isSidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
        </div>
      </div>
    </div>
  )
}

export default ConversationSidebar

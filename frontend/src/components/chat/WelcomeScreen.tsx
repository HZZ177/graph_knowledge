/**
 * 欢迎屏幕组件（动态适配 Agent）
 */

import React from 'react'
import { AgentWelcomeConfig } from '../../types/chat'

// Agent 配置
export const agentWelcomeConfig: Record<string, AgentWelcomeConfig> = {
  knowledge_qa: {
    icon: '🤖',
    title: '业务知识助手',
    subtitle: '探索业务流程、接口实现和数据资源，基于实时图谱提供准确洞察',
    suggestions: [
      'C端封闭的开卡流程是怎样的？',
      '订单相关的接口有哪些？',
      '用户表被哪些服务使用？',
      '微信公众号登录时的校验逻辑是怎么走的？',
    ]
  },
  log_troubleshoot: {
    icon: '🔍',
    title: '日志排查助手',
    subtitle: '智能分析业务日志，快速定位问题根因，提供排查建议',
    suggestions: [
      '最近有哪些错误日志？',
      '支付接口的超时问题如何排查？',
      '用户登录失败的常见原因有哪些？',
      '数据库连接异常如何定位？',
    ]
  },
  code_review: {
    icon: '📝',
    title: '代码审查助手',
    subtitle: '分析代码质量，发现潜在问题，提供优化建议',
    suggestions: [
      '这段代码有什么潜在问题？',
      '如何优化这个函数的性能？',
      '代码中是否存在安全隐患？',
      '有没有更优雅的实现方式？',
    ]
  },
  intelligent_testing: {
    icon: '🧪',
    title: '需求分析测试助手',
    subtitle: '基于需求文档智能生成测试方案和测试用例',
    suggestions: [
      '分析这个需求的测试点',
      '生成功能测试用例',
      '设计边界值测试场景',
      '识别潜在的异常场景',
    ]
  }
}

interface WelcomeScreenProps {
  onSuggestionClick: (q: string) => void
  agentType: string
  businessLine?: string
  privateServer?: string | null
}

export const WelcomeScreen: React.FC<WelcomeScreenProps> = ({ 
  onSuggestionClick, 
  agentType, 
  businessLine, 
  privateServer 
}) => {
  const config = agentWelcomeConfig[agentType] || agentWelcomeConfig.knowledge_qa

  return (
    <div className="welcome-screen">
      <h1 className="welcome-title">{config.title}</h1>
      
      {/* 日志排查助手显示当前配置 */}
      {agentType === 'log_troubleshoot' && businessLine && (
        <div className="welcome-config">
          <span className="welcome-config-label">当前业务线：</span>
          <span className="welcome-config-value">{businessLine}</span>
          {businessLine === '私有化' && privateServer && (
            <>
              <span className="welcome-config-separator">·</span>
              <span className="welcome-config-label">私有化集团：</span>
              <span className="welcome-config-value">{privateServer}</span>
            </>
          )}
        </div>
      )}
      
      <p className="welcome-subtitle">{config.subtitle}</p>
    </div>
  )
}

export default WelcomeScreen

import React from 'react'
import { notification } from 'antd'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  DatabaseOutlined,
  CloudServerOutlined,
} from '@ant-design/icons'

interface SyncResult {
  success: boolean
  message: string
  synced_at?: string
  error_type?: string
  stats?: {
    steps: number
    implementations: number
    data_resources: number
  }
}

/**
 * 显示同步进度通知
 */
export const showSyncProgress = (processName: string) => {
  notification.open({
    key: 'sync-progress',
    message: '正在同步到Neo4j',
    description: (
      <div>
        <p style={{ marginBottom: 8 }}>
          <DatabaseOutlined style={{ marginRight: 8, color: '#1890ff' }} />
          <strong>{processName}</strong> 已保存到SQLite
        </p>
        <p style={{ marginBottom: 0 }}>
          <SyncOutlined spin style={{ marginRight: 8, color: '#1890ff' }} />
          正在同步到Neo4j图数据库...
        </p>
      </div>
    ),
    icon: <SyncOutlined spin style={{ color: '#1890ff' }} />,
    duration: 0, // 不自动关闭
    placement: 'topRight',
  })
}

/**
 * 显示同步成功通知
 */
export const showSyncSuccess = (processName: string, result: SyncResult) => {
  notification.success({
    key: 'sync-progress',
    message: '同步成功！',
    description: (
      <div>
        <p style={{ marginBottom: 8 }}>
          <DatabaseOutlined style={{ marginRight: 8, color: '#52c41a' }} />
          <strong>{processName}</strong> 已保存到SQLite
        </p>
        <p style={{ marginBottom: 8 }}>
          <CloudServerOutlined style={{ marginRight: 8, color: '#52c41a' }} />
          已同步到Neo4j图数据库
        </p>
        {result.stats && (
          <div style={{ 
            padding: '8px 12px', 
            background: '#f6ffed', 
            borderRadius: 4,
            fontSize: 12,
            color: '#52c41a'
          }}>
            <div>✓ 同步 {result.stats.steps} 个步骤</div>
            <div>✓ 同步 {result.stats.implementations} 个实现</div>
            <div>✓ 同步 {result.stats.data_resources} 个数据资源</div>
          </div>
        )}
      </div>
    ),
    icon: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
    duration: 4,
    placement: 'topRight',
  })
}

/**
 * 显示同步失败通知
 */
export const showSyncError = (processName: string, result: SyncResult) => {
  const getErrorTip = (errorType?: string) => {
    switch (errorType) {
      case 'connection_error':
        return '💡 请检查Neo4j服务是否正常运行'
      case 'auth_error':
        return '💡 请检查Neo4j认证信息是否正确'
      case 'query_error':
        return '💡 请检查数据格式是否正确'
      default:
        return '💡 请查看详细错误信息或联系管理员'
    }
  }

  notification.warning({
    key: 'sync-progress',
    message: 'SQLite保存成功，但Neo4j同步失败',
    description: (
      <div>
        <p style={{ marginBottom: 8 }}>
          <DatabaseOutlined style={{ marginRight: 8, color: '#52c41a' }} />
          <strong>{processName}</strong> 已保存到SQLite ✓
        </p>
        <p style={{ marginBottom: 8 }}>
          <CloseCircleOutlined style={{ marginRight: 8, color: '#ff4d4f' }} />
          Neo4j同步失败
        </p>
        <div style={{ 
          padding: '8px 12px', 
          background: '#fff7e6', 
          borderRadius: 4,
          fontSize: 12,
          marginBottom: 8
        }}>
          <div style={{ color: '#d46b08', marginBottom: 4 }}>
            <strong>错误原因：</strong>{result.message}
          </div>
          <div style={{ color: '#8c8c8c' }}>
            {getErrorTip(result.error_type)}
          </div>
        </div>
        <div style={{ fontSize: 12, color: '#8c8c8c' }}>
          ℹ️ 数据已安全保存到SQLite，稍后可重新保存以触发同步
        </div>
      </div>
    ),
    icon: <CloseCircleOutlined style={{ color: '#faad14' }} />,
    duration: 8,
    placement: 'topRight',
  })
}

/**
 * 关闭同步通知
 */
export const closeSyncNotification = () => {
  notification.destroy('sync-progress')
}

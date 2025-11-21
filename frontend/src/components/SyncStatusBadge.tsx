import React from 'react'
import { Badge, Tooltip } from 'antd'
import {
  CheckCircleOutlined,
  SyncOutlined,
  CloseCircleOutlined,
  MinusCircleOutlined,
} from '@ant-design/icons'

export type SyncStatus = 'never_synced' | 'syncing' | 'synced' | 'failed'

interface SyncStatusBadgeProps {
  status: SyncStatus
  lastSyncAt?: string | null
  syncError?: string | null
  showText?: boolean
  size?: 'small' | 'default'
}

const SyncStatusBadge: React.FC<SyncStatusBadgeProps> = ({
  status,
  lastSyncAt,
  syncError,
  showText = true,
  size = 'default',
}) => {
  const statusConfig = {
    synced: {
      status: 'success' as const,
      text: '已同步',
      icon: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
      color: '#52c41a',
    },
    syncing: {
      status: 'processing' as const,
      text: '同步中',
      icon: <SyncOutlined spin style={{ color: '#1890ff' }} />,
      color: '#1890ff',
    },
    failed: {
      status: 'error' as const,
      text: '同步失败',
      icon: <CloseCircleOutlined style={{ color: '#ff4d4f' }} />,
      color: '#ff4d4f',
    },
    never_synced: {
      status: 'default' as const,
      text: '未同步',
      icon: <MinusCircleOutlined style={{ color: '#d9d9d9' }} />,
      color: '#d9d9d9',
    },
  }

  const config = statusConfig[status] || statusConfig.never_synced

  // 构建提示信息
  let tooltipTitle = config.text
  if (lastSyncAt) {
    const syncTime = new Date(lastSyncAt).toLocaleString('zh-CN')
    tooltipTitle += `\n最后同步: ${syncTime}`
  }
  if (syncError) {
    tooltipTitle += `\n错误: ${syncError}`
  }

  if (showText) {
    return (
      <Tooltip title={tooltipTitle} placement="top">
        <Badge
          status={config.status}
          text={
            <span style={{ fontSize: size === 'small' ? '12px' : '14px' }}>
              {config.text}
            </span>
          }
        />
      </Tooltip>
    )
  }

  return (
    <Tooltip title={tooltipTitle} placement="top">
      <span style={{ fontSize: size === 'small' ? '16px' : '18px' }}>
        {config.icon}
      </span>
    </Tooltip>
  )
}

export default SyncStatusBadge

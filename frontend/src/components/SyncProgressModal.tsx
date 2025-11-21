import React, { useState, useEffect } from 'react'
import { Modal, Progress, Result, Descriptions, Space, Typography, Spin } from 'antd'

const { Text } = Typography

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

interface SyncProgressModalProps {
  visible: boolean
  processName: string
  status: 'saving' | 'syncing' | 'success' | 'error'
  result?: SyncResult
  onClose: () => void
}

const SyncProgressModal: React.FC<SyncProgressModalProps> = ({
  visible,
  processName,
  status,
  result,
  onClose,
}) => {
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    if (status === 'saving') {
      setProgress(30)
    } else if (status === 'syncing') {
      setProgress(60)
    } else if (status === 'success' || status === 'error') {
      setProgress(100)
    }
  }, [status])

  const getTitle = () => {
    switch (status) {
      case 'saving':
        return '正在保存到SQLite'
      case 'syncing':
        return '正在同步到Neo4j'
      case 'success':
        return '保存并同步成功'
      case 'error':
        return '保存成功，同步失败'
      default:
        return '处理中'
    }
  }


  const getErrorTip = (errorType?: string) => {
    switch (errorType) {
      case 'connection_error':
        return '请检查Neo4j服务是否正常运行'
      case 'auth_error':
        return '请检查Neo4j认证信息是否正确'
      case 'query_error':
        return '请检查数据格式是否正确'
      default:
        return '请查看详细错误信息或联系管理员'
    }
  }

  const renderContent = () => {
    if (status === 'saving' || status === 'syncing') {
      return (
        <div style={{ textAlign: 'center', padding: '40px 20px' }}>
          <div style={{ marginBottom: 32 }}>
            <Spin size="large" />
          </div>
          
          <Progress
            percent={progress}
            status="active"
            strokeColor={{
              '0%': '#108ee9',
              '100%': '#87d068',
            }}
            style={{ marginBottom: 24 }}
          />

          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <div>
              <Text strong style={{ fontSize: 16, color: status === 'saving' ? '#1890ff' : '#52c41a' }}>
                {status === 'saving' ? '正在保存到SQLite' : 'SQLite保存完成'}
              </Text>
            </div>

            <div>
              <Text strong style={{ fontSize: 16, color: status === 'syncing' ? '#1890ff' : '#d9d9d9' }}>
                {status === 'syncing' ? '正在同步到Neo4j' : '等待同步到Neo4j'}
              </Text>
            </div>
          </Space>

          <div style={{ marginTop: 24, color: '#8c8c8c', fontSize: 14 }}>
            流程：<Text strong>{processName}</Text>
          </div>
        </div>
      )
    }

    if (status === 'success' && result) {
      return (
        <Result
          status="success"
          title="保存并同步成功"
          subTitle={
            <Space direction="vertical" size={8} style={{ marginTop: 16 }}>
              <div>
                <Text>流程 <Text strong>{processName}</Text> 已保存到SQLite</Text>
              </div>
              <div>
                <Text>已成功同步到Neo4j图数据库</Text>
              </div>
            </Space>
          }
          extra={
            result.stats && (
              <Descriptions
                bordered
                size="small"
                column={1}
                style={{ marginTop: 24, textAlign: 'left' }}
              >
                <Descriptions.Item label="同步步骤数">
                  <Text strong style={{ color: '#52c41a' }}>
                    {result.stats.steps} 个
                  </Text>
                </Descriptions.Item>
                <Descriptions.Item label="同步实现数">
                  <Text strong style={{ color: '#52c41a' }}>
                    {result.stats.implementations} 个
                  </Text>
                </Descriptions.Item>
                <Descriptions.Item label="同步数据资源数">
                  <Text strong style={{ color: '#52c41a' }}>
                    {result.stats.data_resources} 个
                  </Text>
                </Descriptions.Item>
                {result.synced_at && (
                  <Descriptions.Item label="同步时间">
                    {new Date(result.synced_at).toLocaleString('zh-CN')}
                  </Descriptions.Item>
                )}
              </Descriptions>
            )
          }
        />
      )
    }

    if (status === 'error' && result) {
      return (
        <Result
          status="warning"
          title="SQLite保存成功，但Neo4j同步失败"
          subTitle={
            <Space direction="vertical" size={8} style={{ marginTop: 16 }}>
              <div>
                <Text>流程 <Text strong>{processName}</Text> 已保存到SQLite</Text>
              </div>
              <div>
                <Text type="danger">Neo4j同步失败</Text>
              </div>
            </Space>
          }
          extra={
            <div style={{ textAlign: 'left' }}>
              <div
                style={{
                  padding: '16px',
                  background: '#fff7e6',
                  borderRadius: 8,
                  border: '1px solid #ffd591',
                  marginBottom: 16,
                }}
              >
                <div style={{ marginBottom: 8 }}>
                  <Text strong style={{ color: '#d46b08' }}>错误原因：</Text>
                  <Text style={{ color: '#d46b08' }}>{result.message}</Text>
                </div>
                <div>
                  <Text type="secondary">{getErrorTip(result.error_type)}</Text>
                </div>
              </div>

              <div
                style={{
                  padding: '12px',
                  background: '#f0f5ff',
                  borderRadius: 8,
                  border: '1px solid #adc6ff',
                }}
              >
                <Text type="secondary">
                  数据已安全保存到SQLite，稍后可重新保存以触发同步
                </Text>
              </div>
            </div>
          }
        />
      )
    }

    return null
  }

  return (
    <Modal
      title={getTitle()}
      open={visible}
      onCancel={onClose}
      footer={status === 'success' || status === 'error' ? [
        <button
          key="close"
          onClick={onClose}
          style={{
            padding: '8px 24px',
            fontSize: 14,
            borderRadius: 6,
            border: 'none',
            background: status === 'success' ? '#52c41a' : '#1890ff',
            color: '#fff',
            cursor: 'pointer',
            fontWeight: 500,
          }}
        >
          {status === 'success' ? '完成' : '我知道了'}
        </button>
      ] : null}
      closable={status === 'success' || status === 'error'}
      maskClosable={false}
      width={560}
      centered
    >
      {renderContent()}
    </Modal>
  )
}

export default SyncProgressModal

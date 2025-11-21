import React, { useState } from 'react'
import { Modal, Button, Space, Alert, Descriptions, Spin, Result } from 'antd'
import {
  SyncOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons'
import { publishProcess } from '../api/processes'

interface PublishProcessModalProps {
  processId: string
  processName: string
  visible: boolean
  onClose: () => void
  onSuccess?: () => void
}

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

const PublishProcessModal: React.FC<PublishProcessModalProps> = ({
  processId,
  processName,
  visible,
  onClose,
  onSuccess,
}) => {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<SyncResult | null>(null)

  const handlePublish = async () => {
    setLoading(true)
    setResult(null)

    try {
      const response = await publishProcess(processId)
      setResult(response)

      if (response.success && onSuccess) {
        setTimeout(() => {
          onSuccess()
        }, 1500)
      }
    } catch (error: any) {
      setResult({
        success: false,
        message: error.response?.data?.detail || '发布失败，请稍后重试',
        error_type: 'request_error',
      })
    } finally {
      setLoading(false)
    }
  }

  const handleClose = () => {
    setResult(null)
    onClose()
  }

  return (
    <Modal
      title="发布流程到Neo4j"
      open={visible}
      onCancel={handleClose}
      footer={null}
      width={600}
    >
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        <Alert
          message="发布说明"
          description={
            <>
              <p>将流程 <strong>{processName}</strong> 同步到Neo4j图数据库。</p>
              <p>此操作会：</p>
              <ul style={{ marginBottom: 0, paddingLeft: 20 }}>
                <li>清理Neo4j中该流程的旧数据</li>
                <li>同步所有步骤、实现和数据资源节点</li>
                <li>建立节点之间的关系</li>
              </ul>
            </>
          }
          type="info"
          showIcon
        />

        {loading && (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Spin size="large" />
            <p style={{ marginTop: 16, color: '#666' }}>
              正在同步到Neo4j，请稍候...
            </p>
          </div>
        )}

        {result && !loading && (
          <>
            {result.success ? (
              <Result
                status="success"
                icon={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
                title="同步成功！"
                subTitle={result.message}
                extra={
                  result.stats && (
                    <Descriptions
                      bordered
                      size="small"
                      column={1}
                      style={{ marginTop: 16 }}
                    >
                      <Descriptions.Item label="同步步骤数">
                        {result.stats.steps}
                      </Descriptions.Item>
                      <Descriptions.Item label="同步实现数">
                        {result.stats.implementations}
                      </Descriptions.Item>
                      <Descriptions.Item label="同步数据资源数">
                        {result.stats.data_resources}
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
            ) : (
              <Result
                status="error"
                icon={<CloseCircleOutlined style={{ color: '#ff4d4f' }} />}
                title="同步失败"
                subTitle={result.message}
                extra={
                  result.error_type && (
                    <Alert
                      message="错误详情"
                      description={
                        <>
                          <p><strong>错误类型:</strong> {result.error_type}</p>
                          {result.error_type === 'connection_error' && (
                            <p style={{ marginTop: 8 }}>
                              请检查Neo4j服务是否正常运行
                            </p>
                          )}
                          {result.error_type === 'auth_error' && (
                            <p style={{ marginTop: 8 }}>
                              请检查Neo4j认证信息是否正确
                            </p>
                          )}
                        </>
                      }
                      type="error"
                      showIcon
                    />
                  )
                }
              />
            )}
          </>
        )}

        <div style={{ textAlign: 'right' }}>
          <Space>
            <Button onClick={handleClose}>
              {result ? '关闭' : '取消'}
            </Button>
            {!result && (
              <Button
                type="primary"
                icon={<SyncOutlined />}
                loading={loading}
                onClick={handlePublish}
              >
                开始发布
              </Button>
            )}
          </Space>
        </div>
      </Space>
    </Modal>
  )
}

export default PublishProcessModal

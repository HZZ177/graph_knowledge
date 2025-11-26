import React, { useEffect, useState } from 'react'
import { Button, Spin } from 'antd'
import { useNavigate } from 'react-router-dom'
import {
  AppstoreOutlined,
  DatabaseOutlined,
  RobotOutlined,
  ArrowRightOutlined,
  PlusOutlined,
  NodeIndexOutlined,
  CodeOutlined,
  PartitionOutlined,
} from '@ant-design/icons'
import { listProcesses, type ProcessItem } from '../api/processes'
import { listBusinessesPaged, listStepsPaged, listImplementationsPaged } from '../api/resourceNodes'
import { listDataResources } from '../api/dataResources'
import { listLLMModels } from '../api/llmModels'

interface StatsData {
  businesses: number
  steps: number
  implementations: number
  dataResources: number
  canvases: number
  models: number
}

const HomePage: React.FC = () => {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState<StatsData>({ 
    businesses: 0, steps: 0, implementations: 0, dataResources: 0, canvases: 0, models: 0 
  })
  const [recentProcesses, setRecentProcesses] = useState<ProcessItem[]>([])

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [
          canvasesRes, 
          businessRes, 
          stepsRes, 
          implRes, 
          dataRes, 
          modelsRes
        ] = await Promise.all([
          listProcesses(),
          listBusinessesPaged('', 1, 1),
          listStepsPaged('', 1, 1),
          listImplementationsPaged('', 1, 1),
          listDataResources({ page: 1, page_size: 1 }),
          listLLMModels(),
        ])
        
        setStats({
          businesses: businessRes.total,
          steps: stepsRes.total,
          implementations: implRes.total,
          dataResources: dataRes.total,
          canvases: canvasesRes.length,
          models: modelsRes.length,
        })
        
        // 取最近5个流程
        setRecentProcesses(canvasesRes.slice(0, 5))
      } catch (e) {
        console.error('Failed to load homepage data:', e)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  // 第一行：资源库相关统计
  const resourceCards = [
    {
      key: 'businesses',
      label: '业务流程',
      value: stats.businesses,
      icon: <AppstoreOutlined />,
      color: '#007aff',
      path: '/resources?tab=business',
    },
    {
      key: 'steps',
      label: '步骤',
      value: stats.steps,
      icon: <NodeIndexOutlined />,
      color: '#5856d6',
      path: '/resources?tab=step',
    },
    {
      key: 'implementations',
      label: '实现单元',
      value: stats.implementations,
      icon: <CodeOutlined />,
      color: '#34c759',
      path: '/resources?tab=implementation',
    },
    {
      key: 'dataResources',
      label: '数据资源',
      value: stats.dataResources,
      icon: <DatabaseOutlined />,
      color: '#ff9500',
      path: '/resources?tab=resource',
    },
  ]

  // 第二行：画布和AI模型
  const operationCards = [
    {
      key: 'canvases',
      label: '画布',
      value: stats.canvases,
      icon: <PartitionOutlined />,
      color: '#ff2d55',
      path: '/business',
    },
    {
      key: 'models',
      label: 'AI 模型',
      value: stats.models,
      icon: <RobotOutlined />,
      color: '#af52de',
      path: '/llm-models',
    },
  ]

  if (loading) {
    return (
      <div style={{ 
        height: '100%', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center' 
      }}>
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div style={{ 
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      gap: 24,
    }}>
      {/* 顶部欢迎区 */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'flex-start',
      }}>
        <div>
          <div style={{ 
            fontSize: 24, 
            fontWeight: 600, 
            color: '#1d1d1f',
            marginBottom: 4,
          }}>
            欢迎回来
          </div>
          <div style={{ 
            fontSize: 14, 
            color: '#86868b',
          }}>
            业务流程配置中心 · 智能编排与管理
          </div>
        </div>
        <Button 
          type="primary" 
          icon={<PlusOutlined />}
          onClick={() => navigate('/business')}
          style={{
            height: 40,
            borderRadius: 8,
            fontWeight: 500,
          }}
        >
          创建业务流程
        </Button>
      </div>

      {/* 第一行：资源库统计 */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(4, 1fr)', 
        gap: 12,
      }}>
        {resourceCards.map((card) => (
          <div
            key={card.key}
            onClick={() => navigate(card.path)}
            style={{
              background: '#f5f5f7',
              borderRadius: 10,
              padding: '16px 18px',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#ebebed'
              e.currentTarget.style.transform = 'translateY(-2px)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#f5f5f7'
              e.currentTarget.style.transform = 'translateY(0)'
            }}
          >
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: 6,
              marginBottom: 10,
            }}>
              <span style={{ 
                width: 6, 
                height: 6, 
                borderRadius: '50%', 
                background: card.color,
              }} />
              <span style={{ 
                fontSize: 12, 
                color: '#86868b',
                fontWeight: 500,
              }}>
                {card.label}
              </span>
            </div>
            <div style={{ 
              fontSize: 28, 
              fontWeight: 600, 
              color: '#1d1d1f',
              marginBottom: 4,
            }}>
              {card.value}
            </div>
            <div style={{ 
              fontSize: 11, 
              color: '#86868b',
              display: 'flex',
              alignItems: 'center',
              gap: 3,
            }}>
              资源库 <ArrowRightOutlined style={{ fontSize: 9 }} />
            </div>
          </div>
        ))}
      </div>

      {/* 第二行：画布和AI模型 */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(2, 1fr)', 
        gap: 12,
      }}>
        {operationCards.map((card) => (
          <div
            key={card.key}
            onClick={() => navigate(card.path)}
            style={{
              background: '#f5f5f7',
              borderRadius: 10,
              padding: '16px 18px',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#ebebed'
              e.currentTarget.style.transform = 'translateY(-2px)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#f5f5f7'
              e.currentTarget.style.transform = 'translateY(0)'
            }}
          >
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: 6,
              marginBottom: 10,
            }}>
              <span style={{ 
                width: 6, 
                height: 6, 
                borderRadius: '50%', 
                background: card.color,
              }} />
              <span style={{ 
                fontSize: 12, 
                color: '#86868b',
                fontWeight: 500,
              }}>
                {card.label}
              </span>
            </div>
            <div style={{ 
              fontSize: 28, 
              fontWeight: 600, 
              color: '#1d1d1f',
              marginBottom: 4,
            }}>
              {card.value}
            </div>
            <div style={{ 
              fontSize: 11, 
              color: '#86868b',
              display: 'flex',
              alignItems: 'center',
              gap: 3,
            }}>
              {card.key === 'canvases' ? '业务库' : 'AI 配置'} <ArrowRightOutlined style={{ fontSize: 9 }} />
            </div>
          </div>
        ))}
      </div>

      {/* 最近编辑 */}
      <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
        <div style={{ 
          fontSize: 15, 
          fontWeight: 500, 
          color: '#1d1d1f',
          marginBottom: 12,
        }}>
          最近的业务流程
        </div>
        
        {recentProcesses.length === 0 ? (
          <div style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            background: '#f5f5f7',
            borderRadius: 12,
            color: '#86868b',
          }}>
            <AppstoreOutlined style={{ fontSize: 32, marginBottom: 12, color: '#c7c7cc' }} />
            <div style={{ fontSize: 14, marginBottom: 16 }}>还没有业务流程</div>
            <Button 
              type="primary" 
              ghost
              onClick={() => navigate('/business')}
              style={{ borderRadius: 6 }}
            >
              创建第一个流程
            </Button>
          </div>
        ) : (
          <div style={{
            background: '#f5f5f7',
            borderRadius: 12,
            overflow: 'hidden',
          }}>
            {recentProcesses.map((process, index) => (
              <div
                key={process.process_id}
                onClick={() => navigate('/business')}
                style={{
                  padding: '14px 20px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  cursor: 'pointer',
                  borderBottom: index < recentProcesses.length - 1 ? '1px solid #e5e5ea' : 'none',
                  transition: 'background 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = '#ebebed'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{
                    width: 36,
                    height: 36,
                    borderRadius: 8,
                    background: '#fff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#007aff',
                    fontSize: 16,
                  }}>
                    <AppstoreOutlined />
                  </div>
                  <div>
                    <div style={{ 
                      fontSize: 14, 
                      fontWeight: 500, 
                      color: '#1d1d1f',
                      marginBottom: 2,
                    }}>
                      {process.name}
                    </div>
                    <div style={{ fontSize: 12, color: '#86868b' }}>
                      {process.channel === 'mobile' ? '移动端' : 
                       process.channel === 'admin' ? '后台' : 
                       process.channel || '未分类'}
                    </div>
                  </div>
                </div>
                <div style={{ 
                  fontSize: 12, 
                  color: '#007aff',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                }}>
                  编辑 <ArrowRightOutlined style={{ fontSize: 10 }} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default HomePage

import React, { useState, useEffect } from 'react'
import { Layout, Menu, Button, Select, Typography, Space } from 'antd'
import {
  HomeOutlined,
  AppstoreOutlined,
  DatabaseOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  RobotOutlined,
  MessageOutlined,
} from '@ant-design/icons'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { listLLMModels, activateLLMModel, activateTaskModel, type AIModelOut } from '../api/llmModels'
import { showError, showSuccess } from '../utils/message'

const { Header, Sider, Content } = Layout
const { Option } = Select
const { Text } = Typography

const MainLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(true)
  const [models, setModels] = useState<AIModelOut[]>([])
  const [activeModelId, setActiveModelId] = useState<number | null>(null)
  const [taskModelId, setTaskModelId] = useState<number | null>(null)
  const [modelLoading, setModelLoading] = useState(false)
  const [activating, setActivating] = useState(false)
  const [activatingTask, setActivatingTask] = useState(false)

  const location = useLocation()
  const navigate = useNavigate()

  const fetchModels = async () => {
    setModelLoading(true)
    try {
      const data = await listLLMModels()
      setModels(data)
      const active = data.find((m) => m.is_active)
      const taskActive = data.find((m) => m.is_task_active)
      setActiveModelId(active ? active.id : null)
      setTaskModelId(taskActive ? taskActive.id : null)
    } catch (e) {
      showError('加载模型列表失败')
    } finally {
      setModelLoading(false)
    }
  }

  useEffect(() => {
    fetchModels()
  }, [])

  const handleChangeActiveModel = async (value: number) => {
    try {
      setActivating(true)
      await activateLLMModel(value)
      showSuccess('已设置为主力模型')
      fetchModels()
    } catch (e) {
      showError('激活模型失败')
    } finally {
      setActivating(false)
    }
  }

  const handleChangeTaskModel = async (value: number) => {
    try {
      setActivatingTask(true)
      await activateTaskModel(value)
      showSuccess('已设置为小任务模型')
      fetchModels()
    } catch (e) {
      showError('激活模型失败')
    } finally {
      setActivatingTask(false)
    }
  }

  const menuItems = [
    {
      key: '/',
      icon: <HomeOutlined />,
      label: <Link to="/">首页</Link>,
    },
    {
      key: '/chat',
      icon: <MessageOutlined />,
      label: <Link to="/chat">智能问答</Link>,
    },
    {
      key: '/resources',
      icon: <DatabaseOutlined />,
      label: <Link to="/resources">资源库</Link>,
    },
    {
      key: '/business',
      icon: <AppstoreOutlined />,
      label: <Link to="/business">业务库</Link>,
    },
    {
      key: '/llm-models',
      icon: <RobotOutlined />,
      label: <Link to="/llm-models">AI 模型</Link>,
    },
  ]

  return (
    <Layout style={{ height: '100vh', overflow: 'hidden' }}>
      <Sider
        theme="light"
        collapsible
        collapsed={collapsed}
        trigger={null}
        width={220}
        style={{
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          borderRight: '1px solid #f0f0f0',
          background: '#fff',
        }}
      >
        <div
          style={{
            height: 48,
            margin: 16,
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            fontSize: 18,
            fontWeight: 600,
            gap: 8,
          }}
        >
          <img 
            src="/favicon.svg" 
            alt="Logo" 
            style={{ 
              width: 28, 
              height: 28,
              flexShrink: 0,
            }} 
          />
          {!collapsed && <span>业务引擎</span>}
        </div>
        <Menu
          theme="light"
          mode="inline"
          selectedKeys={[location.pathname === '/' ? '/' : location.pathname]}
          items={menuItems}
          onClick={(info) => {
            if (info.key !== location.pathname) {
              navigate(info.key)
            }
          }}
        />
      </Sider>

      <Layout
        style={{
          marginLeft: collapsed ? 80 : 220,
          transition: 'margin-left 0.2s',
          height: '100vh',
          overflow: 'hidden',
        }}
      >
        <Header
          style={{
            padding: 0,
            background: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed(!collapsed)}
              style={{
                fontSize: 16,
                width: 64,
                height: 64,
              }}
            />
            <span style={{ fontSize: 16, fontWeight: 500 }}>智能问答</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', paddingRight: 16, gap: 24 }}>
            <Space size={8} align="center">
              <Text type="secondary" style={{ fontSize: 12 }}>
                主力模型
              </Text>
              <Select
                style={{ minWidth: 200 }}
                placeholder="选择模型"
                size="middle"
                value={activeModelId ?? undefined}
                loading={modelLoading || activating}
                onChange={handleChangeActiveModel}
              >
                {models.map((m) => {
                  const label = m.provider ? `${m.provider}/${m.model_name}` : m.model_name
                  return (
                    <Option key={m.id} value={m.id}>
                      {m.name}（{label}）
                    </Option>
                  )
                })}
              </Select>
            </Space>
            <Space size={8} align="center">
              <Text type="secondary" style={{ fontSize: 12 }}>
                快速模型
              </Text>
              <Select
                style={{ minWidth: 200 }}
                placeholder="选择模型"
                size="middle"
                value={taskModelId ?? undefined}
                loading={modelLoading || activatingTask}
                onChange={handleChangeTaskModel}
                allowClear
                onClear={() => setTaskModelId(null)}
              >
                {models.map((m) => {
                  const label = m.provider ? `${m.provider}/${m.model_name}` : m.model_name
                  return (
                    <Option key={m.id} value={m.id}>
                      {m.name}（{label}）
                    </Option>
                  )
                })}
              </Select>
            </Space>
          </div>
        </Header>
        <Content
          style={{
            margin: '24px 16px',
            padding: 24,
            borderRadius: 8,
            background: '#fff',
            display: 'flex',
            flexDirection: 'column',
            // 100vh 减去 Header 高度(64px)、Content 上下 margin(48px)、Content 上下 padding(48px)
            height: 'calc(100vh - 64px - 48px - 48px)',
            overflow: 'hidden',
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}

export default MainLayout

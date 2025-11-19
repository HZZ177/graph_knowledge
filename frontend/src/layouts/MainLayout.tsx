import React, { useState } from 'react'
import { Layout, Menu, Button } from 'antd'
import {
  HomeOutlined,
  AppstoreOutlined,
  DatabaseOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'

const { Header, Sider, Content } = Layout

const MainLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()

  const menuItems = [
    {
      key: '/',
      icon: <HomeOutlined />,
      label: <Link to="/">首页</Link>,
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
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
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
          }}
        >
          <span style={{ marginLeft: collapsed ? 0 : 4 }}>业务引擎</span>
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

      <Layout style={{ marginLeft: collapsed ? 80 : 220, transition: 'margin-left 0.2s' }}>
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
            <span style={{ fontSize: 16, fontWeight: 500 }}>业务流程配置中心</span>
          </div>
        </Header>
        <Content
          style={{
            margin: '24px 16px',
            padding: 24,
            overflow: 'auto',
            borderRadius: 8,
            background: '#fff',
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}

export default MainLayout

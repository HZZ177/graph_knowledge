import React, { useState } from 'react'
import { Tabs } from 'antd'
import {
  DatabaseOutlined,
  CodeOutlined,
  NodeIndexOutlined,
  BranchesOutlined,
} from '@ant-design/icons'

import '../styles/ResourceLibraryPage.css'

import BusinessProcessPage from './BusinessProcessPage'
import StepLibraryPage from './StepLibraryPage'
import ImplementationLibraryPage from './ImplementationLibraryPage'
import DataResourceLibraryPage from './DataResourceLibraryPage'

// ============ 主页面 ============
// 所有Tab已拆分为独立页面组件
// - BusinessProcessPage: 业务流程管理
// - StepLibraryPage: 业务步骤管理
// - ImplementationLibraryPage: 实现单元管理
// - DataResourceLibraryPage: 数据资源管理

const ResourceLibraryPage: React.FC = () => {
  const searchParams = new URLSearchParams(window.location.search)
  const tabFromUrl = searchParams.get('tab')
  const validTabs = ['business', 'step', 'implementation', 'resource']
  const initialTab = tabFromUrl && validTabs.includes(tabFromUrl) ? tabFromUrl : 'business'
  const [activeTab, setActiveTab] = useState<string>(initialTab)

  return (
    <div className="resource-library-container">
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
        <Tabs
          className="custom-tabs"
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            { key: 'business', label: <span><BranchesOutlined /> 业务流程</span>, children: <BusinessProcessPage /> },
            { key: 'step', label: <span><NodeIndexOutlined /> 业务步骤</span>, children: <StepLibraryPage /> },
            { key: 'implementation', label: <span><CodeOutlined /> 实现单元</span>, children: <ImplementationLibraryPage /> },
            { key: 'resource', label: <span><DatabaseOutlined /> 数据资源</span>, children: <DataResourceLibraryPage /> },
          ]}
        />
      </div>
    </div>
  )
}

export default ResourceLibraryPage

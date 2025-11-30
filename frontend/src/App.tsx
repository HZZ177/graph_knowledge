import React from 'react'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { RouterProvider } from 'react-router-dom'
import router from './router'
import { ModelProvider } from './contexts/ModelContext'

const App: React.FC = () => {
  return (
    <ConfigProvider locale={zhCN}>
      <ModelProvider>
        <RouterProvider router={router} />
      </ModelProvider>
    </ConfigProvider>
  )
}

export default App

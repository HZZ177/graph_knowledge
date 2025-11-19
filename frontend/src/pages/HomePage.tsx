import React from 'react'
import { Card, Typography } from 'antd'

const { Title, Paragraph } = Typography

const HomePage: React.FC = () => {
  return (
    <Card>
      <Title level={3}>欢迎使用业务引擎前端框架</Title>
      <Paragraph>
        这里是占位首页，仅用于展示整体布局和样式。实际业务页面可以在此基础上逐步替换和扩展。
      </Paragraph>
    </Card>
  )
}

export default HomePage

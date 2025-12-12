/**
 * 缓存的 Markdown 组件（避免重复渲染已完成的内容）
 */

import React from 'react'
import MarkdownPreview from '@uiw/react-markdown-preview'
import { Image } from 'antd'

interface MemoizedMarkdownProps {
  source: string
  fontSize?: number
}

export const MemoizedMarkdown = React.memo<MemoizedMarkdownProps>(({ source, fontSize = 16 }) => {
  return (
    <MarkdownPreview
      source={source}
      style={{ background: 'transparent', fontSize }}
      wrapperElement={{ "data-color-mode": "light" }}
      components={{
        img: ({ src, alt }) => (
          <Image
            src={src}
            alt={alt}
            style={{ maxWidth: '100%', borderRadius: '8px', cursor: 'pointer' }}
            preview={{ mask: <div style={{ fontSize: 12 }}>点击预览</div> }}
          />
        )
      }}
    />
  )
}, (prevProps, nextProps) => {
  // 只有 source 变化才重新渲染
  return prevProps.source === nextProps.source && prevProps.fontSize === nextProps.fontSize
})

export default MemoizedMarkdown

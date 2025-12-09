/**
 * 缓存的 Markdown 组件（避免重复渲染已完成的内容）
 */

import React from 'react'
import MarkdownPreview from '@uiw/react-markdown-preview'

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
    />
  )
}, (prevProps, nextProps) => {
  // 只有 source 变化才重新渲染
  return prevProps.source === nextProps.source && prevProps.fontSize === nextProps.fontSize
})

export default MemoizedMarkdown

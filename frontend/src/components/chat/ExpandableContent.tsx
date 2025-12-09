/**
 * 通用可展开内容组件（动态测量高度，实现平滑动画）
 */

import React, { useRef, useState, useEffect } from 'react'

interface ExpandableContentProps {
  isExpanded: boolean
  className?: string
  children: React.ReactNode
}

export const ExpandableContent: React.FC<ExpandableContentProps> = ({ isExpanded, className, children }) => {
  const contentRef = useRef<HTMLDivElement>(null)
  const [height, setHeight] = useState<number | 'auto'>(0)
  
  useEffect(() => {
    if (!contentRef.current) return
    
    if (isExpanded) {
      // 展开：测量实际高度
      const scrollHeight = contentRef.current.scrollHeight
      setHeight(scrollHeight)
      // 动画结束后设为 auto，允许内容动态变化
      const timer = setTimeout(() => setHeight('auto'), 300)
      return () => clearTimeout(timer)
    } else {
      // 收起：先设为当前高度（触发过渡），再设为 0
      const scrollHeight = contentRef.current.scrollHeight
      setHeight(scrollHeight)
      requestAnimationFrame(() => {
        requestAnimationFrame(() => setHeight(0))
      })
    }
  }, [isExpanded])
  
  return (
    <div
      ref={contentRef}
      className={`expandable-content ${className || ''}`}
      style={{
        height: height === 'auto' ? 'auto' : height,
        opacity: isExpanded ? 1 : 0,
        visibility: isExpanded || height !== 0 ? 'visible' : 'hidden',
      }}
    >
      {children}
    </div>
  )
}

export default ExpandableContent

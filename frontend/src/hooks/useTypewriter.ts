/**
 * 智能打字机效果 Hook
 * 
 * 特性：
 * - 动态速度调整：根据缓冲区积压量自动加速/减速
 * - 完成加速：标记完成后加速清空缓冲区
 * - 平滑显示：避免一次性全部输出
 * 
 * Usage:
 *   const { text, append, finish, reset, isTyping } = useTypewriter()
 *   
 *   // 收到流式 chunk 时
 *   append(chunk)
 *   
 *   // 流结束时
 *   finish()
 */

import { useState, useRef, useCallback, useEffect } from 'react'

interface TypewriterOptions {
  /** 正常显示速度区间 (ms) */
  normalSpeed?: { min: number; max: number }
  /** 追赶模式速度区间 (ms) */
  catchUpSpeed?: { min: number; max: number }
  /** 完成后加速速度区间 (ms) */
  finishSpeed?: { min: number; max: number }
  /** 触发追赶模式的缓冲区阈值 */
  catchUpThreshold?: number
  /** 每次显示时的回调（用于触发滚动等） */
  onTick?: () => void
}

interface TypewriterReturn {
  /** 当前已显示的文本 */
  text: string
  /** 向缓冲区追加文本 */
  append: (chunk: string) => void
  /** 标记流结束，触发加速显示 */
  finish: () => void
  /** 重置状态 */
  reset: () => void
  /** 是否正在打字（缓冲区有内容） */
  isTyping: boolean
  /** 缓冲区剩余长度 */
  bufferLength: number
}

const DEFAULT_OPTIONS: Required<Omit<TypewriterOptions, 'onTick'>> = {
  normalSpeed: { min: 3, max: 10 },      // 正常模式
  catchUpSpeed: { min: 1, max: 5 },      // 追赶模式
  finishSpeed: { min: 1, max: 3 },       // 完成模式
  catchUpThreshold: 20,                  // 更早触发追赶
}

export function useTypewriter(options?: TypewriterOptions): TypewriterReturn {
  const opts = { ...DEFAULT_OPTIONS, ...options }
  
  const [text, setText] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const [bufferLength, setBufferLength] = useState(0)
  
  const bufferRef = useRef('')
  const timerRef = useRef<number | null>(null)
  const finishedRef = useRef(false)
  const onTickRef = useRef(options?.onTick)
  
  // 更新 onTick 引用
  useEffect(() => {
    onTickRef.current = options?.onTick
  }, [options?.onTick])
  
  // 计算动态速度
  const getSpeed = useCallback((bufLen: number, finished: boolean) => {
    if (finished) {
      // 完成后快速清空
      const { min, max } = opts.finishSpeed
      if (bufLen > 100) return min
      if (bufLen > 50) return Math.floor((min + max) / 2)
      return max
    }
    
    if (bufLen > opts.catchUpThreshold * 3) {
      // 严重积压，使用最快速度
      return opts.catchUpSpeed.min
    }
    
    if (bufLen > opts.catchUpThreshold) {
      // 中等积压，追赶模式
      const { min, max } = opts.catchUpSpeed
      const ratio = Math.min(1, (bufLen - opts.catchUpThreshold) / (opts.catchUpThreshold * 2))
      return Math.floor(max - ratio * (max - min))
    }
    
    // 正常模式，享受打字机效果
    const { min, max } = opts.normalSpeed
    const ratio = bufLen / opts.catchUpThreshold
    return Math.floor(max - ratio * (max - min))
  }, [opts])
  
  // 计算每次取出的字符数：根据积压量动态调整，确保吐量跟得上输入
  const getCharsToTake = useCallback((bufLen: number, firstChar: string, finished: boolean) => {
    const isChinese = /[\u4e00-\u9fa5]/.test(firstChar)
    
    if (finished) {
      // 完成后立即清空
      if (bufLen > 1000) return isChinese ? 100 : 150
      if (bufLen > 500) return isChinese ? 50 : 80
      if (bufLen > 200) return isChinese ? 25 : 40
      if (bufLen > 100) return isChinese ? 15 : 25
      return isChinese ? 8 : 12
    }
    
    // 正常模式：积压越多，每次取越多，保持吐量平衡
    if (bufLen > 500) return isChinese ? 30 : 50
    if (bufLen > 200) return isChinese ? 15 : 25
    if (bufLen > 100) return isChinese ? 8 : 15
    if (bufLen > 50) return isChinese ? 5 : 8
    return isChinese ? 3 : 5
  }, [])
  
  // 启动打字机
  const startTypewriter = useCallback(() => {
    if (timerRef.current) return
    
    const tick = () => {
      const buffer = bufferRef.current
      if (buffer.length === 0) {
        timerRef.current = null
        setIsTyping(false)
        return
      }
      
      const finished = finishedRef.current
      const charsToTake = getCharsToTake(buffer.length, buffer.charAt(0), finished)
      const chars = buffer.slice(0, charsToTake)
      bufferRef.current = buffer.slice(charsToTake)
      
      setText(prev => prev + chars)
      setBufferLength(bufferRef.current.length)
      
      // 触发回调（如滚动）
      onTickRef.current?.()
      
      // 继续下一轮
      if (bufferRef.current.length > 0) {
        const speed = getSpeed(bufferRef.current.length, finished)
        timerRef.current = window.setTimeout(tick, speed)
      } else {
        timerRef.current = null
        setIsTyping(false)
      }
    }
    
    setIsTyping(true)
    const speed = getSpeed(bufferRef.current.length, finishedRef.current)
    timerRef.current = window.setTimeout(tick, speed)
  }, [getSpeed, getCharsToTake])
  
  // 追加文本到缓冲区
  const append = useCallback((chunk: string) => {
    if (!chunk) return
    bufferRef.current += chunk
    setBufferLength(bufferRef.current.length)
    startTypewriter()
  }, [startTypewriter])
  
  // 标记完成
  const finish = useCallback(() => {
    finishedRef.current = true
    startTypewriter()  // 确保在运行以加速清空
  }, [startTypewriter])
  
  // 重置
  const reset = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
    bufferRef.current = ''
    finishedRef.current = false
    setText('')
    setIsTyping(false)
    setBufferLength(0)
  }, [])
  
  // 组件卸载时清理
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current)
      }
    }
  }, [])
  
  return { text, append, finish, reset, isTyping, bufferLength }
}

/**
 * 多通道打字机 Hook（用于多 Agent 场景）
 */
export function useMultiTypewriter(
  channelCount: number,
  options?: TypewriterOptions
): {
  texts: string[]
  append: (channel: number, chunk: string) => void
  finish: (channel: number) => void
  reset: () => void
  isTyping: boolean
} {
  const opts = { ...DEFAULT_OPTIONS, ...options }
  
  const [texts, setTexts] = useState<string[]>(() => Array(channelCount).fill(''))
  const [isTyping, setIsTyping] = useState(false)
  
  const buffersRef = useRef<string[]>(Array(channelCount).fill(''))
  const finishedRef = useRef<boolean[]>(Array(channelCount).fill(false))
  const timerRef = useRef<number | null>(null)
  const onTickRef = useRef(options?.onTick)
  
  // 初始化
  useEffect(() => {
    buffersRef.current = Array(channelCount).fill('')
    finishedRef.current = Array(channelCount).fill(false)
    setTexts(Array(channelCount).fill(''))
  }, [channelCount])
  
  useEffect(() => {
    onTickRef.current = options?.onTick
  }, [options?.onTick])
  
  // 计算速度（基于所有通道的总积压）
  const getSpeed = useCallback((totalLen: number, hasFinished: boolean) => {
    if (hasFinished) {
      const { min, max } = opts.finishSpeed
      if (totalLen > 100) return min
      if (totalLen > 50) return Math.floor((min + max) / 2)
      return max
    }
    if (totalLen > opts.catchUpThreshold * 3) return opts.catchUpSpeed.min
    if (totalLen > opts.catchUpThreshold) {
      const { min, max } = opts.catchUpSpeed
      const ratio = Math.min(1, (totalLen - opts.catchUpThreshold) / (opts.catchUpThreshold * 2))
      return Math.floor(max - ratio * (max - min))
    }
    const { min, max } = opts.normalSpeed
    return Math.floor(max - (totalLen / opts.catchUpThreshold) * (max - min))
  }, [opts])
  
  const getCharsToTake = useCallback((bufLen: number, firstChar: string, finished: boolean) => {
    const isChinese = /[\u4e00-\u9fa5]/.test(firstChar)
    if (finished) {
      // 完成后立即清空
      if (bufLen > 1000) return isChinese ? 100 : 150
      if (bufLen > 500) return isChinese ? 50 : 80
      if (bufLen > 200) return isChinese ? 25 : 40
      if (bufLen > 100) return isChinese ? 15 : 25
      return isChinese ? 8 : 12
    }
    // 正常模式：积压越多，每次取越多
    if (bufLen > 500) return isChinese ? 30 : 50
    if (bufLen > 200) return isChinese ? 15 : 25
    if (bufLen > 100) return isChinese ? 8 : 15
    if (bufLen > 50) return isChinese ? 5 : 8
    return isChinese ? 3 : 5
  }, [])
  
  const startTypewriter = useCallback(() => {
    if (timerRef.current) return
    
    const tick = () => {
      const buffers = buffersRef.current
      const finished = finishedRef.current
      const totalLen = buffers.reduce((sum, b) => sum + b.length, 0)
      
      if (totalLen === 0) {
        timerRef.current = null
        setIsTyping(false)
        return
      }
      
      const hasFinishedWithBuffer = finished.some((f, i) => f && buffers[i].length > 0)
      
      setTexts(prev => prev.map((text, idx) => {
        const buffer = buffers[idx]
        if (buffer.length === 0) return text
        
        const isFinished = finished[idx]
        const charsToTake = getCharsToTake(buffer.length, buffer.charAt(0), isFinished)
        const chars = buffer.slice(0, charsToTake)
        buffersRef.current[idx] = buffer.slice(charsToTake)
        
        return text + chars
      }))
      
      onTickRef.current?.()
      
      const remainingLen = buffersRef.current.reduce((sum, b) => sum + b.length, 0)
      if (remainingLen > 0) {
        const speed = getSpeed(remainingLen, hasFinishedWithBuffer)
        timerRef.current = window.setTimeout(tick, speed)
      } else {
        timerRef.current = null
        setIsTyping(false)
      }
    }
    
    setIsTyping(true)
    const totalLen = buffersRef.current.reduce((sum, b) => sum + b.length, 0)
    const speed = getSpeed(totalLen, false)
    timerRef.current = window.setTimeout(tick, speed)
  }, [getSpeed, getCharsToTake])
  
  const append = useCallback((channel: number, chunk: string) => {
    if (!chunk || channel < 0 || channel >= channelCount) return
    buffersRef.current[channel] += chunk
    startTypewriter()
  }, [channelCount, startTypewriter])
  
  const finish = useCallback((channel: number) => {
    if (channel < 0 || channel >= channelCount) return
    finishedRef.current[channel] = true
    startTypewriter()
  }, [channelCount, startTypewriter])
  
  const reset = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
    buffersRef.current = Array(channelCount).fill('')
    finishedRef.current = Array(channelCount).fill(false)
    setTexts(Array(channelCount).fill(''))
    setIsTyping(false)
  }, [channelCount])
  
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current)
      }
    }
  }, [])
  
  return { texts, append, finish, reset, isTyping }
}

export default useTypewriter

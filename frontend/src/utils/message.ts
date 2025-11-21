import { message } from 'antd'
import type { ArgsProps } from 'antd/es/message'

// 自适应偏移（导航栏高度 + 间距），进一步贴近顶部
const getOffset = (): number => {
  if (typeof window !== 'undefined') {
    // 再缩小一半：移动端略大，桌面端约 26px
    return window.innerWidth <= 768 ? 36 : 26
  }
  return 26
}

// 配置全局默认项
message.config({
  top: getOffset(),
  duration: 3,
  maxCount: 10, // 最多同时显示10个消息
  prefixCls: 'ant-message', // 保持默认前缀
})

// 通用默认配置
const baseDefaults: Partial<ArgsProps> = {
  duration: 3,
}

/**
 * 显示成功消息
 * @param content 消息内容
 * @param options 可选配置项
 */
export const showSuccess = (content: string, options?: Partial<ArgsProps>) => {
  return message.success({
    content,
    ...baseDefaults,
    ...options,
  })
}

/**
 * 显示警告消息
 * @param content 消息内容
 * @param options 可选配置项
 */
export const showWarning = (content: string, options?: Partial<ArgsProps>) => {
  return message.warning({
    content,
    ...baseDefaults,
    ...options,
  })
}

/**
 * 显示错误消息
 * @param content 消息内容
 * @param options 可选配置项
 */
export const showError = (content: string, options?: Partial<ArgsProps>) => {
  return message.error({
    content,
    ...baseDefaults,
    duration: 4, // 错误消息显示时间稍长
    ...options,
  })
}

/**
 * 显示信息消息
 * @param content 消息内容
 * @param options 可选配置项
 */
export const showInfo = (content: string, options?: Partial<ArgsProps>) => {
  return message.info({
    content,
    ...baseDefaults,
    ...options,
  })
}

/**
 * 显示加载中消息
 * @param content 消息内容
 * @param options 可选配置项
 */
export const showLoading = (content: string, options?: Partial<ArgsProps>) => {
  return message.loading({
    content,
    duration: 0, // 加载消息默认不自动关闭
    ...options,
  })
}

/**
 * 显示自定义消息
 * @param options 完整配置项
 */
export const showMessage = (options: ArgsProps) => {
  return message.open({
    ...baseDefaults,
    ...options,
  })
}

// 导出 message 实例的其他方法
export const destroyMessage = message.destroy
export const destroyAllMessages = () => message.destroy()

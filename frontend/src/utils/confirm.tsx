import React from 'react'
import { Modal, type ButtonProps } from 'antd'
import { ExclamationCircleOutlined } from '@ant-design/icons'

export interface ConfirmOptions {
  title?: React.ReactNode
  content?: React.ReactNode
  okText?: React.ReactNode
  cancelText?: React.ReactNode
  okType?: ButtonProps['type']
  okButtonProps?: ButtonProps
  centered?: boolean
}

/**
 * 统一确认弹窗
 * 样式与全局消息风格保持一致，通过 yc-confirm-modal 类名绑定样式。
 */
export const showConfirm = (options: ConfirmOptions): Promise<boolean> => {
  return new Promise((resolve) => {
    Modal.confirm({
      className: 'yc-confirm-modal',
      centered: options.centered ?? true,
      icon: <ExclamationCircleOutlined />,
      okText: options.okText ?? '确定',
      cancelText: options.cancelText ?? '取消',
      okType: options.okType ?? 'primary',
      ...options,
      onOk: () => {
        resolve(true)
      },
      onCancel: () => {
        resolve(false)
      },
    })
  })
}

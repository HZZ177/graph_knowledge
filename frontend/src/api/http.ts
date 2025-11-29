import axios, { type AxiosResponse, type AxiosError } from 'axios'
import { message } from 'antd'

// 简单的 axios 实例，使用相对路径走 Vite 代理
const http = axios.create({
  baseURL: '/api/v1',
})

// 统一处理后端约定的 { code, message, data } 响应格式
http.interceptors.response.use(
  (response: AxiosResponse) => {
    const resData = response.data as any

    // 仅对包含 code/data 字段的响应做统一处理
    if (resData && typeof resData === 'object' && 'code' in resData && 'data' in resData) {
      const { code, message: msg, data } = resData as {
        code: number
        message?: string
        data: any
      }

      if (code === 200) {
        // 保持调用方 API 不变：res.data 直接是业务数据
        ;(response as AxiosResponse).data = data
        return response
      }

      // 业务错误：统一弹出错误提示，并把错误对象抛给调用方
      if (msg) {
        message.error(msg)
      }

      return Promise.reject({ code, message: msg, data })
    }

    return response
  },
  (error: AxiosError) => {
    // 网络/HTTP 层错误（例如 422、500 等）
    message.error(error.message || '网络错误')
    return Promise.reject(error)
  },
)

export default http

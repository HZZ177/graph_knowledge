import axios from 'axios'

// 简单的 axios 实例，指向本地 FastAPI 后端
const http = axios.create({
  baseURL: 'http://localhost:8000/api/v1',
})

export default http

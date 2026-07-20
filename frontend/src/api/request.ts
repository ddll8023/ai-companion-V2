import axios from 'axios'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 响应拦截器
request.interceptors.response.use(
  (response) => {
    const data = response.data
    if (data.code !== 0) {
      return Promise.reject(new Error(data.message || '请求失败'))
    }
    return data
  },
  (error) => {
    return Promise.reject(error)
  },
)

export default request

/**
 * 统一通信抽象层。
 *
 * 浏览器开发环境：使用 HTTP 适配器
 * Electron 正式环境：使用 IPC 适配器
 *
 * 页面和 Store 使用统一业务接口，不感知通信差异。
 */

import type { ApiResponse } from '@/types/api'
import request from '@/api/request'

/** 运行环境类型 */
export type RuntimeEnv = 'browser' | 'electron'

/** 通信适配器接口 */
export interface CommunicationAdapter {
  get: <T>(url: string) => Promise<ApiResponse<T>>
  post: <T>(url: string, data?: unknown) => Promise<ApiResponse<T>>
}

/** HTTP 适配器（浏览器开发模式） */
const httpAdapter: CommunicationAdapter = {
  get: <T>(url: string) => request.get<ApiResponse<T>>(url),
  post: <T>(url: string, data?: unknown) => request.post<ApiResponse<T>>(url, data),
}

/** IPC 适配器（Electron 正式环境） - 占位实现，后续阶段完善 */
const ipcAdapter: CommunicationAdapter = {
  get: <T>(url: string) => {
    // TODO 阶段 3：通过 IPC 转发请求
    return Promise.reject(new Error('IPC 适配器尚未实现'))
  },
  post: <T>(url: string, data?: unknown) => {
    // TODO 阶段 3：通过 IPC 转发请求
    return Promise.reject(new Error('IPC 适配器尚未实现'))
  },
}

/**
 * 检测当前运行环境。
 * 通过 window.electronAPI 的存在判断。
 */
function detectRuntime(): RuntimeEnv {
  return typeof window !== 'undefined' && window.electronAPI ? 'electron' : 'browser'
}

/**
 * 获取当前环境的通信适配器。
 * 环境判断集中在通信层，不在页面中散落 window.electronAPI 判断。
 */
function getAdapter(): CommunicationAdapter {
  return detectRuntime() === 'electron' ? ipcAdapter : httpAdapter
}

/**
 * 统一通信接口。
 * 页面和 Store 使用此接口，不直接使用 Axios 或 IPC。
 */
export function useApi() {
  const adapter = getAdapter()

  return {
    get: adapter.get,
    post: adapter.post,
  }
}

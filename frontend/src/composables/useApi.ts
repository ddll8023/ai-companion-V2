/**
 * 统一通信抽象层。
 *
 * 浏览器开发环境：使用 HTTP 适配器（Axios）
 * Electron 正式环境：使用 IPC 适配器（通过 preload 桥接）
 *
 * 页面和 Store 使用统一业务接口，不感知通信差异。
 * 环境判断集中在通信层，不在页面中散落 window.electronAPI 判断。
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

/** IPC 适配器（Electron 正式环境） */
const ipcAdapter: CommunicationAdapter = {
  get: async <T>(url: string) => {
    const result = await window.electronAPI!.apiGet<T>(url)
    if (result.code !== 0) {
      throw new Error(result.message || '请求失败')
    }
    return result as unknown as ApiResponse<T>
  },
  post: async <T>(url: string, data?: unknown) => {
    const result = await window.electronAPI!.apiPost<T>(url, data)
    if (result.code !== 0) {
      throw new Error(result.message || '请求失败')
    }
    return result as unknown as ApiResponse<T>
  },
}

/** 检测当前运行环境（内部使用，不与 useApi 重复） */
let _runtime: RuntimeEnv | null = null
function detectRuntime(): RuntimeEnv {
  if (_runtime) return _runtime
  _runtime = typeof window !== 'undefined' && window.electronAPI ? 'electron' : 'browser'
  return _runtime
}

/** 获取当前环境的通信适配器 */
function getAdapter(): CommunicationAdapter {
  return detectRuntime() === 'electron' ? ipcAdapter : httpAdapter
}

/**
 * 统一通信接口。
 * 页面和 Store 使用此接口，不直接使用 Axios 或 IPC。
 * 环境判断集中在通信层，不在页面中散落 window.electronAPI 判断。
 */
export function useApi() {
  const adapter = getAdapter()
  const runtime = detectRuntime()

  return {
    get: adapter.get,
    post: adapter.post,

    /** 当前运行环境是否为 Electron */
    isElectron: runtime === 'electron',

    /**
     * 注册后端服务状态变化监听。
     * Electron 模式：通过 IPC 事件接收推送
     * 浏览器模式：不支持事件推送（onBackendStatus 为 undefined），页面需主动轮询
     */
    onBackendStatus: runtime === 'electron'
      ? (callback: (status: { ready: boolean }) => void): void => {
          window.electronAPI!.onBackendStatus(callback)
        }
      : undefined,

    /** 移除后端服务状态监听（仅 Electron 模式有效） */
    removeBackendStatusListener: runtime === 'electron'
      ? (): void => {
          window.electronAPI!.removeBackendStatusListener()
        }
      : undefined,
  }
}

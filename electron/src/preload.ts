/**
 * AI Companion — Preload 脚本
 *
 * 安全职责（按设计文档要求）：
 * - 只暴露受控白名单能力
 * - 不暴露通用 IPC 发送能力（不暴露 ipcRenderer.send）
 * - Renderer 无法获得端口、令牌、数据库路径和密钥明文
 */

import { contextBridge, ipcRenderer } from 'electron';

/** IPC 通道名称（与 main.ts 保持一致） */
const IPC_CHANNELS = {
  API_GET: 'api:get',
  API_POST: 'api:post',
  KEYSTORE_SET: 'keystore:set',
  KEYSTORE_GET: 'keystore:get',
  KEYSTORE_DELETE: 'keystore:delete',
  KEYSTORE_HAS: 'keystore:has',
  BACKEND_STATUS: 'backend-status',
  GET_PLATFORM: 'get-platform',
  GET_APP_VERSION: 'get-app-version',
  GET_DATA_DIR: 'get-data-dir',
} as const;

/**
 * 受控白名单 API。
 * Renderer 只能通过此接口调用指定的桌面能力。
 */
const api = {
  // ── API 代理 ────────────────────────────────────────────
  /** 通过 IPC 发送 GET 请求到本地服务 */
  apiGet: <T>(url: string): Promise<{ code: number; message: string; data?: T }> =>
    ipcRenderer.invoke(IPC_CHANNELS.API_GET, url),

  /** 通过 IPC 发送 POST 请求到本地服务 */
  apiPost: <T>(url: string, data?: unknown): Promise<{ code: number; message: string; data?: T }> =>
    ipcRenderer.invoke(IPC_CHANNELS.API_POST, url, data),

  // ── 安全存储 ────────────────────────────────────────────
  /** 安全存储密钥（加密后保存到磁盘） */
  keystoreSet: (key: string, value: string): Promise<{ success: boolean; error?: string }> =>
    ipcRenderer.invoke(IPC_CHANNELS.KEYSTORE_SET, key, value),

  /** 获取已安全存储的密钥 */
  keystoreGet: (key: string): Promise<{ success: boolean; value: string | null }> =>
    ipcRenderer.invoke(IPC_CHANNELS.KEYSTORE_GET, key),

  /** 删除已安全存储的密钥 */
  keystoreDelete: (key: string): Promise<{ success: boolean }> =>
    ipcRenderer.invoke(IPC_CHANNELS.KEYSTORE_DELETE, key),

  /** 检查密钥是否存在 */
  keystoreHas: (key: string): Promise<{ success: boolean; has: boolean }> =>
    ipcRenderer.invoke(IPC_CHANNELS.KEYSTORE_HAS, key),

  // ── 系统信息 ────────────────────────────────────────────
  /** 获取当前平台 */
  getPlatform: (): Promise<string> =>
    ipcRenderer.invoke(IPC_CHANNELS.GET_PLATFORM),

  /** 获取应用版本 */
  getAppVersion: (): Promise<string> =>
    ipcRenderer.invoke(IPC_CHANNELS.GET_APP_VERSION),

  /** 获取数据目录路径 */
  getDataDir: (): Promise<string> =>
    ipcRenderer.invoke(IPC_CHANNELS.GET_DATA_DIR),

  // ── 事件监听 ────────────────────────────────────────────
  /** 监听后端服务状态变化 */
  onBackendStatus: (callback: (status: { ready: boolean }) => void): void => {
    const handler = (_event: Electron.IpcRendererEvent, status: { ready: boolean }) => {
      callback(status);
    };
    ipcRenderer.on(IPC_CHANNELS.BACKEND_STATUS, handler);
  },

  /** 移除后端服务状态监听 */
  removeBackendStatusListener: (): void => {
    ipcRenderer.removeAllListeners(IPC_CHANNELS.BACKEND_STATUS);
  },
};

contextBridge.exposeInMainWorld('electronAPI', api);

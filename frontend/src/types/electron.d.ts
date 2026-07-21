/** Electron IPC 能力声明。 */

export interface ElectronAPI {
  // ── API 代理 ──
  /** 通过 IPC 发送 GET 请求到本地服务 */
  apiGet: <T>(url: string) => Promise<{ code: number; message: string; data?: T }>
  /** 通过 IPC 发送 POST 请求到本地服务 */
  apiPost: <T>(url: string, data?: unknown) => Promise<{ code: number; message: string; data?: T }>
  /** 通过 IPC 发送 PUT 请求到本地服务 */
  apiPut: <T>(url: string, data?: unknown) => Promise<{ code: number; message: string; data?: T }>
  /** 通过 IPC 发送 DELETE 请求到本地服务 */
  apiDelete: <T>(url: string) => Promise<{ code: number; message: string; data?: T }>

  // ── 安全存储 ──
  /** 安全存储密钥 */
  keystoreSet: (key: string, value: string) => Promise<{ success: boolean; error?: string }>
  /** 获取已安全存储的密钥 */
  keystoreGet: (key: string) => Promise<{ success: boolean; value: string | null }>
  /** 删除已安全存储的密钥 */
  keystoreDelete: (key: string) => Promise<{ success: boolean }>
  /** 检查密钥是否存在 */
  keystoreHas: (key: string) => Promise<{ success: boolean; has: boolean }>

  // ── 系统信息 ──
  /** 获取当前平台 */
  getPlatform: () => Promise<string>
  /** 获取应用版本 */
  getAppVersion: () => Promise<string>

  // ── 事件监听 ──
  /** 监听后端服务状态变化 */
  onBackendStatus: (callback: (status: { ready: boolean }) => void) => void
  /** 移除后端服务状态监听 */
  removeBackendStatusListener: () => void
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI
  }
}

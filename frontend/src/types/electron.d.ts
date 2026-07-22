/** Electron IPC 能力声明。 */

export interface ActivityCaptureStatus {
  running: boolean;
  pollIntervalMs: number;
  lastCaptureTime: string | null;
  lastAppName: string | null;
  eventsSubmitted: number;
  eventsSkipped: number;
  errors: number;
  accessibilityAvailable: boolean;
}

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
  /** 获取平台各能力状态（异步检测 macOS 权限） */
  getPlatformCapabilities: () => Promise<PlatformCapabilitiesResponse>

  // ── 活动采集控制（阶段 11） ──
  /** 启动活动采集 */
  startActivityCapture: () => Promise<{ success: boolean }>
  /** 停止活动采集 */
  stopActivityCapture: () => Promise<{ success: boolean }>
  /** 获取活动采集状态 */
  getActivityCaptureStatus: () => Promise<{
    success: boolean;
    status: ActivityCaptureStatus
  }>

  // ── 事件监听 ──
  /** 监听后端服务状态变化 */
  onBackendStatus: (callback: (status: { ready: boolean }) => void) => void
  /** 移除后端服务状态监听 */
  removeBackendStatusListener: () => void
}

/** 平台能力响应（与后端 schema 保持一致）。 */
export interface PlatformCapability {
  name: string;
  status: string;
  label: string;
  description: string | null;
}

export interface PlatformCapabilitiesResponse {
  platform: string;
  capabilities: PlatformCapability[];
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI
  }
}

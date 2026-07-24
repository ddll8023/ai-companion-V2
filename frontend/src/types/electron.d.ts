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

export interface ChatStreamRequest {
  sessionId: number;
  content: string;
  configId: number;
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

  // ── 安全存储（只写 + 存在检查，不可读取密钥值） ──
  /** 安全存储密钥（只写） */
  keystoreSet: (key: string, value: string) => Promise<{ success: boolean; error?: string }>
  /** 检查密钥是否存在 */
  keystoreHas: (key: string) => Promise<{ success: boolean; has: boolean }>

  // ── 安全对话（密钥由主进程注入） ──
  /**
   * 流式对话（密钥由主进程从 keystore 注入，Renderer 不接触密钥）。
   * 通过回调逐 token 推送，不再一次性返回。
   * @returns 清理函数，用于取消监听和停止流
   */
  streamChat: (
    data: ChatStreamRequest,
    callbacks: {
      onToken: (content: string) => void;
      onDone: (messageId: number | null) => void;
      onError: (message: string) => void;
    },
  ) => () => void

  // ── 安全模型操作（密钥由主进程注入） ──
  /** 测试模型连接（密钥由主进程从 keystore 注入） */
  testModelConnection: (configId: number) => Promise<{ success: boolean; message: string }>
  /** 清除模型密钥 */
  clearModelKey: (configId: number) => Promise<{ success: boolean }>

  // ── 系统信息 ──
  /** 获取当前平台 */
  getPlatform: () => Promise<string>
  /** 获取应用版本 */
  getAppVersion: () => Promise<string>
  /** 获取应用运行时状态 */
  getAppStatus: () => Promise<{
    electronVersion: string;
    nodeVersion: string;
    chromeVersion: string;
    appVersion: string;
    pid: number;
    platform: string;
    uptime: number;
  }>
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

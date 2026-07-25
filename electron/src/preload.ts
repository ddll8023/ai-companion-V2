/**
 * AI Companion — Preload 脚本
 *
 * 安全职责（按设计文档要求）：
 * - 只暴露受控白名单能力
 * - 不暴露通用 IPC 发送能力（不暴露 ipcRenderer.send）
 * - Renderer 无法获得端口、令牌、数据库路径和密钥明文
 *
 * 安全设计（重构后）：
 * - Renderer 只能写入密钥（keystoreSet），不可读取（keystoreGet 已删除）
 * - 敏感操作（对话、测试连接）通过专用 IPC 通道由主进程注入密钥
 * - Renderer 可查询密钥是否存在（keystoreHas），不可获取密钥值
 *
 * 新增（阶段 11）：
 * - 活动采集控制（start/stop/status）
 * - 平台能力实时检测（异步）
 */

import { contextBridge, ipcRenderer } from 'electron';

/** IPC 通道名称常量（与 main.ts 共享的定义一致，内联以避免沙盒 require 问题）。 */
const IPC_CHANNELS = {
  API_GET: 'api:get',
  API_POST: 'api:post',
  API_PUT: 'api:put',
  API_DELETE: 'api:delete',
  KEYSTORE_SET: 'keystore:set',
  KEYSTORE_GET: 'keystore:get',
  KEYSTORE_DELETE: 'keystore:delete',
  KEYSTORE_HAS: 'keystore:has',
  BACKEND_STATUS: 'backend-status',
  GET_PLATFORM: 'get-platform',
  GET_APP_VERSION: 'get-app-version',
  GET_APP_STATUS: 'get-app-status',
  GET_PLATFORM_CAPABILITIES: 'get-platform-capabilities',
  ACTIVITY_CAPTURE_START: 'activity-capture:start',
  ACTIVITY_CAPTURE_STOP: 'activity-capture:stop',
  ACTIVITY_CAPTURE_STATUS: 'activity-capture:status',
  CHAT_STREAM: 'chat:stream',
  CHAT_STREAM_EVENT: 'chat:stream-event',
  MODEL_TEST: 'model:test',
  MODEL_CLEAR_KEY: 'model:clear-key',
} as const;

// 保存监听器引用，实现精准移除（取代 removeAllListeners）
let _backendStatusHandler: ((_event: Electron.IpcRendererEvent, status: { ready: boolean }) => void) | null = null;

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

  /** 通过 IPC 发送 PUT 请求到本地服务 */
  apiPut: <T>(url: string, data?: unknown): Promise<{ code: number; message: string; data?: T }> =>
    ipcRenderer.invoke(IPC_CHANNELS.API_PUT, url, data),

  /** 通过 IPC 发送 DELETE 请求到本地服务 */
  apiDelete: <T>(url: string): Promise<{ code: number; message: string; data?: T }> =>
    ipcRenderer.invoke(IPC_CHANNELS.API_DELETE, url),

  // ── 安全存储（Render 只可写入和查询存在，不可读取密钥值） ──
  /** 安全存储密钥（加密后保存到磁盘）—— 只写，不可读回 */
  keystoreSet: (key: string, value: string): Promise<{ success: boolean; error?: string }> =>
    ipcRenderer.invoke(IPC_CHANNELS.KEYSTORE_SET, key, value),

  /** 检查密钥是否存在 */
  keystoreHas: (key: string): Promise<{ success: boolean; has: boolean }> =>
    ipcRenderer.invoke(IPC_CHANNELS.KEYSTORE_HAS, key),

  // keystoreGet / keystoreDelete 已移除：Renderer 不得获得密钥值
  // 密钥清除通过专用 IPC 通道 model:clear-key 实现

  // ── 安全对话 ──────────────────────────────────────────
  /**
   * 流式对话（密钥由主进程注入，Renderer 不持有密钥）。
   * 通过事件回调逐 token 推送，不再一次性返回。
   *
   * @returns 清理函数，用于取消监听和停止流
   */
  streamChat: (
    data: { sessionId: number; content: string; configId: number },
    callbacks: {
      onToken: (content: string) => void;
      onDone: (messageId: number | null) => void;
      onError: (message: string) => void;
    },
  ): (() => void) => {
    const handler = (_event: Electron.IpcRendererEvent, eventData: any) => {
      if (eventData.type === 'token' && eventData.content) {
        callbacks.onToken(eventData.content);
      } else if (eventData.type === 'done') {
        callbacks.onDone(eventData.message_id ?? null);
      } else if (eventData.type === 'error') {
        callbacks.onError(eventData.message || '对话生成失败');
      }
    };

    ipcRenderer.on(IPC_CHANNELS.CHAT_STREAM_EVENT, handler);
    ipcRenderer.send(IPC_CHANNELS.CHAT_STREAM, data);

    // 返回清理函数
    return () => {
      ipcRenderer.removeListener(IPC_CHANNELS.CHAT_STREAM_EVENT, handler);
    };
  },

  // ── 安全模型操作 ─────────────────────────────────────
  /** 测试模型连接（密钥由主进程注入） */
  testModelConnection: (configId: number): Promise<{
    success: boolean;
    message: string;
  }> => ipcRenderer.invoke(IPC_CHANNELS.MODEL_TEST, configId),

  /** 清除模型密钥（通过 configId 删除安全存储中的对应密钥） */
  clearModelKey: (configId: number): Promise<{ success: boolean }> =>
    ipcRenderer.invoke(IPC_CHANNELS.MODEL_CLEAR_KEY, configId),

  // ── 系统信息 ────────────────────────────────────────────
  /** 获取当前平台 */
  getPlatform: (): Promise<string> =>
    ipcRenderer.invoke(IPC_CHANNELS.GET_PLATFORM),

  /** 获取应用版本 */
  getAppVersion: (): Promise<string> =>
    ipcRenderer.invoke(IPC_CHANNELS.GET_APP_VERSION),

  /** 获取 Electron 运行时状态（PID、版本、运行时长等） */
  getAppStatus: (): Promise<{
    electronVersion: string;
    nodeVersion: string;
    chromeVersion: string;
    appVersion: string;
    pid: number;
    platform: string;
    uptime: number;
  }> => ipcRenderer.invoke(IPC_CHANNELS.GET_APP_STATUS),

  /** 获取平台各能力状态（异步检测 macOS 权限） */
  getPlatformCapabilities: (): Promise<{
    platform: string;
    capabilities: Array<{
      name: string;
      status: string;
      label: string;
      description: string | null;
    }>;
  }> => ipcRenderer.invoke(IPC_CHANNELS.GET_PLATFORM_CAPABILITIES),

  // ── 活动采集控制（阶段 11） ───────────────────────────
  /** 启动活动采集 */
  startActivityCapture: (): Promise<{ success: boolean }> =>
    ipcRenderer.invoke(IPC_CHANNELS.ACTIVITY_CAPTURE_START),

  /** 停止活动采集 */
  stopActivityCapture: (): Promise<{ success: boolean }> =>
    ipcRenderer.invoke(IPC_CHANNELS.ACTIVITY_CAPTURE_STOP),

  /** 获取活动采集状态 */
  getActivityCaptureStatus: (): Promise<{
    success: boolean;
    status: {
      running: boolean;
      pollIntervalMs: number;
      lastCaptureTime: string | null;
      lastAppName: string | null;
      eventsSubmitted: number;
      eventsSkipped: number;
      errors: number;
      accessibilityAvailable: boolean;
    };
  }> => ipcRenderer.invoke(IPC_CHANNELS.ACTIVITY_CAPTURE_STATUS),

  // ── 事件监听 ────────────────────────────────────────────
  /** 监听后端服务状态变化 */
  onBackendStatus: (callback: (status: { ready: boolean }) => void): void => {
    // 先移除上一个监听器（确保不累积）
    if (_backendStatusHandler) {
      ipcRenderer.removeListener(IPC_CHANNELS.BACKEND_STATUS, _backendStatusHandler);
    }
    _backendStatusHandler = (_event: Electron.IpcRendererEvent, status: { ready: boolean }) => {
      callback(status);
    };
    ipcRenderer.on(IPC_CHANNELS.BACKEND_STATUS, _backendStatusHandler);
  },

  /** 移除后端服务状态监听 */
  removeBackendStatusListener: (): void => {
    if (_backendStatusHandler) {
      ipcRenderer.removeListener(IPC_CHANNELS.BACKEND_STATUS, _backendStatusHandler);
      _backendStatusHandler = null;
    }
  },
};

contextBridge.exposeInMainWorld('electronAPI', api);

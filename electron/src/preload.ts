/**
 * AI Companion — Preload 脚本
 *
 * 安全职责（按设计文档要求）：
 * - 只暴露受控白名单能力
 * - 不暴露通用 IPC 发送能力（不暴露 ipcRenderer.send）
 * - Renderer 无法获得端口、令牌、数据库路径和密钥明文
 *
 * 新增（阶段 11）：
 * - 活动采集控制（start/stop/status）
 * - 平台能力实时检测（异步）
 */

import { contextBridge, ipcRenderer } from 'electron';
import { IPC_CHANNELS } from './constants/channels';

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

  /** 获取 Electron 运行时状态（PID、版本、运行时长等） */
  getAppStatus: (): Promise<{
    electronVersion: string;
    nodeVersion: string;
    chromeVersion: string;
    appVersion: string;
    pid: number;
    platform: string;
    appPath: string;
    userDataPath: string;
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

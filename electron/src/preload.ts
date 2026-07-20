import { contextBridge, ipcRenderer } from 'electron';

/**
 * 受控白名单能力。
 * Renderer 只能通过此接口调用指定的桌面能力。
 * 不得暴露通用 IPC 发送能力。
 */
const api = {
  // 系统信息
  getPlatform: (): string => process.platform,

  // 运行时状态
  getAppVersion: (): string => process.env.npm_package_version || '0.1.0',
};

contextBridge.exposeInMainWorld('electronAPI', api);

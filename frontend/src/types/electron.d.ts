/** Electron IPC 能力声明。 */

export interface ElectronAPI {
  /** 获取当前平台 */
  getPlatform: () => string
  /** 获取应用版本 */
  getAppVersion: () => string
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI
  }
}

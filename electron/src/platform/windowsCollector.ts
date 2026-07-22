/**
 * Windows 活动采集适配器（占位实现）。
 *
 * 阶段 12 完成具体实现，当前返回 NOT_IMPLEMENTED 状态。
 * 确保 ActivityCaptureManager 在 Windows 上不会因平台检测错误而崩溃，
 * 同时通过清晰的能力状态告知用户当前平台支持情况。
 *
 * 注意：平台选择由 activityCapture.ts 中的 getActivityCaptureManager 自动处理，
 *       不要在本模块中动态引入 macOSCollector，避免交叉依赖。
 */

import { ActivityPlatformAdapter, FrontmostAppInfo, IdleTimeInfo } from '../services/activityPlatform';
import { PermissionState, PermissionStatusType, PermissionStatus, PermissionNames } from '../constants/platform';

export class WindowsCollector implements ActivityPlatformAdapter {
  async getFrontmostAppInfo(): Promise<FrontmostAppInfo> {
    return {
      appName: '',
      windowTitle: null,
      success: false,
      error: 'Windows 活动采集尚未实现',
    };
  }

  async getFrontmostAppName(): Promise<string | null> {
    return null;
  }

  async getIdleTime(): Promise<IdleTimeInfo> {
    return { idleSeconds: 0, success: false, error: 'Windows 活动采集尚未实现' };
  }

  async checkAccessibilityPermission(): Promise<PermissionStatusType> {
    return PermissionStatus.NOT_IMPLEMENTED;
  }

  async getAllCapabilities(): Promise<PermissionState[]> {
    // 与 platform.ts 中 getWindowsCapabilities 一致的返回值
    return [
      {
        name: PermissionNames.ACTIVITY_CAPTURE,
        status: PermissionStatus.NOT_IMPLEMENTED,
        label: '活动采集',
        description: '采集前台应用和窗口信息',
      },
      {
        name: PermissionNames.ACCESSIBILITY,
        status: PermissionStatus.NOT_IMPLEMENTED,
        label: '辅助功能',
        description: '获取前台应用和窗口标题',
      },
      {
        name: PermissionNames.INPUT_MONITORING,
        status: PermissionStatus.NOT_IMPLEMENTED,
        label: '输入监控',
        description: '监控键盘输入事件',
      },
      {
        name: PermissionNames.SCREEN_RECORDING,
        status: PermissionStatus.NOT_IMPLEMENTED,
        label: '屏幕录制',
        description: '屏幕截图和录制',
      },
      {
        name: PermissionNames.NOTIFICATION,
        status: PermissionStatus.AVAILABLE,
        label: '系统通知',
        description: '发送桌面通知',
      },
      {
        name: PermissionNames.AUTOMATION,
        status: PermissionStatus.NOT_IMPLEMENTED,
        label: '自动化',
        description: '控制其他应用',
      },
    ];
  }
}

/** 单例引用。 */
let _instance: WindowsCollector | null = null;

/**
 * 获取 Windows 采集适配器单例。
 */
export function getWindowsCollector(): WindowsCollector {
  if (!_instance) {
    _instance = new WindowsCollector();
  }
  return _instance;
}

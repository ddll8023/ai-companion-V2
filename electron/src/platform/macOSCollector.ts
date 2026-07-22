/**
 * macOS 活动采集适配器实现。
 *
 * 实现 ActivityPlatformAdapter 接口，
 * 将 macOSActivity.ts 中的独立函数封装为统一的平台采集接口。
 */

import { ActivityPlatformAdapter, FrontmostAppInfo, IdleTimeInfo } from '../services/activityPlatform';
import { PermissionState, PermissionStatusType } from '../constants/platform';
import {
  getFrontmostAppInfo as macOSGetFrontmostAppInfo,
  getFrontmostAppName as macOSGetFrontmostAppName,
  getIdleTime as macOSGetIdleTime,
  checkAccessibilityPermission as macOSCheckAccessibility,
  getAllMacOSCapabilities,
} from './macOSActivity';

export class MacOSCollector implements ActivityPlatformAdapter {
  async getFrontmostAppInfo(): Promise<FrontmostAppInfo> {
    return macOSGetFrontmostAppInfo();
  }

  async getFrontmostAppName(): Promise<string | null> {
    return macOSGetFrontmostAppName();
  }

  async getIdleTime(): Promise<IdleTimeInfo> {
    return macOSGetIdleTime();
  }

  async checkAccessibilityPermission(): Promise<PermissionStatusType> {
    return macOSCheckAccessibility();
  }

  async getAllCapabilities(): Promise<PermissionState[]> {
    // 类型兼容：getAllMacOSCapabilities 返回的结构与 PermissionState 一致
    return (await getAllMacOSCapabilities()) as unknown as PermissionState[];
  }
}

/** 单例引用。 */
let _instance: MacOSCollector | null = null;

/**
 * 获取 macOS 采集适配器单例。
 */
export function getMacOSCollector(): MacOSCollector {
  if (!_instance) {
    _instance = new MacOSCollector();
  }
  return _instance;
}

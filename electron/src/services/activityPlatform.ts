/**
 * 平台活动采集适配器接口与类型定义。
 *
 * macOS 和 Windows 分别实现此接口，
 * ActivityCaptureManager 通过接口调用平台能力，不感知具体平台差异。
 *
 * 设计原则：
 * - 差异只存在于 Electron 平台适配层（platform/ 目录）
 * - 业务层（services/）和 IPC 层不散落平台判断
 */

import { PermissionState, PermissionStatusType } from '../constants/platform';

/** 前台应用信息。 */
export interface FrontmostAppInfo {
  /** 应用名称（如 "Google Chrome"） */
  appName: string;
  /** 窗口标题（获取失败或无权限时为 null） */
  windowTitle: string | null;
  /** 获取是否成功 */
  success: boolean;
  /** 错误信息 */
  error: string | null;
}

/**
 * 平台活动采集适配器接口。
 *
 * 每个平台（macOS / Windows）各自实现此接口，
 * ActivityCaptureManager 通过此接口调用平台能力。
 */
export interface ActivityPlatformAdapter {
  /** 获取前台应用信息（名称 + 窗口标题）。 */
  getFrontmostAppInfo(): Promise<FrontmostAppInfo>;

  /** 仅获取前台应用名称（降级场景，无需窗口标题权限）。 */
  getFrontmostAppName(): Promise<string | null>;

  /** 检测当前平台 Accessibility 权限状态。 */
  checkAccessibilityPermission(): Promise<PermissionStatusType>;

  /** 获取当前平台独有的所有权限能力状态。 */
  getAllCapabilities(): Promise<PermissionState[]>;
}

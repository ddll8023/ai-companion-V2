/**
 * 跨平台能力定义（单一来源）。
 *
 * 统一 macOS 和 Windows 的基础能力差异表达。
 * 所有需要能力默认值的模块统一从此文件导入，不再各自定义。
 */

import { PermissionNames, PermissionStatus, type PermissionState, type PlatformType, getPlatform } from './platform';

/**
 * 获取当前平台的基础能力列表。
 * 不包含实时权限检测（仅返回项目规划中的能力状态）。
 *
 * @param platform 可选平台参数，不传时自动检测
 * @returns 能力状态列表
 */
export function getBaseCapabilities(platform: PlatformType = getPlatform()): PermissionState[] {
  const isMac = platform === 'macos';

  return [
    {
      name: PermissionNames.ACTIVITY_CAPTURE,
      status: isMac ? PermissionStatus.AVAILABLE : PermissionStatus.NOT_IMPLEMENTED,
      label: '活动采集',
      description: '采集前台应用和窗口信息',
    },
    {
      name: PermissionNames.ACCESSIBILITY,
      status: isMac ? PermissionStatus.PENDING_AUTH : PermissionStatus.NOT_IMPLEMENTED,
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

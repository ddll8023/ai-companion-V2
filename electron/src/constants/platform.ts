/**
 * 跨平台系统适配模块 - 平台能力与权限枚举。
 *
 * 统一 Windows 和 macOS 的系统能力差异表达。
 * 每项能力独立管理，不共用笼统的「系统权限」状态。
 */

/** 权限状态枚举（与设计文档一致）。 */
export const PermissionStatus = {
  /** 平台支持且已授权 */
  AVAILABLE: 'available' as const,
  /** 平台支持但用户尚未授权 */
  PENDING_AUTH: 'pending_auth' as const,
  /** 用户明确拒绝 */
  DENIED: 'denied' as const,
  /** 受系统策略或企业策略限制 */
  RESTRICTED: 'restricted' as const,
  /** 当前平台无法提供 */
  UNSUPPORTED: 'unsupported' as const,
  /** 产品暂未接入该能力 */
  NOT_IMPLEMENTED: 'not_implemented' as const,
} as const;

export type PermissionStatusType = (typeof PermissionStatus)[keyof typeof PermissionStatus];

/** 权限能力名称枚举。 */
export const PermissionNames = {
  /** 桌面活动采集 */
  ACTIVITY_CAPTURE: 'activity_capture' as const,
  /** 辅助功能（Accessibility API） */
  ACCESSIBILITY: 'accessibility' as const,
  /** 输入监控 */
  INPUT_MONITORING: 'input_monitoring' as const,
  /** 屏幕录制权限 */
  SCREEN_RECORDING: 'screen_recording' as const,
  /** 系统通知 */
  NOTIFICATION: 'notification' as const,
  /** 自动化权限 */
  AUTOMATION: 'automation' as const,
} as const;

export type PermissionName = (typeof PermissionNames)[keyof typeof PermissionNames];

/** 平台类型。 */
export type PlatformType = 'macos' | 'windows';

/** 单项权限及其详细状态。 */
export interface PermissionState {
  name: PermissionName;
  status: PermissionStatusType;
  label: string;
  description: string | null;
}

/** 平台能力列表响应（与后端 schema 保持一致）。 */
export interface PlatformCapabilitiesResponse {
  platform: string;
  capabilities: PermissionState[];
}

/**
 * 获取当前平台。
 * 在 Electron Main 和 Preload 中均可使用。
 */
export function getPlatform(): PlatformType {
  return process.platform === 'darwin' ? 'macos' : 'windows';
}

/**
 * 获取当前平台支持的能力列表（基础实现，不含实际权限检测）。
 * macOS 和 Windows 的具体权限检测在阶段 11/12 中分别实现。
 */
export function getSupportedCapabilities(): PermissionState[] {
  const platform = getPlatform();

  return [
    {
      name: PermissionNames.ACTIVITY_CAPTURE,
      status: PermissionStatus.NOT_IMPLEMENTED,
      label: '活动采集',
      description: '采集前台应用和窗口信息',
    },
    {
      name: PermissionNames.ACCESSIBILITY,
      status: platform === 'macos' ? PermissionStatus.PENDING_AUTH : PermissionStatus.NOT_IMPLEMENTED,
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

/**
 * 获取所有权限状态的简化映射（key: name → status）。
 * 用于快速判断某个权限是否可用。
 */
export function getCapabilityMap(): Record<PermissionName, PermissionStatusType> {
  const caps = getSupportedCapabilities();
  const map: Record<string, PermissionStatusType> = {};
  for (const cap of caps) {
    map[cap.name] = cap.status;
  }
  return map as Record<PermissionName, PermissionStatusType>;
}

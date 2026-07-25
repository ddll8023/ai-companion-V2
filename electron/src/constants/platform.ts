/**
 * 跨平台系统适配模块 - 平台能力与权限枚举。
 *
 * 统一 Windows 和 macOS 的系统能力差异表达。
 * 每项能力独立管理，不共用笼统的「系统权限」状态。
 *
 * macOS 下，能力检测会实时调用系统 API 判断权限状态。
 */

import { getBaseCapabilities } from './capabilities';

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
 * macOS 权限检测的结果缓存。
 * 避免每次调用都执行 osascript，减少延迟。
 */
let _capabilityCache: PermissionState[] | null = null;
let _cacheTimestamp = 0;
const CACHE_TTL_MS = 30000; // 30 秒缓存

/**
 * 清除能力状态缓存。
 * 当用户可能已修改系统权限时调用（如当前台窗口变化后）。
 */
export function clearCapabilityCache(): void {
  _capabilityCache = null;
  _cacheTimestamp = 0;
}

/**
 * 获取当前平台支持的能力列表（含实际权限检测）。
 *
 * macOS：通过 osascript 检测 Accessibility 等权限的真实状态。
 * Windows：返回基础能力定义（阶段 12 完成具体检测）。
 *
 * 缓存 30 秒以减少重复的系统调用。
 */
export async function getPlatformCapabilities(): Promise<PermissionState[]> {
  const platform = getPlatform();
  const now = Date.now();

  // 缓存有效期内直接返回
  if (_capabilityCache && (now - _cacheTimestamp) < CACHE_TTL_MS) {
    return _capabilityCache;
  }

  let capabilities: PermissionState[];

  if (platform === 'macos') {
    // macOS 下实时检测权限状态
    capabilities = await getMacOSCapabilities();
  } else {
    // Windows 返回基础定义（阶段 12 实现真实检测）
    capabilities = getBaseCapabilities('windows');
  }

  // 更新缓存
  _capabilityCache = capabilities;
  _cacheTimestamp = now;

  return capabilities;
}

/**
 * 获取所有权限状态的简化映射（key: name → status）。
 * 同步版本，使用缓存或默认值。
 */
export function getCapabilityMap(): Record<PermissionName, PermissionStatusType> {
  const caps = _capabilityCache || getBaseCapabilities();
  const map: Record<string, PermissionStatusType> = {};
  for (const cap of caps) {
    map[cap.name] = cap.status;
  }
  return map as Record<PermissionName, PermissionStatusType>;
}

/**
 * 获取 macOS 的实时权限状态。
 * 通过动态导入 macOSActivity 模块来避免在非 macOS 平台上引入依赖。
 */
async function getMacOSCapabilities(): Promise<PermissionState[]> {
  try {
    const { getAllMacOSCapabilities } = await import(
      /* webpackIgnore: true */
      '../platform/macOSActivity'
    );
    const capabilities = await getAllMacOSCapabilities();
    return capabilities as PermissionState[];
  } catch {
    // 动态导入失败时返回默认值
    console.warn('[Platform] macOS 权限检测模块加载失败，使用默认值');
    return getBaseCapabilities();
  }
}

/** 导出基础能力查询函数，供外部模块统一使用 */


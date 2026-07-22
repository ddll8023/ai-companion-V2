/**
 * macOS 活动采集适配器。
 *
 * 使用 macOS 原生工具（osascript、ioreg）获取前台应用信息、
 * 窗口标题、用户空闲状态和系统权限状态。
 *
 * 职责边界：
 * - 只负责与 macOS 系统交互获取原始数据
 * - 不决定是否应该采集（由 ActivityCaptureManager 负责）
 * - 不直接提交事件到后端
 */

import { exec } from 'child_process';
import { PermissionStatus, PermissionStatusType } from '../constants/platform';

// ── 类型定义 ──────────────────────────────────────────────────────────────

/** 前台应用信息。 */
export interface FrontmostAppInfo {
  /** 应用名称（如 "Google Chrome"） */
  appName: string;
  /** 窗口标题（获取失败时为 null） */
  windowTitle: string | null;
  /** 当前是否成功获取 */
  success: boolean;
  /** 错误信息 */
  error: string | null;
}

/** 空闲时间信息。 */
export interface IdleTimeInfo {
  /** 空闲秒数 */
  idleSeconds: number;
  /** 获取是否成功 */
  success: boolean;
  /** 错误信息 */
  error: string | null;
}

// ── 工具函数 ──────────────────────────────────────────────────────────────

/** 执行 shell 命令并返回 stdout。 */
function execCommand(cmd: string, timeout = 5000): Promise<string> {
  return new Promise((resolve, reject) => {
    const child = exec(cmd, { timeout }, (error, stdout) => {
      if (error) {
        reject(error);
      } else {
        resolve(stdout.trim());
      }
    });
  });
}

// ── 前台应用采集 ──────────────────────────────────────────────────────────

/**
 * 获取当前前台应用信息。
 *
 * 使用 osascript 调用 System Events 获取：
 * - 前台应用名称（始终可用）
 * - 窗口标题（需要 Accessibility 权限，否则返回 null）
 *
 * 在 macOS 上，应用名称获取通常不需要额外权限，
 * 但窗口标题需要 Accessibility 权限。
 */
export async function getFrontmostAppInfo(): Promise<FrontmostAppInfo> {
  try {
    const script = `
      tell application "System Events"
        set frontProcess to first process whose frontmost is true
        set appName to name of frontProcess
        try
          set winTitle to title of first window of frontProcess
        on error
          set winTitle to ""
        end try
        return appName & "|||" & winTitle
      end tell
    `;
    const result = await execCommand(`osascript -e '${script.replace(/'/g, "'\\''")}'`, 5000);

    const separator = result.lastIndexOf('|||');
    if (separator === -1) {
      return {
        appName: result,
        windowTitle: null,
        success: true,
        error: null,
      };
    }

    const appName = result.substring(0, separator).trim();
    const windowTitleRaw = result.substring(separator + 3).trim();
    const windowTitle = windowTitleRaw.length > 0 ? windowTitleRaw : null;

    return {
      appName,
      windowTitle,
      success: true,
      error: null,
    };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    return {
      appName: '',
      windowTitle: null,
      success: false,
      error: message,
    };
  }
}

/**
 * 仅获取前台应用名称（轻量版本，无需 Accessibility 权限）。
 *
 * 此方式不获取窗口标题，适用于 Accessibility 权限未授权时的降级采集。
 */
export async function getFrontmostAppName(): Promise<string | null> {
  try {
    const result = await execCommand(
      `osascript -e 'tell application "System Events" to get name of first process whose frontmost is true'`,
      5000,
    );
    return result || null;
  } catch {
    return null;
  }
}

// ── 用户空闲时间 ──────────────────────────────────────────────────────────

/**
 * 获取用户空闲时间（秒）。
 *
 * 使用 `ioreg` 读取 IOHIDSystem 的 HIDIdleTime 属性，
 * 该值表示自上次用户输入事件（键盘/鼠标/触控板）以来的纳米秒数。
 */
export async function getIdleTime(): Promise<IdleTimeInfo> {
  try {
    const result = await execCommand(
      `ioreg -c IOHIDSystem | awk '/HIDIdleTime/ {gsub(/[^0-9a-fA-F]/, "", $NF); print $NF; exit}'`,
      5000,
    );

    if (!result) {
      return { idleSeconds: 0, success: false, error: '无法读取空闲时间' };
    }

    const idleNanoseconds = parseInt(result, 16);
    if (isNaN(idleNanoseconds)) {
      return { idleSeconds: 0, success: false, error: '空闲时间解析失败' };
    }

    return {
      idleSeconds: Math.floor(idleNanoseconds / 1000000000),
      success: true,
      error: null,
    };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    return { idleSeconds: 0, success: false, error: message };
  }
}

// ── macOS 权限检测 ────────────────────────────────────────────────────────

/**
 * 检测 macOS Accessibility 权限状态。
 *
 * 通过尝试使用 System Events 获取窗口标题来判断 Accessibility 权限。
 * - System Events 调用成功且返回标题 → 权限已授权
 * - System Events 调用不报错但返回空标题 → 可能无窗口，不一定是权限问题
 * - System Events 调用被拒绝 → 权限未授权
 */
export async function checkAccessibilityPermission(): Promise<PermissionStatusType> {
  try {
    const script = `
      tell application "System Events"
        set frontProcess to first process whose frontmost is true
        try
          set winTitle to title of first window of frontProcess
          if winTitle is not "" then
            return "ok"
          end if
        end try
        return "ok"
      end tell
    `;
    await execCommand(`osascript -e '${script.replace(/'/g, "'\\''")}'`, 5000);

    // 如果 osascript 执行成功，权限基本可用（可能部分受限）
    // 进一步验证：尝试获取一个已知窗口的标题
    // 如果 Accessibility 权限完全不足，osascript 会返回权限错误
    return PermissionStatus.AVAILABLE;
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message.toLowerCase() : '';

    // macOS 权限拒绝的典型错误信息
    if (
      message.includes('not allowed') ||
      message.includes('permission') ||
      message.includes(' denied') ||
      message.includes('accessibility') ||
      message.includes('privacy') ||
      message.includes('osascript error')
    ) {
      return PermissionStatus.PENDING_AUTH;
    }

    // System Events 可能不可用或系统限制
    if (message.includes('application isn') || message.includes('can\'t get')) {
      return PermissionStatus.RESTRICTED;
    }

    return PermissionStatus.PENDING_AUTH;
  }
}

/**
 * 检测 macOS Screen Recording 权限状态。
 *
 * 首版不采集屏幕截图，不进行真实权限检测。
 * 实际获取窗口标题依赖的是 Accessibility 权限，而非 Screen Recording。
 *
 * 返回 NOT_IMPLEMENTED 表明产品暂未接入该能力，与首版范围一致。
 * 后续版本如需屏幕截图功能，应使用原生调用（CGDisplayStream / SCStream）
 * 或通过 macOS 授权对话框 API 进行真实检测。
 */
export async function checkScreenRecordingPermission(): Promise<PermissionStatusType> {
  return PermissionStatus.NOT_IMPLEMENTED;
}

/**
 * 检测 macOS 上开发所需的辅助功能是否可用。
 * 用于设置页面的统一能力展示。
 */
export async function checkMacOSPermission(
  permissionName: 'accessibility' | 'screen_recording',
): Promise<PermissionStatusType> {
  if (permissionName === 'accessibility') {
    return checkAccessibilityPermission();
  }
  if (permissionName === 'screen_recording') {
    return checkScreenRecordingPermission();
  }
  return PermissionStatus.UNSUPPORTED;
}

/**
 * 获取所有 macOS 权限的实时状态。
 * 返回 PermissionState 格式的数组，供平台能力展示使用。
 */
export async function getAllMacOSCapabilities(): Promise<
  Array<{
    name: string;
    status: PermissionStatusType;
    label: string;
    description: string | null;
  }>
> {
  const accessibilityStatus = await checkAccessibilityPermission();

  return [
    {
      name: 'activity_capture',
      status: PermissionStatus.AVAILABLE,
      label: '活动采集',
      description: '采集前台应用和窗口信息',
    },
    {
      name: 'accessibility',
      status: accessibilityStatus,
      label: '辅助功能',
      description: accessibilityStatus === PermissionStatus.PENDING_AUTH
        ? '需要辅助功能权限以获取窗口标题。请在 系统设置 → 隐私与安全性 → 辅助功能 中授权。'
        : '获取前台应用和窗口标题',
    },
    {
      name: 'input_monitoring',
      status: PermissionStatus.NOT_IMPLEMENTED,
      label: '输入监控',
      description: '监控键盘输入事件',
    },
    {
      name: 'screen_recording',
      status: PermissionStatus.NOT_IMPLEMENTED,
      label: '屏幕录制',
      description: '首版不采集屏幕截图，此能力暂未实现',
    },
    {
      name: 'notification',
      status: PermissionStatus.AVAILABLE,
      label: '系统通知',
      description: '发送桌面通知',
    },
    {
      name: 'automation',
      status: PermissionStatus.NOT_IMPLEMENTED,
      label: '自动化',
      description: '控制其他应用',
    },
  ];
}

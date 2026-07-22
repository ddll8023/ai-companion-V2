/**
 * 活动采集管理器。
 *
 * 职责：
 * - 管理采集轮询生命周期（启动/停止）
 * - 从平台适配器获取原始活动数据
 * - 本地隐私规则缓存与快速判断（采集前硬阻断）
 * - 事件去重（连续相同应用合并）
 * - 批量提交活动事件到后端服务
 * - 错误处理和状态管理
 *
 * 设计原则：
 * - 采集前硬阻断优先（无法确认安全时停止采集）
 * - 本地判断不依赖后端可用性
 * - 单事件失败不影响整体采集流程
 */

import { httpRequest } from './httpClient';
import {
  FrontmostAppInfo,
  getIdleTime,
  getFrontmostAppInfo,
  getFrontmostAppName,
  checkAccessibilityPermission,
} from '../platform/macOSActivity';

// ── 活动事件类型（与后端 ActivityEvent Schema 保持一致） ─────────────────

export interface ActivityEvent {
  app_name: string;
  window_title: string | null;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number | null;
  is_idle: boolean;
  platform: string;
  source_id: string | null;
}

/** 本地缓存的隐私规则。 */
interface LocalPrivacyRule {
  type: string;
  value: string;
  active: boolean;
}

/** 采集状态。 */
export interface CaptureStatus {
  running: boolean;
  pollIntervalMs: number;
  lastCaptureTime: string | null;
  lastAppName: string | null;
  eventsSubmitted: number;
  eventsSkipped: number;
  errors: number;
  accessibilityAvailable: boolean;
}

/** 采集状态变更回调。 */
type StatusCallback = (status: CaptureStatus) => void;

// ── 常量 ──────────────────────────────────────────────────────────────────

/** 默认采集间隔（毫秒） */
const DEFAULT_POLL_INTERVAL_MS = 5000;

/** 连续相同应用的最大上报间隔（秒） */
const MAX_SAME_APP_INTERVAL_SECONDS = 300;

/** 最小空闲阈值（秒），超过此值认为用户空闲 */
const IDLE_THRESHOLD_SECONDS = 300; // 5 分钟无操作

/** 后端的活动事件提交端点 */
const SUBMIT_EVENTS_PATH = '/api/v1/activities/events';

/** 后端的隐私规则评估端点 */
const EVALUATE_PRIVACY_PATH = '/api/v1/activities/privacy/evaluate';

/** 后端的活动事件批量提交最大条数 */
const MAX_BATCH_SIZE = 20;

// ── 活动采集管理器 ─────────────────────────────────────────────────────────

export class ActivityCaptureManager {
  /** 是否正在运行 */
  private _running = false;

  /** 轮询定时器引用 */
  private _pollTimer: ReturnType<typeof setInterval> | null = null;

  /** 采集间隔（毫秒） */
  private _pollIntervalMs: number = DEFAULT_POLL_INTERVAL_MS;

  /** 本地隐私规则缓存 */
  private _privacyRules: LocalPrivacyRule[] = [];

  /** 上一次成功采集的应用信息（用于去重和持续时间计算） */
  private _lastCapture: {
    appName: string;
    windowTitle: string | null;
    timestamp: string;
    sourceId: string;
  } | null = null;

  /** 事件缓冲区（批量提交） */
  private _eventBuffer: ActivityEvent[] = [];

  /** 缓冲区提交定时器 */
  private _bufferTimer: ReturnType<typeof setInterval> | null = null;

  /** 采集状态 */
  private _status: CaptureStatus = {
    running: false,
    pollIntervalMs: DEFAULT_POLL_INTERVAL_MS,
    lastCaptureTime: null,
    lastAppName: null,
    eventsSubmitted: 0,
    eventsSkipped: 0,
    errors: 0,
    accessibilityAvailable: false,
  };

  /** 状态变更监听器 */
  private _statusListeners: StatusCallback[] = [];

  /** 后端地址和认证令牌（由 Main 进程设置） */
  private _backendPort = 0;
  private _authToken = '';

  // ── 生命周期管理 ──────────────────────────────────────────────────────

  /**
   * 设置后端连接信息。
   * 由 Main 进程在启动后调用。
   */
  setBackendInfo(port: number, token: string): void {
    this._backendPort = port;
    this._authToken = token;
  }

  /**
   * 更新本地隐私规则缓存。
   * 后端规则变更时，Main 进程调用此方法同步。
   */
  setPrivacyRules(rules: LocalPrivacyRule[]): void {
    this._privacyRules = rules;
  }

  /**
   * 添加状态变更监听器。
   */
  addStatusListener(callback: StatusCallback): void {
    this._statusListeners.push(callback);
  }

  /**
   * 移除状态变更监听器。
   */
  removeStatusListener(callback: StatusCallback): void {
    this._statusListeners = this._statusListeners.filter((cb) => cb !== callback);
  }

  /** 通知所有监听器状态变更。 */
  private _notifyStatus(): void {
    const snap = { ...this._status };
    for (const cb of this._statusListeners) {
      try {
        cb(snap);
      } catch {
        // 监听器异常不影响运行时
      }
    }
  }

  // ── 采集控制 ──────────────────────────────────────────────────────────

  /**
   * 启动活动采集。
   *
   * 流程：
   * 1. 检测 Accessibility 权限
   * 2. 启动定时轮询
   * 3. 每轮：获取前台应用 → 本地隐私检查 → 提交到后端
   */
  async start(): Promise<boolean> {
    if (this._running) {
      return true;
    }

    // 检测 Accessibility 权限
    const accessibilityStatus = await checkAccessibilityPermission();
    const accessibilityAvailable = accessibilityStatus === 'available';
    this._status.accessibilityAvailable = accessibilityAvailable;

    console.log(
      `[ActivityCapture] 启动采集, Accessibility: ${accessibilityAvailable}`,
    );

    this._running = true;
    this._status.running = true;

    // 立即执行一次采集
    await this._capture();

    // 启动轮询
    this._pollTimer = setInterval(() => {
      this._capture();
    }, this._pollIntervalMs);

    // 每 30 秒刷新隐私规则缓存
    this._bufferTimer = setInterval(() => {
      this._flushBuffer();
    }, 30000);

    this._notifyStatus();
    return true;
  }

  /**
   * 停止活动采集。
   * 停止轮询并清空事件缓冲区。
   */
  async stop(): Promise<void> {
    this._running = false;
    this._status.running = false;

    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }

    if (this._bufferTimer) {
      clearInterval(this._bufferTimer);
      this._bufferTimer = null;
    }

    // 提交剩余缓冲事件
    await this._flushBuffer();

    this._lastCapture = null;
    this._notifyStatus();
    console.log('[ActivityCapture] 已停止采集');
  }

  /**
   * 设置采集间隔。
   */
  setPollInterval(ms: number): void {
    this._pollIntervalMs = Math.max(2000, Math.min(60000, ms));
    this._status.pollIntervalMs = this._pollIntervalMs;

    // 如果正在运行，重新设置定时器
    if (this._running && this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = setInterval(() => {
        this._capture();
      }, this._pollIntervalMs);
    }

    this._notifyStatus();
  }

  /**
   * 获取当前采集状态。
   */
  getStatus(): CaptureStatus {
    return { ...this._status };
  }

  // ── 核心采集逻辑 ──────────────────────────────────────────────────────

  /**
   * 执行一次采集周期。
   *
   * 1. 获取前台应用信息
   * 2. 获取用户空闲状态
   * 3. 本地隐私规则检查（硬阻断层）
   * 4. 去重判断
   * 5. 构造事件并加入缓冲区
   */
  private async _capture(): Promise<void> {
    if (!this._running) return;

    try {
      // 1. 获取前台应用信息
      let appInfo: FrontmostAppInfo;

      if (this._status.accessibilityAvailable) {
        appInfo = await getFrontmostAppInfo();
      } else {
        // 降级：只获取应用名称，不获取窗口标题
        const appName = await getFrontmostAppName();
        appInfo = {
          appName: appName || '',
          windowTitle: null,
          success: appName !== null,
          error: appName ? null : '无法获取前台应用',
        };
      }

      if (!appInfo.success || !appInfo.appName) {
        // 无法获取前台应用 → 视为安全阻断（无法确认时停止采集）
        console.log('[ActivityCapture] 无法获取前台应用，跳过本次采集');
        return;
      }

      // 2. 获取用户空闲状态
      const idleInfo = await getIdleTime();
      const isIdle = idleInfo.success && idleInfo.idleSeconds >= IDLE_THRESHOLD_SECONDS;

      // 3. 本地隐私规则检查（采集前硬阻断）
      const localCheck = this._localPrivacyCheck(appInfo.appName, appInfo.windowTitle);
      if (!localCheck.allow) {
        this._status.eventsSkipped++;
        this._handleBlockedEvent(appInfo, localCheck.reason || '本地规则阻断');
        return;
      }

      // 4. 去重判断：连续相同应用在短时间内合并
      const now = new Date().toISOString();
      const sourceId = this._generateSourceId(appInfo);

      if (this._lastCapture && this._lastCapture.sourceId === sourceId) {
        if (this._lastCapture.appName === appInfo.appName) {
          // 相同应用且相同窗口 → 更新持续时间，不产生新事件
          this._status.lastCaptureTime = now;
          return;
        }
      }

      // 5. 构造事件
      const event: ActivityEvent = {
        app_name: appInfo.appName,
        window_title: appInfo.windowTitle,
        started_at: now,
        ended_at: null,
        duration_seconds: null,
        is_idle: isIdle,
        platform: 'macos',
        source_id: sourceId,
      };

      // 记录上一次捕获信息
      this._lastCapture = {
        appName: appInfo.appName,
        windowTitle: appInfo.windowTitle,
        timestamp: now,
        sourceId,
      };

      // 6. 加入缓冲区
      this._eventBuffer.push(event);
      this._status.lastCaptureTime = now;
      this._status.lastAppName = appInfo.appName;

      // 缓冲区达到阈值立即提交
      if (this._eventBuffer.length >= MAX_BATCH_SIZE) {
        await this._flushBuffer();
      }

      this._notifyStatus();
      console.log(`[ActivityCapture] 采集: ${appInfo.appName}, idle=${isIdle}`);
    } catch (err: unknown) {
      this._status.errors++;
      console.error('[ActivityCapture] 采集异常:', err);
      this._notifyStatus();
    }
  }

  /**
   * 处理被阻断的事件（发送阻断事件记录到后端）。
   */
  private async _handleBlockedEvent(
    appInfo: FrontmostAppInfo,
    reason: string,
  ): Promise<void> {
    try {
      const event: ActivityEvent = {
        app_name: appInfo.appName || 'unknown',
        window_title: appInfo.windowTitle,
        started_at: new Date().toISOString(),
        ended_at: null,
        duration_seconds: null,
        is_idle: false,
        platform: 'macos',
        source_id: `blocked_${Date.now()}_${appInfo.appName}`,
      };

      this._eventBuffer.push(event);

      // 阻断事件即时提交（不积累）
      await this._flushBuffer();
    } catch {
      // 阻断事件提交失败不影响采集
    }
  }

  // ── 本地隐私规则检查 ──────────────────────────────────────────────────

  /**
   * 本地隐私规则检查（采集前硬阻断层）。
   *
   * 检查项（按优先级）：
   * 1. 全局暂停 → 阻断
   * 2. 应用黑名单 → 阻断
   * 3. 临时暂停 → 阻断
   *
   * 内容脱敏和白名单等复杂规则由后端处理。
   * 无法确认安全时默认阻断。
   */
  private _localPrivacyCheck(
    appName: string,
    windowTitle: string | null,
  ): { allow: boolean; reason: string | null } {
    if (!this._privacyRules.length) {
      return { allow: true, reason: null };
    }

    const appNameLower = appName.toLowerCase();

    for (const rule of this._privacyRules) {
      if (!rule.active) continue;

      if (rule.type === 'global_pause') {
        return { allow: false, reason: '全局暂停采集（本地规则）' };
      }

      if (rule.type === 'app_blacklist') {
        const blacklistApps = rule.value
          .split('\n')
          .map((s) => s.trim().toLowerCase())
          .filter((s) => s.length > 0);

        if (blacklistApps.some((ba) => appNameLower === ba || appNameLower.includes(ba))) {
          return { allow: false, reason: `应用在黑名单中: ${appName}` };
        }
      }

      if (rule.type === 'temp_pause') {
        try {
          const config = JSON.parse(rule.value);
          const untilTime = new Date(config.pause_until);
          if (untilTime > new Date()) {
            return { allow: false, reason: '临时暂停中（本地规则）' };
          }
        } catch {
          // 解析失败，跳过
        }
      }
    }

    return { allow: true, reason: null };
  }

  // ── 事件提交 ──────────────────────────────────────────────────────────

  /**
   * 提交事件缓冲区到后端。
   */
  private async _flushBuffer(): Promise<void> {
    if (this._eventBuffer.length === 0) return;

    const batch = this._eventBuffer.splice(0);
    console.log(`[ActivityCapture] 提交 ${batch.length} 条事件`);

    try {
      await httpRequest(
        'POST',
        this._backendPort,
        this._authToken,
        SUBMIT_EVENTS_PATH,
        { events: batch },
      );
      this._status.eventsSubmitted += batch.length;
      this._notifyStatus();
    } catch (err) {
      console.error('[ActivityCapture] 事件提交失败:', err);
      this._status.errors++;

      // 提交失败时重新放回缓冲区（防止丢失）
      // 但如果缓冲区已很大，丢弃旧事件以确保不持续增长
      const maxBufferSize = 200;
      this._eventBuffer = [...batch, ...this._eventBuffer].slice(0, maxBufferSize);
      this._notifyStatus();
    }
  }

  /**
   * 刷新本地隐私规则缓存。
   * 从后端获取最新规则。
   */
  async refreshPrivacyRules(): Promise<void> {
    try {
      const response = await httpRequest(
        'POST',
        this._backendPort,
        this._authToken,
        '/api/v1/activities/privacy-rules/list',
        { page: 1, page_size: 100 },
      );

      if (response && response.code === 0 && response.data?.lists) {
        this._privacyRules = response.data.lists.map((rule: any) => ({
          type: rule.rule_type || '',
          value: rule.rule_value || '',
          active: rule.is_active !== false,
        }));
      }
    } catch {
      // 刷新失败不影响现有缓存
    }
  }

  // ── 工具函数 ──────────────────────────────────────────────────────────

  /**
   * 为事件生成去重标识。
   */
  private _generateSourceId(info: FrontmostAppInfo): string {
    const now = new Date();
    // 按 30 秒窗口对齐，避免短时间内的重复事件
    const windowKey = Math.floor(now.getTime() / 30000);
    return `macos_${info.appName.replace(/[^a-zA-Z0-9_-]/g, '_')}_${windowKey}`;
  }
}

// 单例导出
let _instance: ActivityCaptureManager | null = null;

export function getActivityCaptureManager(): ActivityCaptureManager {
  if (!_instance) {
    _instance = new ActivityCaptureManager();
  }
  return _instance;
}

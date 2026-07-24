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
 *
 * 平台差异：
 * - 通过 ActivityPlatformAdapter 接口调用平台能力，
 *   不直接 import 平台模块，不散落平台判断。
 * - 由 getActivityCaptureManager() 自动选择当前平台适配器。
 */

import { httpRequest } from './httpClient';
import {
  ActivityPlatformAdapter,
  FrontmostAppInfo,
} from './activityPlatform';
import { getPlatform } from '../constants/platform';

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

/** 最小空闲阈值（秒），超过此值认为用户空闲 */
const IDLE_THRESHOLD_SECONDS = 300; // 5 分钟无操作

/** 后端的活动事件提交端点 */
const SUBMIT_EVENTS_PATH = '/api/v1/activities/events';

/** 后端的活动事件批量提交最大条数 */
const MAX_BATCH_SIZE = 20;

/** 缓冲区最大事件数（超过后丢弃最旧事件） */
const MAX_BUFFER_SIZE = 200;

// ── 活动采集管理器 ─────────────────────────────────────────────────────────

export class ActivityCaptureManager {
  /** 平台采集适配器（macOS / Windows） */
  private _adapter: ActivityPlatformAdapter;

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

  constructor(adapter: ActivityPlatformAdapter) {
    this._adapter = adapter;
  }

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
    const accessibilityStatus = await this._adapter.checkAccessibilityPermission();
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

    // 每 30 秒提交缓冲区
    this._bufferTimer = setInterval(() => {
      this._flushBuffer();
    }, 30000);

    this._notifyStatus();
    return true;
  }

  /**
   * 停止活动采集。
   * 停止轮询并提交剩余缓冲区事件。
   */
  async stop(): Promise<void> {
    this._running = false;
    this._status.running = false;

    this._clearTimers();

    // 提交剩余缓冲事件
    await this._flushBuffer();

    this._lastCapture = null;
    this._notifyStatus();
    console.log('[ActivityCapture] 已停止采集');
  }

  /**
   * 同步停止活动采集（用于应用退出场景）。
   *
   * 与 stop() 的区别：
   * - 同步执行，不 await 缓冲区提交
   * - 仅停止定时器和管理状态
   * - 应用退出时缓冲区数据丢失是可接受的（最多几秒的事件）
   */
  stopSync(): void {
    this._running = false;
    this._status.running = false;

    this._clearTimers();
    this._lastCapture = null;

    this._notifyStatus();
    console.log('[ActivityCapture] 同步停止（应用退出）');
  }

  /** 清除所有定时器。 */
  private _clearTimers(): void {
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }

    if (this._bufferTimer) {
      clearInterval(this._bufferTimer);
      this._bufferTimer = null;
    }
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
        appInfo = await this._adapter.getFrontmostAppInfo();
      } else {
        // 降级：只获取应用名称，不获取窗口标题
        const appName = await this._adapter.getFrontmostAppName();
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
      const idleInfo = await this._adapter.getIdleTime();
      const isIdle = idleInfo.success && idleInfo.idleSeconds >= IDLE_THRESHOLD_SECONDS;

      // 3. 本地隐私规则检查（采集前硬阻断）
      const localCheck = this._localPrivacyCheck(appInfo.appName, appInfo.windowTitle);
      if (!localCheck.allow) {
        this._status.eventsSkipped++;
        // 阻断事件不入缓冲区、不提交后端——阻断就是「没发生」
        console.log(
          `[ActivityCapture] 阻断: ${appInfo.appName}, 原因: ${localCheck.reason}`,
        );
        return;
      }

      // 4. 去重判断：连续相同应用合并
      const now = new Date().toISOString();
      const sourceId = this._generateSourceId(appInfo);

      if (this._lastCapture && this._lastCapture.sourceId === sourceId) {
        if (this._lastCapture.appName === appInfo.appName) {
          // 相同应用且相同窗口 → 更新时间戳，不产生新事件
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
        platform: getPlatform(),
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

  // ── 本地隐私规则检查（采集前硬阻断层） ─────────────────────────────────

  /**
   * 本地隐私规则检查（采集前硬阻断层）。
   *
   * 支持规则类型：
   * 1. global_pause    → 全局暂停
   * 2. app_blacklist   → 应用黑名单（名称或 Bundle ID 匹配）
   * 3. app_whitelist   → 应用白名单（仅白名单中的应用可采集）
   * 4. title_keyword   → 窗口标题关键字阻断
   * 5. time_based      → 特定时段暂停
   * 6. temp_pause      → 单次临时暂停
   *
   * 不在此层处理：
   * - content_masking  → 内容脱敏，由后端 Python 层处理
   *
   * 设计原则：
   * - 采集前硬阻断：敏感场景在采集前被阻断，而不是先采集后判断
   * - 无法确认安全时默认阻断（fail closed）
   */
  private _localPrivacyCheck(
    appName: string,
    windowTitle: string | null,
  ): { allow: boolean; reason: string | null } {
    if (!this._privacyRules.length) {
      return { allow: false, reason: '无隐私规则，默认阻断' };
    }

    const appNameLower = appName.toLowerCase();
    const now = new Date();
    const currentHour = now.getHours();
    const currentMinutes = now.getHours() * 60 + now.getMinutes();

    // 先分类规则，按优先级排序
    const activeRules = this._privacyRules.filter((r) => r.active);

    for (const rule of activeRules) {
      try {
        switch (rule.type) {
          // ── 全局暂停 ─────────────────────────────────────────────
          case 'global_pause':
            return { allow: false, reason: '全局暂停采集（本地规则）' };

          // ── 应用黑名单 ─────────────────────────────────────────
          case 'app_blacklist': {
            const blacklistApps = rule.value
              .split('\n')
              .map((s) => s.trim().toLowerCase())
              .filter((s) => s.length > 0);

            if (blacklistApps.some((ba) => appNameLower === ba || appNameLower.includes(ba))) {
              return { allow: false, reason: `应用在黑名单中: ${appName}` };
            }
            break;
          }

          // ── 应用白名单 ─────────────────────────────────────────
          case 'app_whitelist': {
            const whitelistApps = rule.value
              .split('\n')
              .map((s) => s.trim().toLowerCase())
              .filter((s) => s.length > 0);

            // 白名单存在且非空时，不在白名单中的应用一律阻断
            if (whitelistApps.length > 0 && !whitelistApps.some((wa) => appNameLower === wa)) {
              return { allow: false, reason: `应用不在白名单中: ${appName}` };
            }
            break;
          }

          // ── 窗口标题关键字阻断 ─────────────────────────────────
          case 'title_keyword': {
            if (!windowTitle) break; // 无窗口标题时无法判断，跳过

            const windowTitleLower = windowTitle.toLowerCase();
            const keywords = rule.value
              .split('\n')
              .map((s) => s.trim().toLowerCase())
              .filter((s) => s.length > 0);

            if (keywords.some((kw) => windowTitleLower.includes(kw))) {
              return { allow: false, reason: `窗口标题包含敏感关键字` };
            }
            break;
          }

          // ── 特定时段暂停 ───────────────────────────────────────
          case 'time_based': {
            const config = JSON.parse(rule.value);
            const startHour = config.start_hour;
            const endHour = config.end_hour;

            if (typeof startHour !== 'number' || typeof endHour !== 'number') {
              break; // 配置格式错误，跳过
            }

            const startMinutes = startHour * 60;
            const endMinutes = endHour * 60;

            const inRange = startMinutes <= endMinutes
              // 同一天内（如 9:00-18:00）
              ? (currentMinutes >= startMinutes && currentMinutes < endMinutes)
              // 跨天（如 22:00-07:00）
              : (currentMinutes >= startMinutes || currentMinutes < endMinutes);

            if (inRange) {
              return { allow: false, reason: `当前时段暂停采集（${startHour}:00-${endHour}:00）` };
            }
            break;
          }

          // ── 单次临时暂停 ───────────────────────────────────────
          case 'temp_pause': {
            const config = JSON.parse(rule.value);
            const untilTime = new Date(config.pause_until);
            if (untilTime > now) {
              return { allow: false, reason: '临时暂停中（本地规则）' };
            }
            break;
          }

          // ── 内容脱敏 ─────────────────────────────────────────
          case 'content_masking':
            // 脱敏由后端 Python 层处理，本地只做硬阻断
            break;

          default:
            break;
        }
      } catch {
        // 单条规则解析失败，不影响其他规则判断
        continue;
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

      // 提交失败时重新放回缓冲区
      // 保留最新事件，丢弃最旧事件，防止缓冲区无限增长
      this._eventBuffer = [...this._eventBuffer, ...batch].slice(-MAX_BUFFER_SIZE);
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
    return `${getPlatform()}_${info.appName.replace(/[^a-zA-Z0-9_-]/g, '_')}_${windowKey}`;
  }
}

// ── 单例管理 ──────────────────────────────────────────────────────────────

let _instance: ActivityCaptureManager | null = null;

/**
 * 获取活动采集管理器单例。
 *
 * 自动根据当前平台选择适配器：
 * - macOS → MacOSCollector
 * - Windows → WindowsCollector
 */
export function getActivityCaptureManager(): ActivityCaptureManager {
  if (!_instance) {
    const platform = getPlatform();
    let adapter: ActivityPlatformAdapter;

    if (platform === 'macos') {
      const { getMacOSCollector } = require('../platform/macOSCollector');
      adapter = getMacOSCollector();
    } else {
      const { getWindowsCollector } = require('../platform/windowsCollector');
      adapter = getWindowsCollector();
    }

    _instance = new ActivityCaptureManager(adapter);
  }
  return _instance;
}

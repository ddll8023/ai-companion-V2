/**
 * 日期时间格式化工具函数。
 *
 * 集中管理所有时间格式化逻辑，避免各页面重复定义。
 */

/**
 * 格式化日期时间为本地化字符串。
 * @param dateStr - ISO 日期字符串或 null
 * @returns 格式化后的字符串，null 时返回 '-'
 */
export function formatTime(dateStr: string | null): string {
  if (!dateStr) return '-'
  try {
    return new Date(dateStr).toLocaleString('zh-CN')
  } catch {
    return dateStr
  }
}

/**
 * 格式化持续时长（秒）为人类可读形式。
 * @param seconds - 持续秒数
 * @returns 如 '3秒', '5分20秒', '1时30分'
 */
export function formatDuration(seconds: number): string {
  if (!seconds && seconds !== 0) return '-'
  if (seconds < 0) return '-'
  if (seconds < 60) return `${seconds}秒`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}分${seconds % 60}秒`
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return `${h}时${m}分`
}

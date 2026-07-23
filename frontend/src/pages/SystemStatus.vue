<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getSystemStatus, getAuditStats, getAuditLogs } from '@/api/system'
import type { SystemStatusResponse, AuditStats, PaginatedResponse, AuditLogResponse } from '@/types/api'
import LoadingState from '@/components/custom/LoadingState.vue'
import ErrorState from '@/components/custom/ErrorState.vue'
import EmptyState from '@/components/custom/EmptyState.vue'

const loading = ref(true)
const error = ref<string | null>(null)
const status = ref<SystemStatusResponse | null>(null)
const auditStats = ref<AuditStats | null>(null)
const recentAuditLogs = ref<AuditLogResponse[]>([])

async function fetchData() {
  loading.value = true
  error.value = null

  try {
    const [statusRes, auditRes, auditLogsRes] = await Promise.all([
      getSystemStatus(),
      getAuditStats(),
      getAuditLogs({ page: 1, page_size: 10 }),
    ])

    if (statusRes.code === 0) {
      status.value = statusRes.data
    }
    if (auditRes.code === 0) {
      auditStats.value = auditRes.data
    }
    if (auditLogsRes.code === 0) {
      const data = auditLogsRes.data as PaginatedResponse<AuditLogResponse>
      recentAuditLogs.value = data.lists || []
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '获取系统状态失败'
  } finally {
    loading.value = false
  }
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`
}

function formatTime(iso: string | null): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN')
}

/** 将能力状态映射为颜色类 */
function statusColor(ok: boolean): string {
  return ok ? 'text-success' : 'text-error'
}

/** 将能力状态映射为图标 */
function statusIcon(ok: boolean): string {
  return ok ? 'circle-check' : 'circle-xmark'
}

onMounted(fetchData)
</script>

<template>
  <div class="p-6 space-y-6">
    <div class="mb-6">
      <h2 class="text-xl font-semibold text-text">系统状态</h2>
      <p class="mt-1 text-sm text-text-secondary">查看各项能力和服务的运行状态</p>
    </div>

    <LoadingState :loading="loading" loading-text="正在获取系统状态...">
      <ErrorState
        :error="error"
        :show-retry="true"
        @retry="fetchData"
      >
        <EmptyState
          v-if="!status"
          empty-text="未能获取系统状态数据"
        >
          <!-- 数据渲染区域 -->
          <div v-if="status" class="space-y-6">

            <!-- 服务概览 -->
            <section>
              <h3 class="text-base font-medium text-text mb-3">服务概览</h3>
              <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm text-text-secondary">
                    <font-awesome-icon :icon="['fas', 'server']" />
                    <span>服务状态</span>
                  </div>
                  <p class="mt-2 text-lg font-semibold" :class="statusColor(status.service.status === 'running')">
                    {{ status.service.status === 'running' ? '运行中' : '异常' }}
                  </p>
                </div>

                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm text-text-secondary">
                    <font-awesome-icon :icon="['fas', 'cube']" />
                    <span>服务名称</span>
                  </div>
                  <p class="mt-2 text-sm font-medium text-text">{{ status.service.name }}</p>
                </div>

                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm text-text-secondary">
                    <font-awesome-icon :icon="['fas', 'tag']" />
                    <span>版本</span>
                  </div>
                  <p class="mt-2 text-sm font-medium text-text">{{ status.service.version }}</p>
                </div>

                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm text-text-secondary">
                    <font-awesome-icon :icon="['fas', 'clock']" />
                    <span>检查时间</span>
                  </div>
                  <p class="mt-2 text-sm font-medium text-text">{{ formatTime(status.checked_at) }}</p>
                </div>
              </div>
            </section>

            <!-- 数据库状态 -->
            <section>
              <h3 class="text-base font-medium text-text mb-3">
                <font-awesome-icon :icon="['fas', 'database']" class="mr-2" />
                数据库
              </h3>
              <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm">
                    <font-awesome-icon :icon="['fas', statusIcon(status.database.ready)]" :class="statusColor(status.database.ready)" />
                    <span :class="statusColor(status.database.ready)">
                      {{ status.database.ready ? '就绪' : '不可用' }}
                    </span>
                  </div>
                  <p class="mt-2 text-xs text-text-tertiary break-all">{{ status.database.path }}</p>
                </div>

                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm text-text-secondary">
                    <font-awesome-icon :icon="['fas', 'hard-drive']" />
                    <span>数据库大小</span>
                  </div>
                  <p class="mt-2 text-sm font-medium text-text">{{ formatBytes(status.database.file_size_bytes) }}</p>
                </div>

                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm">
                    <font-awesome-icon :icon="['fas', statusIcon(status.database.fts5_ready)]" :class="statusColor(status.database.fts5_ready)" />
                    <span>全文索引 (FTS5)</span>
                  </div>
                  <p class="mt-2 text-sm font-medium text-text">
                    {{ status.database.fts5_ready ? '可用' : '不可用' }}
                    <span v-if="status.database.fts5_ready" class="text-text-tertiary text-xs ml-1">
                      ({{ status.database.fts5_index_count }} 条索引)
                    </span>
                  </p>
                </div>
              </div>
            </section>

            <!-- 数据目录 -->
            <section>
              <h3 class="text-base font-medium text-text mb-3">
                <font-awesome-icon :icon="['fas', 'folder']" class="mr-2" />
                数据目录
              </h3>
              <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm">
                    <font-awesome-icon :icon="['fas', statusIcon(status.data_directory.writable)]" :class="statusColor(status.data_directory.writable)" />
                    <span :class="statusColor(status.data_directory.writable)">
                      {{ status.data_directory.writable ? '可写' : '不可写' }}
                    </span>
                  </div>
                  <p class="mt-2 text-xs text-text-tertiary break-all">{{ status.data_directory.path }}</p>
                </div>

                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm text-text-secondary">
                    <font-awesome-icon :icon="['fas', 'file']" />
                    <span>文件数量</span>
                  </div>
                  <p class="mt-2 text-sm font-medium text-text">{{ status.data_directory.file_count }}</p>
                </div>

                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm text-text-secondary">
                    <font-awesome-icon :icon="['fas', 'hard-drive']" />
                    <span>总大小</span>
                  </div>
                  <p class="mt-2 text-sm font-medium text-text">{{ formatBytes(status.data_directory.total_size_bytes) }}</p>
                </div>
              </div>
            </section>

            <!-- 模型配置 -->
            <section>
              <h3 class="text-base font-medium text-text mb-3">
                <font-awesome-icon :icon="['fas', 'brain']" class="mr-2" />
                模型配置
              </h3>
              <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm">
                    <font-awesome-icon :icon="['fas', statusIcon(status.model_config.available)]" :class="statusColor(status.model_config.available)" />
                    <span>可用状态</span>
                  </div>
                  <p class="mt-2 text-sm font-medium" :class="statusColor(status.model_config.available)">
                    {{ status.model_config.available ? '可用' : '不可用' }}
                  </p>
                </div>

                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm text-text-secondary">
                    <font-awesome-icon :icon="['fas', 'list']" />
                    <span>配置总数</span>
                  </div>
                  <p class="mt-2 text-sm font-medium text-text">{{ status.model_config.total_configs }}</p>
                </div>

                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm text-text-secondary">
                    <font-awesome-icon :icon="['fas', 'check-circle']" />
                    <span>激活数</span>
                  </div>
                  <p class="mt-2 text-sm font-medium text-text">{{ status.model_config.active_count }}</p>
                </div>

                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm text-text-secondary">
                    <font-awesome-icon :icon="['fas', 'exclamation-triangle']" />
                    <span>错误数</span>
                  </div>
                  <p class="mt-2 text-sm font-medium" :class="status.model_config.error_count > 0 ? 'text-warning' : 'text-text'">
                    {{ status.model_config.error_count }}
                  </p>
                </div>
              </div>
              <!-- 当前激活配置详情 -->
              <div v-if="status.model_config.active_config" class="mt-3 p-3 bg-surface rounded-lg border border-border">
                <h4 class="text-xs font-medium text-text-secondary mb-2">当前激活配置</h4>
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                  <div>
                    <span class="text-text-tertiary text-xs">名称</span>
                    <p class="text-text">{{ status.model_config.active_config.name }}</p>
                  </div>
                  <div>
                    <span class="text-text-tertiary text-xs">供应商</span>
                    <p class="text-text">{{ status.model_config.active_config.provider }}</p>
                  </div>
                  <div>
                    <span class="text-text-tertiary text-xs">模型</span>
                    <p class="text-text">{{ status.model_config.active_config.model_name }}</p>
                  </div>
                  <div>
                    <span class="text-text-tertiary text-xs">密钥</span>
                    <p class="text-text">
                      {{ status.model_config.active_config.has_key ? '已配置' : '未配置' }}
                    </p>
                  </div>
                </div>
                <p v-if="status.model_config.active_config.error_message" class="mt-2 text-xs text-error">
                  {{ status.model_config.active_config.error_message }}
                </p>
              </div>
              <div v-else class="mt-3 p-3 bg-surface rounded-lg border border-border">
                <p class="text-xs text-text-tertiary">暂无激活的模型配置</p>
              </div>
            </section>

            <!-- 后台任务 -->
            <section>
              <h3 class="text-base font-medium text-text mb-3">
                <font-awesome-icon :icon="['fas', 'tasks']" class="mr-2" />
                后台任务
              </h3>
              <div class="grid grid-cols-1 sm:grid-cols-4 gap-4">
                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm">
                    <font-awesome-icon :icon="['fas', statusIcon(status.background_tasks.healthy)]" :class="statusColor(status.background_tasks.healthy)" />
                    <span>积压状态</span>
                  </div>
                  <p class="mt-2 text-sm font-medium" :class="statusColor(status.background_tasks.healthy)">
                    {{ status.background_tasks.healthy ? '正常' : '积压过多' }}
                  </p>
                </div>

                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm text-text-secondary">
                    <font-awesome-icon :icon="['fas', 'hourglass-half']" />
                    <span>待处理</span>
                  </div>
                  <p class="mt-2 text-sm font-medium text-text">{{ status.background_tasks.pending }}</p>
                </div>

                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm text-text-secondary">
                    <font-awesome-icon :icon="['fas', 'spinner']" />
                    <span>执行中</span>
                  </div>
                  <p class="mt-2 text-sm font-medium text-text">{{ status.background_tasks.running }}</p>
                </div>

                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm text-text-secondary">
                    <font-awesome-icon :icon="['fas', 'bug']" />
                    <span>失败/重试</span>
                  </div>
                  <p class="mt-2 text-sm font-medium" :class="(status.background_tasks.failed + status.background_tasks.retrying) > 0 ? 'text-warning' : 'text-text'">
                    {{ status.background_tasks.failed }} 失败 / {{ status.background_tasks.retrying }} 重试
                  </p>
                </div>
              </div>
            </section>

            <!-- 活动采集 -->
            <section>
              <h3 class="text-base font-medium text-text mb-3">
                <font-awesome-icon :icon="['fas', 'clock']" class="mr-2" />
                活动采集
              </h3>
              <div class="grid grid-cols-1 sm:grid-cols-4 gap-4">
                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm text-text-secondary">
                    <font-awesome-icon :icon="['fas', 'shield']" />
                    <span>隐私规则</span>
                  </div>
                  <p class="mt-2 text-sm font-medium text-text">
                    {{ status.activity_collection.privacy_rules_active }} / {{ status.activity_collection.privacy_rules_total }} 激活
                  </p>
                </div>

                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm text-text-secondary">
                    <font-awesome-icon :icon="['fas', 'calendar-day']" />
                    <span>今日记录</span>
                  </div>
                  <p class="mt-2 text-sm font-medium text-text">{{ status.activity_collection.activities_today }}</p>
                </div>

                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm text-text-secondary">
                    <font-awesome-icon :icon="['fas', 'list']" />
                    <span>总记录数</span>
                  </div>
                  <p class="mt-2 text-sm font-medium text-text">{{ status.activity_collection.activities_total }}</p>
                </div>
              </div>
            </section>

            <!-- 备份状态 -->
            <section>
              <h3 class="text-base font-medium text-text mb-3">
                <font-awesome-icon :icon="['fas', 'archive']" class="mr-2" />
                备份状态
              </h3>
              <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm text-text-secondary">
                    <font-awesome-icon :icon="['fas', 'database']" />
                    <span>备份总数</span>
                  </div>
                  <p class="mt-2 text-sm font-medium text-text">{{ status.backup.total_backups }}</p>
                </div>

                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm text-text-secondary">
                    <font-awesome-icon :icon="['fas', 'clock']" />
                    <span>最近备份</span>
                  </div>
                  <p class="mt-2 text-xs font-medium text-text">{{ formatTime(status.backup.latest_backup_at) }}</p>
                </div>

                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm text-text-secondary">
                    <font-awesome-icon :icon="['fas', 'circle-info']" />
                    <span>最近备份状态</span>
                  </div>
                  <p class="mt-2 text-sm font-medium" :class="statusColor(status.backup.latest_backup_status === 'completed')">
                    {{ status.backup.latest_backup_status === 'completed' ? '完成' : (status.backup.latest_backup_status || '-') }}
                  </p>
                </div>
              </div>
            </section>

            <!-- 审计日志概览 -->
            <section>
              <h3 class="text-base font-medium text-text mb-3">
                <font-awesome-icon :icon="['fas', 'clipboard-list']" class="mr-2" />
                审计日志
              </h3>
              <div v-if="auditStats" class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm text-text-secondary">
                    <font-awesome-icon :icon="['fas', 'list']" />
                    <span>总计</span>
                  </div>
                  <p class="mt-2 text-lg font-semibold text-text">{{ auditStats.total }}</p>
                </div>
                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm text-text-secondary">
                    <font-awesome-icon :icon="['fas', 'check-circle']" />
                    <span>成功</span>
                  </div>
                  <p class="mt-2 text-lg font-semibold text-success">{{ auditStats.success }}</p>
                </div>
                <div class="p-4 bg-surface rounded-lg border border-border">
                  <div class="flex items-center gap-2 text-sm text-text-secondary">
                    <font-awesome-icon :icon="['fas', 'times-circle']" />
                    <span>失败</span>
                  </div>
                  <p class="mt-2 text-lg font-semibold" :class="auditStats.fail > 0 ? 'text-error' : 'text-text'">{{ auditStats.fail }}</p>
                </div>
              </div>

              <!-- 最近审计记录 -->
              <h4 class="text-sm font-medium text-text-secondary mb-2">最近审计记录</h4>
              <div v-if="recentAuditLogs.length > 0" class="overflow-x-auto">
                <table class="w-full text-sm">
                  <thead>
                    <tr class="border-b border-border">
                      <th class="text-left py-2 px-3 text-text-tertiary font-medium">时间</th>
                      <th class="text-left py-2 px-3 text-text-tertiary font-medium">操作</th>
                      <th class="text-left py-2 px-3 text-text-tertiary font-medium">对象类型</th>
                      <th class="text-left py-2 px-3 text-text-tertiary font-medium">摘要</th>
                      <th class="text-center py-2 px-3 text-text-tertiary font-medium">结果</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="log in recentAuditLogs" :key="log.id" class="border-b border-border hover:bg-hover">
                      <td class="py-2 px-3 text-text-tertiary text-xs">{{ formatTime(log.created_at) }}</td>
                      <td class="py-2 px-3 text-text font-medium">{{ log.action }}</td>
                      <td class="py-2 px-3 text-text-secondary">{{ log.target_type || '-' }}</td>
                      <td class="py-2 px-3 text-text-secondary max-w-xs truncate">{{ log.summary || '-' }}</td>
                      <td class="py-2 px-3 text-center">
                        <font-awesome-icon
                          :icon="['fas', log.result === 0 ? 'check-circle' : 'times-circle']"
                          :class="log.result === 0 ? 'text-success' : 'text-error'"
                          :title="log.result === 0 ? '成功' : '失败'"
                        />
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div v-else class="p-6 text-center text-sm text-text-tertiary">
                暂无审计记录
              </div>
            </section>
          </div>
        </EmptyState>
      </ErrorState>
    </LoadingState>
  </div>
</template>

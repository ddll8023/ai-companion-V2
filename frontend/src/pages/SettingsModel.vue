<template>
  <div class="p-6 max-w-4xl">
    <!-- 页面标题 -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h2 class="text-xl font-semibold text-text">模型设置</h2>
        <p class="mt-1 text-sm text-text-secondary">配置外部模型供应商，用于对话和记忆处理</p>
      </div>
      <button
        class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-dark transition-colors"
        @click="openCreateForm"
      >
        <font-awesome-icon :icon="['fas', 'plus']" class="mr-1" />
        添加配置
      </button>
    </div>

    <!-- 支持的供应商 -->
    <div class="mb-6 flex items-center gap-4 text-sm text-text-secondary">
      <span>支持的供应商：</span>
      <span v-for="(label, key) in providers" :key="key" class="inline-flex items-center gap-1 px-2 py-0.5 bg-surface border border-border rounded">
        <font-awesome-icon :icon="['fas', 'check-circle']" class="text-xs text-success" />
        {{ label }}
      </span>
    </div>

    <!-- 编辑表单抽屉 -->
    <Transition name="slide">
      <div
        v-if="showForm"
        class="mb-6 p-5 bg-surface border border-border rounded-lg"
      >
        <h3 class="text-base font-medium text-text mb-4">
          {{ editingId ? '编辑配置' : '新增配置' }}
        </h3>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <label class="block text-sm font-medium text-text mb-1">配置名称</label>
            <input
              v-model="form.name"
              type="text"
              class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text placeholder-text-tertiary focus:outline-none focus:border-primary"
              placeholder="如：主力模型"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-text mb-1">供应商</label>
            <select
              v-model="form.provider"
              class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text focus:outline-none focus:border-primary"
            >
              <option value="" disabled>选择供应商</option>
              <option v-for="(label, key) in providers" :key="key" :value="key">
                {{ label }}
              </option>
            </select>
          </div>
          <div>
            <label class="block text-sm font-medium text-text mb-1">模型名称</label>
            <input
              v-model="form.model_name"
              type="text"
              class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text placeholder-text-tertiary focus:outline-none focus:border-primary"
              placeholder="如：gpt-4o"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-text mb-1">API 地址（可选）</label>
            <input
              v-model="form.api_base"
              type="text"
              class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text placeholder-text-tertiary focus:outline-none focus:border-primary"
              placeholder="留空使用默认地址"
            />
          </div>
        </div>

        <div class="flex items-center gap-3">
          <button
            class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-dark transition-colors disabled:opacity-50"
            :disabled="!formValid || saving"
            @click="saveConfig"
          >
            {{ saving ? '保存中...' : '保存' }}
          </button>
          <button
            class="px-4 py-2 text-sm font-medium text-text-secondary bg-hover rounded-lg hover:text-text transition-colors"
            @click="closeForm"
          >
            取消
          </button>
          <span v-if="formError" class="text-sm text-error">{{ formError }}</span>
        </div>
      </div>
    </Transition>

    <!-- 加载状态 -->
    <LoadingState :loading="loading" loading-text="加载模型配置...">
      <!-- 空状态 -->
      <EmptyState :empty="configs.length === 0" empty-text="暂无模型配置，点击上方「添加配置」开始配置">
        <!-- 配置列表 -->
        <div class="space-y-4">
          <div
            v-for="config in configs"
            :key="config.id"
            class="p-5 bg-surface border border-border rounded-lg"
          >
            <div class="flex items-start justify-between">
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                  <h3 class="text-base font-medium text-text truncate">{{ config.name }}</h3>
                  <!-- 激活标签 -->
                  <span
                    v-if="config.is_active"
                    class="inline-flex items-center px-2 py-0.5 text-xs font-medium text-primary-dark bg-primary-light rounded"
                  >
                    当前使用
                  </span>
                  <!-- 状态标签 -->
                  <span
                    class="inline-flex items-center px-2 py-0.5 text-xs rounded"
                    :class="statusClass(config.status)"
                  >
                    {{ statusLabel(config.status) }}
                  </span>
                  <!-- 密钥状态 -->
                  <span
                    class="inline-flex items-center px-2 py-0.5 text-xs rounded"
                    :class="config.has_key ? 'text-success bg-green-50' : 'text-text-tertiary bg-hover'"
                  >
                    {{ config.has_key ? '密钥已配置' : '密钥未配置' }}
                  </span>
                </div>
                <div class="flex items-center gap-4 text-sm text-text-secondary">
                  <span>{{ providers[config.provider] || config.provider }}</span>
                  <span class="font-mono">{{ config.model_name }}</span>
                  <span v-if="config.api_base" class="truncate max-w-xs">{{ config.api_base }}</span>
                </div>
                <p v-if="config.error_message" class="mt-1 text-xs text-error truncate">
                  {{ config.error_message }}
                </p>
              </div>

              <!-- 操作按钮 -->
              <div class="flex items-center gap-2 ml-4 flex-shrink-0">
                <!-- 测试连接 -->
                <button
                  class="px-3 py-1.5 text-xs font-medium text-text-secondary border border-border rounded-lg hover:bg-hover hover:text-text transition-colors"
                  :title="config.has_key ? '测试连接' : '请先配置密钥'"
                  @click="testConnection(config)"
                >
                  <font-awesome-icon :icon="['fas', 'plug']" class="mr-1" />
                  测试
                </button>

                <!-- 配置密钥 -->
                <button
                  class="px-3 py-1.5 text-xs font-medium text-text-secondary border border-border rounded-lg hover:bg-hover hover:text-text transition-colors"
                  @click="showKeyDialog(config)"
                >
                  <font-awesome-icon :icon="['fas', 'key']" class="mr-1" />
                  密钥
                </button>

                <!-- 设为当前使用 -->
                <button
                  v-if="!config.is_active"
                  class="px-3 py-1.5 text-xs font-medium text-text-secondary border border-border rounded-lg hover:bg-hover hover:text-text transition-colors"
                  @click="activateConfig(config)"
                >
                  激活
                </button>

                <!-- 编辑 -->
                <button
                  class="px-3 py-1.5 text-xs font-medium text-text-secondary border border-border rounded-lg hover:bg-hover hover:text-text transition-colors"
                  @click="editConfig(config)"
                >
                  <font-awesome-icon :icon="['fas', 'pen']" />
                </button>

                <!-- 删除 -->
                <button
                  class="px-3 py-1.5 text-xs font-medium text-error border border-border rounded-lg hover:bg-error hover:text-white transition-colors"
                  @click="deleteConfig(config)"
                >
                  <font-awesome-icon :icon="['fas', 'trash']" />
                </button>
              </div>
            </div>

            <!-- 测试结果行 -->
            <Transition name="fade">
              <div
                v-if="testingId === config.id"
                class="mt-3 pt-3 border-t border-border"
              >
                <div v-if="testLoading" class="flex items-center gap-2 text-sm text-text-secondary">
                  <font-awesome-icon :icon="['fas', 'spinner']" class="fa-spin" />
                  测试中...
                </div>
                <div v-else class="flex items-center gap-2 text-sm" :class="testSuccess ? 'text-success' : 'text-error'">
                  <font-awesome-icon :icon="testSuccess ? ['fas', 'check-circle'] : ['fas', 'circle-exclamation']" />
                  {{ testMessage }}
                </div>
              </div>
            </Transition>
          </div>
        </div>
      </EmptyState>
    </LoadingState>

    <!-- 错误状态 -->
    <ErrorState :error="error" :show-retry="true" @retry="fetchConfigs" />

    <!-- API 密钥输入对话框 -->
    <Transition name="fade">
      <div
        v-if="keyDialogVisible"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
        @click.self="closeKeyDialog"
      >
        <div class="w-96 p-5 bg-surface rounded-xl border border-border shadow-lg">
          <h3 class="text-base font-medium text-text mb-1">配置 API 密钥</h3>
          <p class="text-sm text-text-secondary mb-4">
            为「{{ keyDialogConfig?.name }}」输入 API Key（仅保存到系统安全存储，不写入数据库）
          </p>
          <input
            v-model="keyInput"
            type="password"
            class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text placeholder-text-tertiary focus:outline-none focus:border-primary mb-4"
            placeholder="输入 API Key"
          />
          <div class="flex items-center gap-3">
            <button
              class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-dark transition-colors disabled:opacity-50"
              :disabled="!keyInput || keySaving"
              @click="saveKey"
            >
              {{ keySaving ? '保存中...' : '保存' }}
            </button>
            <button
              class="px-4 py-2 text-sm font-medium text-text-secondary bg-hover rounded-lg hover:text-text transition-colors"
              @click="closeKeyDialog"
            >
              取消
            </button>
            <span v-if="keyError" class="text-sm text-error">{{ keyError }}</span>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 测试连接时的 API Key 输入（Browser 模式或密钥未配置时） -->
    <Transition name="fade">
      <div
        v-if="testKeyDialogVisible"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
        @click.self="closeTestKeyDialog"
      >
        <div class="w-96 p-5 bg-surface rounded-xl border border-border shadow-lg">
          <h3 class="text-base font-medium text-text mb-1">输入 API Key</h3>
          <p class="text-sm text-text-secondary mb-4">
            为「{{ testKeyDialogConfig?.name }}」输入 API Key 以测试连接
          </p>
          <input
            v-model="testKeyInput"
            type="password"
            class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg text-text placeholder-text-tertiary focus:outline-none focus:border-primary mb-4"
            placeholder="输入 API Key"
          />
          <div class="flex items-center gap-3">
            <button
              class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-dark transition-colors disabled:opacity-50"
              :disabled="!testKeyInput || testLoading"
              @click="doTestConnectionWithKey"
            >
              {{ testLoading ? '测试中...' : '开始测试' }}
            </button>
            <button
              class="px-4 py-2 text-sm font-medium text-text-secondary bg-hover rounded-lg hover:text-text transition-colors"
              @click="closeTestKeyDialog"
            >
              取消
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import type { ModelConfig, ModelConfigCreate, ModelConfigUpdate } from '@/types/api'
import * as modelApi from '@/api/model'
import LoadingState from '@/components/custom/LoadingState.vue'
import EmptyState from '@/components/custom/EmptyState.vue'
import ErrorState from '@/components/custom/ErrorState.vue'

// ── 供应商列表 ──
const providers = ref<Record<string, string>>({})

// ── 配置列表 ──
const configs = ref<ModelConfig[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

// ── 编辑表单 ──
const showForm = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)
const formError = ref<string | null>(null)
const form = ref<ModelConfigCreate>({
  name: '',
  provider: '',
  model_name: '',
  api_base: '',
})

// ── 测试连接 ──
const testingId = ref<number | null>(null)
const testLoading = ref(false)
const testSuccess = ref(false)
const testMessage = ref('')

// ── 密钥对话框 ──
const keyDialogVisible = ref(false)
const keyDialogConfig = ref<ModelConfig | null>(null)
const keyInput = ref('')
const keySaving = ref(false)
const keyError = ref<string | null>(null)

// ── 测试时密钥输入对话框 ──
const testKeyDialogVisible = ref(false)
const testKeyDialogConfig = ref<ModelConfig | null>(null)
const testKeyInput = ref('')

// ── 计算属性 ──
const formValid = computed(() => {
  return form.value.name && form.value.provider && form.value.model_name
})

// ── 加载配置列表 ──
async function fetchConfigs() {
  loading.value = true
  error.value = null
  try {
    const res = await modelApi.listConfigs()
    configs.value = res.data || []
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载模型配置失败'
  } finally {
    loading.value = false
  }
}

// ── 加载支持的供应商 ──
async function fetchProviders() {
  try {
    const res = await modelApi.getProviders()
    providers.value = res.data || {}
  } catch {
    providers.value = { openai: 'OpenAI', anthropic: 'Anthropic', 'openai-compatible': '兼容 OpenAI 格式' }
  }
}

// ── 表单操作 ──
function openCreateForm() {
  editingId.value = null
  form.value = { name: '', provider: '', model_name: '', api_base: '' }
  formError.value = null
  showForm.value = true
}

function editConfig(config: ModelConfig) {
  editingId.value = config.id
  form.value = {
    name: config.name,
    provider: config.provider,
    model_name: config.model_name,
    api_base: config.api_base || '',
  }
  formError.value = null
  showForm.value = true
}

function closeForm() {
  showForm.value = false
  editingId.value = null
  formError.value = null
}

async function saveConfig() {
  if (!formValid.value) return
  saving.value = true
  formError.value = null
  try {
    if (editingId.value) {
      await modelApi.updateConfig(editingId.value, form.value)
    } else {
      await modelApi.createConfig(form.value)
    }
    closeForm()
    await fetchConfigs()
  } catch (e: unknown) {
    formError.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    saving.value = false
  }
}

async function deleteConfig(config: ModelConfig) {
  if (!confirm(`确定删除配置「${config.name}」吗？`)) return
  try {
    // 先清理安全存储中的密钥
    if (window.electronAPI) {
      await window.electronAPI.keystoreDelete(`model_key_${config.id}`)
    }
    // 再删除配置记录
    await modelApi.deleteConfig(config.id)
    await fetchConfigs()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '删除失败'
  }
}

async function activateConfig(config: ModelConfig) {
  try {
    await modelApi.activateConfig(config.id)
    await fetchConfigs()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '激活失败'
  }
}

// ── 密钥对话框 ──
function showKeyDialog(config: ModelConfig) {
  keyDialogConfig.value = config
  keyInput.value = ''
  keyError.value = null
  keyDialogVisible.value = true
}

function closeKeyDialog() {
  keyDialogVisible.value = false
  keyDialogConfig.value = null
  keyInput.value = ''
  keyError.value = null
}

async function saveKey() {
  if (!keyInput.value || !keyDialogConfig.value) return
  keySaving.value = true
  keyError.value = null
  try {
    // Electron 模式：保存到 keystore
    if (window.electronAPI) {
      const result = await window.electronAPI.keystoreSet(
        `model_key_${keyDialogConfig.value.id}`,
        keyInput.value,
      )
      if (!result.success) {
        keyError.value = result.error || '保存密钥失败'
        return
      }
    }
    // 更新 has_key 状态（所有环境）
    await modelApi.updateConfig(keyDialogConfig.value.id, { has_key: true })
    closeKeyDialog()
    await fetchConfigs()
  } catch (e: unknown) {
    keyError.value = e instanceof Error ? e.message : '保存密钥失败'
  } finally {
    keySaving.value = false
  }
}

// ── 连接测试 ──
async function testConnection(config: ModelConfig) {
  testingId.value = config.id
  testLoading.value = false
  testMessage.value = ''

  // 先尝试从 keystore 获取密钥（Electron 模式）
  if (config.has_key && window.electronAPI) {
    try {
      const result = await window.electronAPI.keystoreGet(`model_key_${config.id}`)
      if (result.success && result.value) {
        await doTest(config.id, result.value)
        return
      }
      // 密钥已丢失（如用户在系统 keychain 中手动清除）
      // 同步更新 has_key 状态
      testMessage.value = '密钥已丢失，请重新配置密钥'
      testSuccess.value = false
      await modelApi.updateConfig(config.id, { has_key: false })
      await fetchConfigs()
      return
    } catch {
      // 获取失败，回退到手动输入
    }
  }

  // Browser 模式或密钥不可用时，弹出输入框
  testKeyDialogConfig.value = config
  testKeyInput.value = ''
  testKeyDialogVisible.value = true
}

function closeTestKeyDialog() {
  testKeyDialogVisible.value = false
  testKeyDialogConfig.value = null
  testKeyInput.value = ''
  testingId.value = null
  testMessage.value = ''
}

async function doTestConnectionWithKey() {
  if (!testKeyInput.value || !testKeyDialogConfig.value) return
  await doTest(testKeyDialogConfig.value.id, testKeyInput.value)
  closeTestKeyDialog()
}

async function doTest(configId: number, apiKey: string) {
  testLoading.value = true
  testSuccess.value = false
  testMessage.value = '测试中...'
  try {
    const res = await modelApi.testConnection(configId, apiKey)
    testSuccess.value = true
    testMessage.value = res.message || '连接成功'
    await fetchConfigs()
  } catch (e: unknown) {
    testSuccess.value = false
    testMessage.value = e instanceof Error ? e.message : '连接测试失败'
  } finally {
    testLoading.value = false
  }
}

// ── 辅助函数 ──
function statusLabel(status: string): string {
  const map: Record<string, string> = {
    active: '可用',
    inactive: '未测试',
    error: '异常',
  }
  return map[status] || status
}

function statusClass(status: string): string {
  const map: Record<string, string> = {
    active: 'text-success bg-green-50',
    inactive: 'text-text-tertiary bg-hover',
    error: 'text-error bg-red-50',
  }
  return map[status] || 'text-text-tertiary bg-hover'
}

// ── 生命周期 ──
onMounted(async () => {
  await Promise.all([fetchProviders(), fetchConfigs()])
})
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
}
.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>

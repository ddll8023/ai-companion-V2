<template>
  <main class="p-6 max-w-5xl">
    <!-- 头部横幅 -->
    <header
      class="relative overflow-hidden mb-6 p-6 rounded-2xl border border-primary/15 bg-gradient-to-br from-primary/10 via-surface to-surface"
    >
      <font-awesome-icon
        :icon="['fas', 'brain']"
        class="absolute -right-4 -top-6 text-[7rem] text-primary/10 pointer-events-none"
      />
      <div class="relative flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 class="text-xl font-semibold text-text">人物理解</h2>
          <p class="mt-1 text-sm text-text-secondary">
            AI 正在持续理解你的思考方式、动机与沟通风格
          </p>
        </div>
        <button
          class="relative px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-dark transition-all disabled:opacity-50 disabled:cursor-not-allowed glow-btn"
          :disabled="reflecting"
          @click="handleReflect"
        >
          <font-awesome-icon
            :icon="['fas', reflecting ? 'spinner' : 'wand-magic-sparkles']"
            :class="{ 'animate-spin': reflecting }"
            class="mr-1"
          />
          {{ reflecting ? '反思中...' : '立即反思' }}
        </button>
      </div>
      <!-- 统计小卡 -->
      <div class="relative mt-5 grid grid-cols-3 gap-3">
        <div class="p-3 bg-white/60 border border-border rounded-xl">
          <p class="text-2xl font-semibold text-text leading-none">{{ establishedCount }}</p>
          <p class="mt-1.5 text-xs text-text-secondary">稳定洞见</p>
        </div>
        <div class="p-3 bg-white/60 border border-border rounded-xl">
          <p class="text-2xl font-semibold text-text leading-none">{{ observations.length }}</p>
          <p class="mt-1.5 text-xs text-text-secondary">观察累计</p>
        </div>
        <div class="p-3 bg-white/60 border border-border rounded-xl">
          <p class="text-2xl font-semibold text-text leading-none">{{ document ? `v${document.version}` : '--' }}</p>
          <p class="mt-1.5 text-xs text-text-secondary">侧写版本</p>
        </div>
      </div>
    </header>

    <!-- 人物侧写 -->
    <section class="mb-8 p-5 bg-surface border border-border rounded-xl">
      <div class="flex flex-wrap items-center gap-2 mb-4">
        <h3 class="text-sm font-medium text-text mr-auto">
          <font-awesome-icon :icon="['fas', 'id-card']" class="mr-1.5 text-primary" />
          人物侧写
        </h3>
        <span v-if="document" class="text-xs px-2 py-0.5 rounded-full bg-hover text-text-secondary">
          引用 {{ document.cited_insight_ids.length }} 条洞见
        </span>
        <span v-if="document?.change_summary" class="text-xs text-text-tertiary" :title="document.change_summary">
          {{ document.change_summary }}
        </span>
        <button
          v-if="document"
          class="text-xs text-primary hover:underline"
          @click="editingDocument = !editingDocument"
        >
          {{ editingDocument ? '取消编辑' : '编辑侧写' }}
        </button>
      </div>
      <div v-if="editingDocument" class="space-y-3">
        <textarea
          v-model="documentDraft"
          rows="14"
          class="w-full p-3 text-sm border border-border rounded-lg bg-bg text-text resize-y focus:outline-none focus:border-primary transition-colors"
        />
        <div class="flex justify-end gap-2">
          <button
            class="px-3 py-1.5 text-sm text-text-secondary hover:text-text transition-colors"
            @click="editingDocument = false"
          >
            取消
          </button>
          <button
            class="px-4 py-1.5 text-sm text-white bg-primary rounded-lg hover:bg-primary-dark transition-colors"
            :disabled="savingDocument"
            @click="saveDocument"
          >
            <font-awesome-icon
              :icon="['fas', savingDocument ? 'spinner' : 'floppy-disk']"
              :class="{ 'animate-spin': savingDocument }"
              class="mr-1"
            />
            保存
          </button>
        </div>
      </div>
      <article
        v-else-if="document"
        class="relative prose prose-sm max-w-none whitespace-pre-wrap text-text leading-relaxed pl-4 border-l-2 border-primary/30"
      >
        {{ document.content }}
      </article>
      <div v-else class="flex flex-col items-center py-10 text-center">
        <font-awesome-icon :icon="['fas', 'user-astronaut']" class="text-4xl text-primary/30 mb-3" />
        <p class="text-sm text-text-tertiary">
          还没有形成侧写。继续对话，系统会从你的表达和选择中逐步建立理解。
        </p>
      </div>
    </section>

    <!-- 洞见 -->
    <section class="mb-8">
      <div class="mb-3 flex items-center justify-between">
        <h3 class="text-sm font-medium text-text">
          <font-awesome-icon :icon="['fas', 'lightbulb']" class="mr-1.5 text-primary" />
          人物洞见
        </h3>
        <span class="text-xs text-text-tertiary">自动演化 · 你只需在必要时纠正</span>
      </div>
      <LoadingState :loading="loadingInsights" loading-text="加载洞见...">
        <EmptyState :empty="insights.length === 0" empty-text="暂无洞见，继续对话后自动形成">
          <TransitionGroup name="insight" tag="div" class="space-y-3">
            <article
              v-for="item in insights"
              :key="item.id"
              class="group p-4 bg-surface border border-border rounded-xl hover:shadow-md hover:-translate-y-0.5 transition-all duration-200"
              :class="{ 'opacity-60': isDormant(item) }"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="flex flex-wrap items-center gap-2 mb-1.5">
                    <span class="text-xs px-2 py-0.5 rounded-full font-medium" :class="dimensionBadge(item.dimension)">
                      {{ item.dimension }}
                    </span>
                    <span class="text-xs px-2 py-0.5 rounded-full" :class="maturityBadge(item.maturity)">
                      {{ maturityLabel(item.maturity) }}
                    </span>
                    <span v-if="item.user_override" class="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary">
                      已人工修订
                    </span>
                    <span v-if="item.contradiction_count > 0" class="text-xs px-2 py-0.5 rounded-full bg-error/10 text-error">
                      <font-awesome-icon :icon="['fas', 'triangle-exclamation']" class="mr-0.5" />
                      {{ item.contradiction_count }} 条矛盾证据
                    </span>
                    <span class="text-xs text-text-tertiary">v{{ item.version }}</span>
                  </div>
                  <p class="text-sm text-text leading-relaxed">{{ item.content }}</p>
                </div>
                <div class="flex gap-1 shrink-0 opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity">
                  <button class="p-1.5 text-text-tertiary hover:text-primary rounded-md hover:bg-hover" title="纠正" @click="openCorrection(item)">
                    <font-awesome-icon :icon="['fas', 'pen']" />
                  </button>
                  <button class="p-1.5 text-text-tertiary hover:text-error rounded-md hover:bg-error/10" title="否定" @click="handleReject(item)">
                    <font-awesome-icon :icon="['fas', 'xmark']" />
                  </button>
                </div>
              </div>
              <!-- 成熟度 / 置信度 / 稳定度 -->
              <div class="mt-3 grid grid-cols-3 gap-4">
                <div>
                  <div class="flex items-center justify-between mb-1">
                    <span class="text-xs text-text-tertiary">成熟度</span>
                    <span class="text-xs text-text-tertiary">{{ maturityProgress(item) }}%</span>
                  </div>
                  <div class="h-1.5 rounded-full bg-hover overflow-hidden">
                    <div class="h-full rounded-full bg-gradient-to-r from-primary/60 to-primary transition-all duration-700" :style="{ width: `${maturityProgress(item)}%` }" />
                  </div>
                </div>
                <div>
                  <div class="flex items-center justify-between mb-1">
                    <span class="text-xs text-text-tertiary">置信度</span>
                    <span class="text-xs text-text-tertiary">{{ item.confidence }}%</span>
                  </div>
                  <div class="h-1.5 rounded-full bg-hover overflow-hidden">
                    <div class="h-full rounded-full bg-gradient-to-r from-success/50 to-success transition-all duration-700" :style="{ width: `${item.confidence}%` }" />
                  </div>
                </div>
                <div>
                  <div class="flex items-center justify-between mb-1">
                    <span class="text-xs text-text-tertiary">稳定度</span>
                    <span class="text-xs text-text-tertiary">{{ item.stability_score }}%</span>
                  </div>
                  <div class="h-1.5 rounded-full bg-hover overflow-hidden">
                    <div class="h-full rounded-full bg-gradient-to-r from-[#7C9CF5]/60 to-[#7C9CF5] transition-all duration-700" :style="{ width: `${item.stability_score}%` }" />
                  </div>
                </div>
              </div>
              <p class="mt-2 text-xs text-text-tertiary">
                <font-awesome-icon :icon="['fas', 'magnifying-glass-chart']" class="mr-1" />
                {{ item.support_count }} 条支持证据
              </p>
            </article>
          </TransitionGroup>
        </EmptyState>
      </LoadingState>
    </section>

    <!-- 观察流 -->
    <section>
      <div class="mb-3 flex items-center justify-between">
        <h3 class="text-sm font-medium text-text">
          <font-awesome-icon :icon="['fas', 'stream']" class="mr-1.5 text-primary" />
          观察流
        </h3>
        <span class="text-xs text-text-tertiary">从对话中提取的原始证据</span>
      </div>
      <LoadingState :loading="loadingObservations" loading-text="加载观察...">
        <EmptyState :empty="observations.length === 0" empty-text="暂无观察，对话后系统会自动提取">
          <TransitionGroup name="observation" tag="div" class="relative pl-5 space-y-4">
            <!-- 时间线竖线 -->
            <div class="absolute left-[5px] top-2 bottom-2 w-px bg-border" />
            <article
              v-for="item in observations"
              :key="item.id"
              class="relative group"
            >
              <span
                class="absolute -left-5 top-2.5 w-[11px] h-[11px] rounded-full border-2 bg-surface"
                :class="typeDot(item.observation_type)"
              />
              <div class="p-3.5 bg-surface border border-border rounded-lg hover:border-primary/40 transition-colors">
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <div class="flex flex-wrap items-center gap-2 mb-1">
                      <span class="text-xs px-1.5 py-0.5 rounded bg-primary/10 text-primary">{{ item.dimension }}</span>
                      <span class="text-xs px-1.5 py-0.5 rounded bg-hover text-text-secondary">{{ typeLabel(item.observation_type) }}</span>
                      <span class="text-xs text-text-tertiary">{{ formatTime(item.created_at) }}</span>
                    </div>
                    <p class="text-sm text-text">{{ item.content }}</p>
                    <blockquote class="mt-1.5 pl-3 border-l-2 border-border text-xs text-text-tertiary italic">
                      “{{ item.evidence }}”
                    </blockquote>
                  </div>
                  <button
                    class="p-1.5 text-text-tertiary hover:text-error rounded-md hover:bg-error/10 shrink-0"
                    title="删除观察"
                    @click="handleDeleteObservation(item)"
                  >
                    <font-awesome-icon :icon="['fas', 'trash-can']" />
                  </button>
                </div>
              </div>
            </article>
          </TransitionGroup>
        </EmptyState>
      </LoadingState>
    </section>

    <!-- 纠正洞见弹窗 -->
    <Transition name="fade">
      <div
        v-if="correctionTarget"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-[2px]"
        @click.self="correctionTarget = null"
      >
        <div class="w-[32rem] p-5 bg-surface rounded-xl border border-border shadow-xl">
          <h3 class="mb-3 text-base font-medium text-text">纠正洞见</h3>
          <textarea
            v-model="correctionDraft"
            rows="5"
            class="w-full p-3 text-sm border border-border rounded-lg bg-bg text-text resize-none focus:outline-none focus:border-primary transition-colors"
          />
          <div class="mt-3 flex justify-end gap-2">
            <button class="px-3 py-1.5 text-sm text-text-secondary hover:text-text transition-colors" @click="correctionTarget = null">
              取消
            </button>
            <button class="px-4 py-1.5 text-sm text-white bg-primary rounded-lg hover:bg-primary-dark transition-colors" @click="saveCorrection">
              保存
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import EmptyState from '@/components/custom/EmptyState.vue'
import LoadingState from '@/components/custom/LoadingState.vue'
import { correctInsight, deleteObservation, editPersonaDocument, getPersonaDocument, listInsights, listObservations, reflectPersona, rejectInsight } from '@/api/persona'
import { formatTime } from '@/utils/format'
import type { Insight, Observation, PersonaDocument } from '@/types/api'

const document = ref<PersonaDocument | null>(null)
const documentDraft = ref('')
const editingDocument = ref(false)
const savingDocument = ref(false)
const reflecting = ref(false)
const loadingInsights = ref(false)
const loadingObservations = ref(false)
const insights = ref<Insight[]>([])
const observations = ref<Observation[]>([])
const correctionTarget = ref<Insight | null>(null)
const correctionDraft = ref('')

const MATURITY_WEIGHT: Record<Insight['maturity'], number> = {
  established: 0,
  developing: 1,
  emerging: 2,
  superseded: 3,
  declining: 4,
  rejected: 5,
}

const MATURITY_LABEL: Record<Insight['maturity'], string> = {
  emerging: '初步',
  developing: '形成中',
  established: '已建立',
  declining: '减弱中',
  superseded: '已取代',
  rejected: '已否定',
}

/** 成熟度进度（用于进度条展示） */
const MATURITY_PROGRESS: Record<Insight['maturity'], number> = {
  emerging: 25,
  developing: 55,
  established: 100,
  declining: 70,
  superseded: 0,
  rejected: 0,
}

/** 洞见排序：已建立优先，减弱/否定置底 */
const sortedInsights = computed(() =>
  [...insights.value].sort((a, b) => MATURITY_WEIGHT[a.maturity] - MATURITY_WEIGHT[b.maturity]),
)

const establishedCount = computed(() =>
  insights.value.filter((item) => item.maturity === 'established').length,
)

function isDormant(item: Insight): boolean {
  return item.maturity === 'superseded' || item.maturity === 'rejected'
}

/** 维度徽章：按维度哈希取色，保证同一维度颜色稳定 */
const DIMENSION_STYLES = [
  'bg-primary/10 text-primary',
  'bg-success/10 text-success',
  'bg-[#7C9CF5]/10 text-[#5B7CE8]',
  'bg-[#9B7CF5]/10 text-[#7A5CE8]',
  'bg-[#F57CB8]/10 text-[#E85B9B]',
  'bg-[#5CB8F5]/10 text-[#3B9BE8]',
]

function hashDimension(value: string): number {
  let hash = 0
  for (let i = 0; i < value.length; i++) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0
  }
  return hash
}

function dimensionBadge(dimension: string): string {
  return DIMENSION_STYLES[hashDimension(dimension) % DIMENSION_STYLES.length]
}

function maturityBadge(maturity: Insight['maturity']): string {
  const map: Record<Insight['maturity'], string> = {
    emerging: 'bg-[#7C9CF5]/10 text-[#5B7CE8]',
    developing: 'bg-primary/10 text-primary',
    established: 'bg-success/10 text-success',
    declining: 'bg-error/10 text-error',
    superseded: 'bg-hover text-text-secondary',
    rejected: 'bg-hover text-text-secondary',
  }
  return map[maturity]
}

function maturityLabel(maturity: Insight['maturity']): string {
  return MATURITY_LABEL[maturity]
}

function maturityProgress(item: Insight): number {
  return MATURITY_PROGRESS[item.maturity]
}

/** 观察类型：圆点颜色与标签 */
function typeDot(type: string): string {
  const map: Record<string, string> = {
    content: 'border-primary',
    expression: 'border-success',
    emotion: 'border-[#9B7CF5]',
    interaction: 'border-[#5CB8F5]',
  }
  return map[type] ?? 'border-text-tertiary'
}

function typeLabel(type: string): string {
  const map: Record<string, string> = {
    content: '内容观察',
    expression: '表达观察',
    emotion: '情绪观察',
    interaction: '互动观察',
  }
  return map[type] ?? type
}

async function fetchData() {
  loadingInsights.value = true
  loadingObservations.value = true
  try {
    insights.value = (await listInsights({})).data.lists
  } finally {
    loadingInsights.value = false
  }
  try {
    observations.value = (await listObservations()).data.lists
  } finally {
    loadingObservations.value = false
  }
  const response = await getPersonaDocument()
  document.value = response.data
  documentDraft.value = response.data?.content || ''
}

async function handleReflect() {
  reflecting.value = true
  try {
    await reflectPersona()
  } finally {
    reflecting.value = false
  }
}

async function saveDocument() {
  savingDocument.value = true
  try {
    const response = await editPersonaDocument(documentDraft.value)
    document.value = response.data
    editingDocument.value = false
  } finally {
    savingDocument.value = false
  }
}

function openCorrection(item: Insight) {
  correctionTarget.value = item
  correctionDraft.value = item.content
}

async function saveCorrection() {
  if (!correctionTarget.value) return
  await correctInsight(correctionTarget.value.id, correctionDraft.value)
  correctionTarget.value = null
  await fetchData()
}

async function handleReject(item: Insight) {
  await rejectInsight(item.id)
  await fetchData()
}

async function handleDeleteObservation(item: Observation) {
  await deleteObservation(item.id)
  observations.value = observations.value.filter((entry) => entry.id !== item.id)
}

onMounted(fetchData)
</script>

<style scoped>
/* 反思按钮光晕 */
.glow-btn {
  box-shadow: 0 0 0 0 rgba(245, 166, 35, 0.35);
}
.glow-btn:hover:not(:disabled) {
  box-shadow: 0 0 18px 2px rgba(245, 166, 35, 0.35);
}

/* 洞见列表入场动画 */
.insight-enter-active,
.insight-leave-active,
.observation-enter-active,
.observation-leave-active {
  transition: all 0.3s ease;
}
.insight-enter-from,
.observation-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.insight-leave-to,
.observation-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* 弹窗淡入 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

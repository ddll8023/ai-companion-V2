<template>
  <main class="p-6 max-w-5xl">
    <header class="mb-6 flex items-start justify-between">
      <div>
        <h2 class="text-xl font-semibold text-text">人物理解</h2>
        <p class="mt-1 text-sm text-text-secondary">AI 正在持续理解你的思考方式、动机与沟通风格</p>
      </div>
      <button class="px-4 py-2 text-sm text-white bg-primary rounded-lg disabled:opacity-50" :disabled="reflecting" @click="handleReflect">
        <font-awesome-icon :icon="['fas', reflecting ? 'spinner' : 'brain']" :class="{ 'animate-spin': reflecting }" class="mr-1" />
        {{ reflecting ? '反思中...' : '立即反思' }}
      </button>
    </header>

    <section class="mb-6 p-5 bg-surface border border-border rounded-xl">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-sm font-medium text-text">人物侧写</h3>
        <button v-if="document" class="text-xs text-primary" @click="editingDocument = !editingDocument">{{ editingDocument ? '取消编辑' : '编辑侧写' }}</button>
      </div>
      <div v-if="editingDocument" class="space-y-3">
        <textarea v-model="documentDraft" rows="14" class="w-full p-3 text-sm border border-border rounded-lg bg-bg text-text resize-y" />
        <button class="px-3 py-1.5 text-sm text-white bg-primary rounded-lg" :disabled="savingDocument" @click="saveDocument">保存</button>
      </div>
      <article v-else-if="document" class="prose prose-sm max-w-none whitespace-pre-wrap text-text leading-relaxed">{{ document.content }}</article>
      <p v-else class="text-sm text-text-tertiary">还没有形成侧写。继续对话，系统会从你的表达和选择中逐步建立理解。</p>
    </section>

    <section class="mb-6">
      <div class="mb-3 flex items-center justify-between"><h3 class="text-sm font-medium text-text">稳定洞见</h3><span class="text-xs text-text-tertiary">自动演化 · 你只需在必要时纠正</span></div>
      <LoadingState :loading="loadingInsights" loading-text="加载洞见...">
        <EmptyState :empty="insights.length === 0" empty-text="暂无稳定洞见">
          <div class="space-y-3">
            <article v-for="item in insights" :key="item.id" class="p-4 bg-surface border border-border rounded-lg">
              <div class="flex items-start justify-between gap-3"><div><div class="flex items-center gap-2 mb-1"><span class="text-xs px-1.5 py-0.5 rounded bg-primary/10 text-primary">{{ item.dimension }}</span><span class="text-xs text-text-tertiary">{{ maturityLabel(item.maturity) }} · {{ item.confidence }}%</span></div><p class="text-sm text-text leading-relaxed">{{ item.content }}</p><p class="mt-2 text-xs text-text-tertiary">{{ item.support_count }} 条支持证据 · 稳定度 {{ item.stability_score }}%</p></div><div class="flex gap-1 shrink-0"><button class="p-1.5 text-text-tertiary hover:text-primary" title="纠正" @click="openCorrection(item)"><font-awesome-icon :icon="['fas', 'pen']" /></button><button class="p-1.5 text-text-tertiary hover:text-error" title="否定" @click="handleReject(item)"><font-awesome-icon :icon="['fas', 'xmark']" /></button></div></div>
            </article>
          </div>
        </EmptyState>
      </LoadingState>
    </section>

    <section><h3 class="mb-3 text-sm font-medium text-text">观察流</h3><LoadingState :loading="loadingObservations" loading-text="加载观察..."><EmptyState :empty="observations.length === 0" empty-text="暂无观察"><div class="space-y-2"><article v-for="item in observations" :key="item.id" class="p-3 bg-surface border border-border rounded-lg"><div class="flex items-start justify-between gap-3"><div><span class="text-xs text-primary">{{ item.dimension }}</span><p class="mt-1 text-sm text-text">{{ item.content }}</p><p class="mt-1 text-xs text-text-tertiary">证据：“{{ item.evidence }}”</p></div><button class="p-1.5 text-xs text-text-tertiary hover:text-error" title="删除观察" @click="handleDeleteObservation(item)"><font-awesome-icon :icon="['fas', 'trash-can']" /></button></div></article></div></EmptyState></LoadingState></section>

    <Transition name="fade"><div v-if="correctionTarget" class="fixed inset-0 z-50 flex items-center justify-center bg-black/30" @click.self="correctionTarget = null"><div class="w-[32rem] p-5 bg-surface rounded-xl border border-border shadow-lg"><h3 class="mb-3 text-base font-medium text-text">纠正洞见</h3><textarea v-model="correctionDraft" rows="5" class="w-full p-3 text-sm border border-border rounded-lg bg-bg text-text resize-none" /><div class="mt-3 flex justify-end gap-2"><button class="px-3 py-1.5 text-sm text-text-secondary" @click="correctionTarget = null">取消</button><button class="px-3 py-1.5 text-sm text-white bg-primary rounded-lg" @click="saveCorrection">保存</button></div></div></div></Transition>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import EmptyState from '@/components/custom/EmptyState.vue'
import LoadingState from '@/components/custom/LoadingState.vue'
import { correctInsight, deleteObservation, editPersonaDocument, getPersonaDocument, listInsights, listObservations, reflectPersona, rejectInsight } from '@/api/persona'
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

async function fetchData() {
  loadingInsights.value = true
  loadingObservations.value = true
  try { insights.value = (await listInsights({ maturity: 'established' })).data.lists } finally { loadingInsights.value = false }
  try { observations.value = (await listObservations()).data.lists } finally { loadingObservations.value = false }
  const response = await getPersonaDocument()
  document.value = response.data
  documentDraft.value = response.data?.content || ''
}
async function handleReflect() { reflecting.value = true; try { await reflectPersona() } finally { reflecting.value = false } }
async function saveDocument() { savingDocument.value = true; try { const response = await editPersonaDocument(documentDraft.value); document.value = response.data; editingDocument.value = false } finally { savingDocument.value = false } }
function openCorrection(item: Insight) { correctionTarget.value = item; correctionDraft.value = item.content }
async function saveCorrection() { if (!correctionTarget.value) return; await correctInsight(correctionTarget.value.id, correctionDraft.value); correctionTarget.value = null; await fetchData() }
async function handleReject(item: Insight) { await rejectInsight(item.id); await fetchData() }
async function handleDeleteObservation(item: Observation) { await deleteObservation(item.id); observations.value = observations.value.filter((entry) => entry.id !== item.id) }
function maturityLabel(value: string) { return ({ emerging: '初步', developing: '形成中', established: '已建立', declining: '减弱中' } as Record<string, string>)[value] || value }
onMounted(fetchData)
</script>

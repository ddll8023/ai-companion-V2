<template>
  <div ref="root" class="markdown-body text-sm leading-relaxed" v-html="renderedHtml" />
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'

const props = defineProps<{
  content: string
}>()

onMounted(() => {
  marked.use({
    breaks: true,
    gfm: true,
    async: false,
    langPrefix: 'hljs language-',
    highlight(code: string, lang: string): string {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(code, { language: lang }).value
      }
      return hljs.highlightAuto(code).value
    },
  })
})

const renderedHtml = computed(() => {
  if (!props.content) return ''
  // trimEnd：去掉模型回复尾随换行，避免 breaks:true 将行尾 \n 渲染成 <br> 产生多余空行
  return marked.parse(props.content.trimEnd()) as string
})

// 当前显示"已复制"的按钮，用于恢复文案
let copiedBtn: HTMLButtonElement | null = null
let copiedTimer: number | null = null

const root = ref<HTMLElement | null>(null)

/** 给代码块挂载复制按钮（每次内容渲染后重建，避免重复） */
function attachCopyButtons() {
  const container = root.value
  if (!container) return
  container.querySelectorAll<HTMLButtonElement>('.md-copy-btn').forEach((btn) => btn.remove())
  container.querySelectorAll('pre').forEach((pre) => {
    if (!pre.querySelector('code')) return
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.className = 'md-copy-btn'
    btn.textContent = '复制'
    btn.addEventListener('click', (e) => {
      e.stopPropagation()
      const code = pre.querySelector('code')?.textContent ?? pre.textContent ?? ''
      void copyText(code)
      if (copiedTimer !== null) window.clearTimeout(copiedTimer)
      if (copiedBtn) copiedBtn.textContent = '复制'
      btn.textContent = '已复制'
      btn.classList.add('copied')
      copiedBtn = btn
      copiedTimer = window.setTimeout(() => {
        btn.textContent = '复制'
        btn.classList.remove('copied')
        copiedBtn = null
      }, 1500)
    })
    pre.appendChild(btn)
  })
}

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // 非安全上下文（如 http）降级为 execCommand
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    ta.remove()
  }
}

watch(renderedHtml, async () => {
  await nextTick()
  attachCopyButtons()
})

onMounted(async () => {
  await nextTick()
  attachCopyButtons()
})
</script>

<style>
/* ── Markdown 渲染样式 ────────────────────────────────────────────── */

.markdown-body {
  word-break: break-word;
  line-height: 1.7;
}

/* 标题 */
.markdown-body h1,
.markdown-body h2,
.markdown-body h3,
.markdown-body h4 {
  font-weight: 600;
  margin-top: 1.25em;
  margin-bottom: 0.5em;
  line-height: 1.3;
}
.markdown-body h1 { font-size: 1.25rem; }
.markdown-body h2 { font-size: 1.15rem; }
.markdown-body h3 { font-size: 1.05rem; }
.markdown-body h4 { font-size: 1rem; }

/* 段落 */
.markdown-body p {
  margin-bottom: 0.5em;
}
.markdown-body p:last-child {
  margin-bottom: 0;
}

/* 代码块/列表/引用等结尾元素不留底部边距，避免气泡内多余空白 */
.markdown-body > :last-child {
  margin-bottom: 0;
}

/* 列表 */
.markdown-body ul,
.markdown-body ol {
  margin: 0.3em 0;
  padding-left: 1.5em;
}
.markdown-body li {
  margin-bottom: 0.15em;
}
.markdown-body li > ul,
.markdown-body li > ol {
  margin: 0;
}

/* 引用 */
.markdown-body blockquote {
  border-left: 3px solid var(--border-color, #d1d5db);
  padding: 0.25em 0 0.25em 0.75em;
  margin: 0.5em 0;
  color: var(--quote-color, #6b7280);
  font-style: italic;
}

/* 代码块 */
.markdown-body pre {
  border-radius: 8px;
  padding: 0.75em 1em;
  margin: 0.6em 0;
  overflow-x: auto;
  font-size: 0.8125rem;
  line-height: 1.5;
  position: relative;
  background: #f4f4f5 !important;
  border: 1px solid #e4e4e7;
}

/* 代码块复制按钮 */
.markdown-body .md-copy-btn {
  position: absolute;
  top: 0.5em;
  right: 0.5em;
  padding: 0.2em 0.6em;
  font-size: 0.6875rem;
  line-height: 1.4;
  color: #8b8b93;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid #e0e0e4;
  border-radius: 6px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}
.markdown-body pre:hover .md-copy-btn {
  opacity: 1;
}
.markdown-body .md-copy-btn:hover {
  color: var(--color-primary-dark, #d4890a);
  border-color: var(--color-primary-light, #fdebd0);
}
.markdown-body .md-copy-btn.copied {
  color: var(--color-success, #52c41a);
  border-color: var(--color-success, #52c41a);
  opacity: 1;
}

/* 行内代码 */
.markdown-body code {
  font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
  font-size: 0.8em;
  padding: 0.15em 0.35em;
  border-radius: 4px;
  background: #f0f0f0;
  border: 1px solid #e0e0e0;
}
.markdown-body pre code {
  background: none !important;
  border: none !important;
  padding: 0;
  font-size: inherit;
  color: inherit;
}

/* 表格 */
.markdown-body table {
  border-collapse: collapse;
  width: 100%;
  margin: 0.6em 0;
  font-size: 0.875rem;
}
.markdown-body th,
.markdown-body td {
  border: 1px solid #e0e0e0;
  padding: 0.4em 0.6em;
  text-align: left;
}
.markdown-body th {
  background: #f8f8f8;
  font-weight: 600;
}

/* 链接 */
.markdown-body a {
  text-decoration: underline;
  opacity: 0.9;
}
.markdown-body a:hover {
  opacity: 1;
}

/* 分割线 */
.markdown-body hr {
  border: none;
  border-top: 1px solid #e0e0e0;
  margin: 1em 0;
}

/* 加粗 */
.markdown-body strong {
  font-weight: 600;
}
</style>

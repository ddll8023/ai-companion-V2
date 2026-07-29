<template>
  <div class="markdown-body text-sm leading-relaxed" v-html="renderedHtml" />
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
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
  return marked.parse(props.content) as string
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

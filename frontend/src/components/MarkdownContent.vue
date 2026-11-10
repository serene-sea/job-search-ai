<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'

const props = defineProps<{ text: string }>()

// 模型的回答只是文字，不能让它夹带 HTML 在页面中执行。
// markdown-it 会把原始 HTML 转义；图片也关掉，避免回答偷偷加载外部图片。
const markdown = new MarkdownIt({ html: false, linkify: false, breaks: true })
markdown.disable('image')
const rendered = computed(() => markdown.render(props.text))
</script>

<template>
  <!-- 只有上面处理过的 HTML 才能进入 v-html；不要把模型原文直接传给它。 -->
  <div class="markdown-content break-words" v-html="rendered"></div>
</template>

<style scoped>
.markdown-content :deep(:first-child) { margin-top: 0; }
.markdown-content :deep(:last-child) { margin-bottom: 0; }
.markdown-content :deep(p) { margin: 0.5rem 0; }
.markdown-content :deep(h1), .markdown-content :deep(h2), .markdown-content :deep(h3) {
  margin: 0.9rem 0 0.4rem;
  font-weight: 700;
  line-height: 1.4;
}
.markdown-content :deep(h1) { font-size: 1.3rem; }
.markdown-content :deep(h2) { font-size: 1.15rem; }
.markdown-content :deep(h3) { font-size: 1.05rem; }
.markdown-content :deep(strong) { font-weight: 700; }
.markdown-content :deep(ul) { margin: 0.5rem 0; padding-left: 1.4rem; list-style: disc; }
.markdown-content :deep(ol) { margin: 0.5rem 0; padding-left: 1.4rem; list-style: decimal; }
.markdown-content :deep(li) { margin: 0.2rem 0; }
.markdown-content :deep(a) { color: #047857; text-decoration: underline; }
.markdown-content :deep(blockquote) { margin: 0.6rem 0; padding-left: 0.8rem; border-left: 3px solid #cbd5e1; color: #475569; }
.markdown-content :deep(code) { padding: 0.1rem 0.25rem; border-radius: 0.25rem; background: #f1f5f9; }
.markdown-content :deep(pre) { margin: 0.6rem 0; overflow-x: auto; padding: 0.75rem; border-radius: 0.5rem; background: #f1f5f9; }
.markdown-content :deep(pre code) { padding: 0; background: none; }
</style>

<template>
  <main class="mx-auto max-w-[1050px] px-4 py-6 sm:px-8 sm:py-8">
    <p class="text-xs font-extrabold tracking-widest text-emerald-700">个人资料</p>
    <h1 class="mt-1 text-3xl font-bold">项目经历</h1>
    <p class="mt-2 text-sm text-slate-600">只填写真实参与和理解的工作；技术亮点可以写你能解释的实现与取舍。</p>
    <p v-if="error" role="alert" class="mt-5 rounded-lg bg-red-50 p-3 text-sm text-red-800">{{ error }}</p>
    <p v-if="notice" role="status" class="mt-5 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">{{ notice }}</p>
    <form class="mt-6 grid gap-4 rounded-2xl border border-slate-200 bg-white p-5 sm:p-7" @submit.prevent="save">
      <h2 class="text-lg font-bold">{{ editingId === null ? '添加项目' : '编辑项目' }}</h2>
      <label class="grid gap-2 text-sm font-bold">项目名称<input v-model="draft.name" required maxlength="200" class="rounded-lg border border-slate-300 px-3 py-2 font-normal" placeholder="例如：Video Assistant" /></label>
      <label class="grid gap-2 text-sm font-bold">大概介绍<textarea v-model="draft.summary" maxlength="10000" rows="4" class="rounded-lg border border-slate-300 px-3 py-2 font-normal" placeholder="项目解决什么问题、你实际完成了什么"></textarea></label>
      <label class="grid gap-2 text-sm font-bold">在线链接（可选）<input v-model="draft.source_url" type="url" maxlength="1000" class="rounded-lg border border-slate-300 px-3 py-2 font-normal" placeholder="https://..." /></label>
      <label class="grid gap-2 text-sm font-bold">技术亮点<textarea v-model="draft.highlights" maxlength="10000" rows="5" class="rounded-lg border border-slate-300 px-3 py-2 font-normal" placeholder="关键技术、难点、你能讲清楚的设计与结果"></textarea></label>
      <div class="flex justify-end gap-3"><button v-if="editingId !== null" type="button" class="rounded-lg border border-slate-300 px-4 py-2 text-sm" @click="reset">取消编辑</button><button type="submit" :disabled="busy" class="rounded-lg bg-emerald-700 px-5 py-2 text-sm font-bold text-white disabled:opacity-60">{{ busy ? '保存中…' : '保存项目' }}</button></div>
    </form>
    <section class="mt-6 rounded-2xl border border-slate-200 bg-white p-5 sm:p-7">
      <h2 class="text-lg font-bold">我的项目（{{ entries.length }}）</h2>
      <p v-if="loading" class="mt-4 text-sm text-slate-500">正在读取…</p>
      <p v-else-if="!entries.length" class="mt-4 text-sm text-slate-500">还没有项目记录。</p>
      <ul v-else class="mt-3 divide-y divide-slate-100">
        <li v-for="entry in entries" :key="entry.id" class="flex flex-wrap justify-between gap-3 py-4">
          <div class="min-w-0"><strong>{{ entry.name }}</strong><p v-if="entry.summary" class="mt-2 whitespace-pre-wrap text-sm text-slate-600">{{ entry.summary }}</p><p v-if="entry.highlights" class="mt-2 whitespace-pre-wrap text-sm text-slate-600"><strong>技术亮点：</strong>{{ entry.highlights }}</p><a v-if="entry.source_url" :href="entry.source_url" target="_blank" rel="noopener noreferrer" class="mt-2 inline-block break-all text-sm text-emerald-700 underline">在线链接</a></div>
          <div class="flex items-start gap-3 text-sm font-bold"><button class="text-emerald-700" @click="edit(entry)">编辑</button><button class="text-red-700" @click="remove(entry)">删除</button></div>
        </li>
      </ul>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ApiError } from '../auth'
import { createProject, deleteProject, listProjects, updateProject, type Project, type ProjectFields } from '../history'

type Draft = { name: string; summary: string; source_url: string; highlights: string }
const blank = (): Draft => ({ name: '', summary: '', source_url: '', highlights: '' })
const draft = ref<Draft>(blank())
const entries = ref<Project[]>([])
const editingId = ref<number | null>(null)
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const message = (cause: unknown) => cause instanceof ApiError ? cause.message : '操作失败，请稍后重试'
function reset() { draft.value = blank(); editingId.value = null }
function edit(entry: Project) {
  editingId.value = entry.id
  draft.value = { name: entry.name, summary: entry.summary ?? '', source_url: entry.source_url ?? '', highlights: entry.highlights ?? '' }
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
async function reload() { entries.value = await listProjects() }
onMounted(async () => { try { await reload() } catch (cause) { error.value = message(cause) } finally { loading.value = false } })
async function save() {
  if (busy.value) return
  const fields: ProjectFields = { name: draft.value.name.trim(), summary: draft.value.summary.trim() || null,
    source_url: draft.value.source_url.trim() || null, highlights: draft.value.highlights.trim() || null }
  busy.value = true; error.value = ''; notice.value = ''
  try {
    if (editingId.value === null) await createProject(fields)
    else await updateProject(editingId.value, fields)
    await reload(); reset(); notice.value = '项目已保存'
  } catch (cause) { error.value = message(cause) } finally { busy.value = false }
}
async function remove(entry: Project) {
  if (!window.confirm(`确定删除项目“${entry.name}”吗？`)) return
  busy.value = true; error.value = ''; notice.value = ''
  try { await deleteProject(entry.id); if (editingId.value === entry.id) reset(); await reload(); notice.value = '项目已删除' }
  catch (cause) { error.value = message(cause) } finally { busy.value = false }
}
</script>

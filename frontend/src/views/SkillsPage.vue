<template>
  <main class="mx-auto max-w-[1100px] px-4 py-6 sm:px-8 sm:py-8">
    <div class="mb-6">
      <p class="text-xs font-extrabold tracking-widest text-emerald-700">个人资料</p>
      <h1 class="mt-1 text-3xl font-bold">技能与能力定位</h1>
      <p class="mt-2 text-sm leading-7 text-slate-500">掌握程度如实填写；说明可以写会什么、缺少什么实战经验。</p>
      <button v-if="!showForm" type="button" class="mt-5 rounded-lg bg-emerald-700 px-4 py-2 text-sm font-bold text-white" @click="startCreate">添加技能</button>
    </div>
    <p v-if="error" class="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-800" role="alert">{{ error }}</p>
    <p v-if="notice" class="mb-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800" role="status">{{ notice }}</p>

    <form v-if="showForm" class="mb-6 grid gap-4 rounded-2xl border border-slate-200 bg-white p-5 sm:p-7" @submit.prevent="save">
      <h2 class="text-lg font-bold">{{ editingId === null ? '添加技能' : '编辑技能' }}</h2>
      <div class="grid gap-4 sm:grid-cols-3">
        <label class="grid gap-2 text-sm font-bold">技能名称<input v-model="draft.name" maxlength="100" required class="rounded-lg border border-slate-300 px-3 py-2 font-normal" placeholder="请输入技能名称" /></label>
        <label class="grid gap-2 text-sm font-bold">掌握程度<select v-model.number="draft.proficiency" class="rounded-lg border border-slate-300 px-3 py-2 font-normal"><option v-for="(label, index) in proficiencyLabels" :key="label" :value="index">{{ label }}</option></select></label>
        <label class="grid gap-2 text-sm font-bold">重要性（由低到高）<select v-model.number="draft.importance" class="rounded-lg border border-slate-300 px-3 py-2 font-normal"><option v-for="(label, index) in importanceLabels" :key="label" :value="index + 1">{{ label }}</option></select></label>
      </div>
      <label class="grid gap-2 text-sm font-bold">请在下方描述一下您对本项技能的掌握程度，方便AI助手了解您的现状<textarea v-model="description" maxlength="5000" rows="4" class="rounded-lg border border-slate-300 px-3 py-2 font-normal" placeholder="写明已经掌握的内容和仍需提高的部分"></textarea></label>
      <div class="flex justify-end gap-3">
        <button type="button" class="rounded-lg px-4 py-2 text-sm font-bold text-slate-600" :disabled="busy" @click="resetDraft">取消</button>
        <button type="submit" class="rounded-lg bg-emerald-700 px-5 py-2 text-sm font-bold text-white disabled:opacity-60" :disabled="busy">{{ busy ? '保存中…' : '保存技能' }}</button>
      </div>
    </form>

    <section class="rounded-2xl border border-slate-200 bg-white p-5 sm:p-7">
      <h2 class="mb-4 font-bold">我的技能（{{ skills.length }}）</h2>
      <p v-if="loading" class="text-sm text-slate-500">正在读取技能…</p>
      <p v-else-if="skills.length === 0" class="py-8 text-center text-sm text-slate-500">还没有技能，先添加一项。</p>
      <ul v-else class="divide-y divide-slate-100">
        <li v-for="skill in skills" :key="skill.id" class="py-3">
          <details class="group">
            <summary class="flex cursor-pointer list-none items-center justify-between gap-3 [&::-webkit-details-marker]:hidden"><span><strong>{{ skill.name }}</strong><span class="ml-3 text-xs text-emerald-700">{{ proficiencyLabels[skill.proficiency] }} · 重要性：{{ importanceLabels[skill.importance - 1] }}</span></span><span class="text-sm text-emerald-700 group-open:hidden">展开</span><span class="hidden text-sm text-emerald-700 group-open:inline">收起</span></summary>
            <div class="mt-3 border-t border-slate-100 pt-3"><p class="whitespace-pre-wrap text-sm leading-6 text-slate-600">{{ skill.description || '暂无说明' }}</p><div class="mt-3 flex gap-3"><button type="button" class="text-sm font-bold text-emerald-700 disabled:opacity-60" :disabled="busy" @click="edit(skill)">编辑</button><button type="button" class="text-sm font-bold text-red-700 disabled:opacity-60" :disabled="busy" @click="askDelete(skill)">删除</button></div></div>
          </details>
        </li>
      </ul>
    </section>
    <dialog ref="deleteDialog" aria-labelledby="skill-delete-title" class="m-auto w-[min(92vw,420px)] rounded-2xl border border-slate-200 p-0 shadow-2xl backdrop:bg-slate-900/40" @close="pendingDelete = null">
      <div class="p-6">
        <h2 id="skill-delete-title" class="text-lg font-bold text-slate-900">删除技能</h2>
        <p class="mt-3 text-sm leading-6 text-slate-600">确定删除“{{ pendingDelete?.name }}”吗？这项技能及其说明会被移除。</p>
        <div class="mt-6 flex justify-end gap-3"><button type="button" :disabled="busy" class="rounded-lg border border-slate-300 px-4 py-2 text-sm font-bold text-slate-700" @click="deleteDialog?.close()">取消</button><button type="button" :disabled="busy" class="rounded-lg bg-red-700 px-4 py-2 text-sm font-bold text-white disabled:opacity-60" @click="remove">{{ busy ? '删除中…' : '确认删除' }}</button></div>
      </div>
    </dialog>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ApiError } from '../auth'
import { createSkill, deleteSkill, importanceLabels, listSkills, proficiencyLabels, updateSkill, type Skill, type SkillFields } from '../personal'

const skills = ref<Skill[]>([])
const draft = ref<SkillFields>({ name: '', proficiency: 1, importance: 3, description: null })
const description = ref('')
const editingId = ref<number | null>(null)
const showForm = ref(false)
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const deleteDialog = ref<HTMLDialogElement | null>(null)
const pendingDelete = ref<Skill | null>(null)

function message(cause: unknown): string {
  return cause instanceof ApiError ? cause.message : '操作失败，请稍后重试'
}

async function reload() {
  skills.value = await listSkills()
}

onMounted(async () => {
  try { await reload() } catch (cause) { error.value = message(cause) } finally { loading.value = false }
})

function resetDraft() {
  editingId.value = null
  showForm.value = false
  draft.value = { name: '', proficiency: 1, importance: 3, description: null }
  description.value = ''
}

function startCreate() {
  resetDraft()
  showForm.value = true
}

function edit(skill: Skill) {
  editingId.value = skill.id
  showForm.value = true
  draft.value = { name: skill.name, proficiency: skill.proficiency,
    importance: skill.importance, description: skill.description }
  description.value = skill.description ?? ''
  notice.value = ''
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function save() {
  if (busy.value) return
  if (!draft.value.name.trim()) { error.value = '请填写技能名称'; return }
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const fields = { ...draft.value, name: draft.value.name.trim(), description: description.value.trim() || null }
    if (editingId.value === null) await createSkill(fields)
    else await updateSkill(editingId.value, fields)
    await reload()
    resetDraft()
    notice.value = '技能已保存'
  } catch (cause) { error.value = message(cause) } finally { busy.value = false }
}

function askDelete(skill: Skill) {
  pendingDelete.value = skill
  deleteDialog.value?.showModal()
}

async function remove() {
  const skill = pendingDelete.value
  if (!skill || busy.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await deleteSkill(skill.id)
    deleteDialog.value?.close()
    if (editingId.value === skill.id) resetDraft()
    await reload()
    notice.value = '技能已删除'
  } catch (cause) { error.value = message(cause) } finally { busy.value = false }
}
</script>

<template>
  <main class="mx-auto max-w-[1050px] px-4 py-6 sm:px-8 sm:py-8">
    <p class="text-xs font-extrabold tracking-widest text-emerald-700">个人资料</p>
    <h1 class="mt-1 text-3xl font-bold">基本信息</h1>
    <p class="mt-2 text-sm text-slate-600">教育经历和项目请分别到左侧对应页面添加。这里保留求职方向及其他真实经历说明。</p>
    <section class="mt-6 rounded-2xl border border-slate-200 bg-white p-5 sm:p-7">
      <p v-if="error" class="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-800" role="alert">{{ error }}</p>
      <p v-if="notice" class="mb-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800" role="status">{{ notice }}</p>
      <p v-if="loading" class="text-sm text-slate-500">正在读取资料…</p>
      <form v-else class="grid gap-5" @submit.prevent="submit">
        <label class="grid gap-2 text-sm font-bold text-slate-700">求职方向<input v-model="targetRoles" maxlength="500" class="rounded-lg border border-slate-300 px-4 py-3 font-normal" placeholder="例如：Python 后端、AI 应用" /></label>
        <label class="grid gap-2 text-sm font-bold text-slate-700">其他经历或补充说明<textarea v-model="experienceText" maxlength="15000" rows="7" class="rounded-lg border border-slate-300 px-4 py-3 font-normal" placeholder="例如真实的实习、研究经历；具体项目请在项目页面单独添加"></textarea></label>
        <p class="text-xs text-slate-500">旧版填写在这里的项目文字会保留。请自行核对并整理到“项目经历”，系统不会自动拆分或补写。</p>
        <div class="flex items-center justify-between gap-3"><span class="text-xs text-slate-400">{{ updatedAt ? `上次保存：${new Date(updatedAt).toLocaleString()}` : '尚未保存' }}</span><button type="submit" class="rounded-lg bg-emerald-700 px-5 py-3 text-sm font-bold text-white disabled:opacity-60" :disabled="busy">{{ busy ? '保存中…' : '保存资料' }}</button></div>
      </form>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ApiError } from '../auth'
import { loadProfile, saveProfile } from '../personal'

const targetRoles = ref('')
const experienceText = ref('')
const updatedAt = ref<string | null>(null)
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const message = (cause: unknown) => cause instanceof ApiError ? cause.message : '操作失败，请稍后重试'

onMounted(async () => {
  try {
    const profile = await loadProfile()
    targetRoles.value = profile.target_roles ?? ''
    experienceText.value = profile.experience_text ?? ''
    updatedAt.value = profile.updated_at
  } catch (cause) { error.value = message(cause) } finally { loading.value = false }
})

async function submit() {
  if (busy.value) return
  busy.value = true; error.value = ''; notice.value = ''
  try {
    // PATCH 只发送当前表单字段；旧教育字段仍在库里，不会被空表单覆盖。
    const saved = await saveProfile({ target_roles: targetRoles.value || null, experience_text: experienceText.value || null })
    updatedAt.value = saved.updated_at
    notice.value = '资料已保存'
  } catch (cause) { error.value = message(cause) } finally { busy.value = false }
}
</script>

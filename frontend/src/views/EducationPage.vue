<template>
  <main class="mx-auto max-w-[1050px] px-4 py-6 sm:px-8 sm:py-8">
    <p class="text-xs font-extrabold tracking-widest text-emerald-700">个人资料</p>
    <h1 class="mt-1 text-3xl font-bold">教育经历</h1>
    <p class="mt-2 text-sm text-slate-600">本科、硕士、博士等分别添加一条。年月以月份为单位；旧资料缺少的月份请自行补充。</p>
    <button v-if="!showForm" type="button" class="mt-5 rounded-lg bg-emerald-700 px-4 py-2 text-sm font-bold text-white" @click="startCreate">添加教育经历</button>
    <p v-if="error" role="alert" class="mt-5 rounded-lg bg-red-50 p-3 text-sm text-red-800">{{ error }}</p>
    <p v-if="notice" role="status" class="mt-5 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">{{ notice }}</p>

    <form v-if="showForm" class="mt-6 grid gap-4 rounded-2xl border border-slate-200 bg-white p-5 sm:p-7" @submit.prevent="save">
      <h2 class="text-lg font-bold">{{ editingId === null ? '添加教育经历' : '编辑教育经历' }}</h2>
      <div class="grid gap-4 sm:grid-cols-2">
        <label class="grid gap-2 text-sm font-bold">学校<input v-model="draft.school" required maxlength="200" class="rounded-lg border border-slate-300 px-3 py-2 font-normal" placeholder="请输入学校名称" /></label>
        <label class="grid gap-2 text-sm font-bold">专业<input v-model="draft.major" maxlength="200" class="rounded-lg border border-slate-300 px-3 py-2 font-normal" placeholder="请输入专业名称" /></label>
        <label class="grid gap-2 text-sm font-bold">学历或学位<input v-model="draft.degree" maxlength="100" class="rounded-lg border border-slate-300 px-3 py-2 font-normal" placeholder="本科／硕士／博士" /></label>
      </div>
      <div class="grid gap-4 sm:grid-cols-2">
        <fieldset class="rounded-lg border border-slate-200 p-3">
          <legend class="px-1 text-sm font-bold">入学年月</legend>
          <div class="grid grid-cols-2 gap-2">
            <label class="grid gap-1 text-sm">年份<input v-model="draft.startYear" type="number" min="1900" max="2100" required class="rounded-lg border border-slate-300 px-3 py-2" placeholder="入学年份" /></label>
            <label class="grid gap-1 text-sm">月份<select v-model="draft.startMonth" required class="rounded-lg border border-slate-300 px-3 py-2"><option value="">选择月份</option><option v-for="month in 12" :key="month" :value="String(month)">{{ month }} 月</option></select></label>
          </div>
        </fieldset>
        <fieldset class="rounded-lg border border-slate-200 p-3">
          <legend class="px-1 text-sm font-bold">毕业年月</legend>
          <div class="grid grid-cols-2 gap-2">
            <label class="grid gap-1 text-sm">年份<input v-model="draft.endYear" type="number" min="1900" max="2100" required class="rounded-lg border border-slate-300 px-3 py-2" placeholder="毕业年份" /></label>
            <label class="grid gap-1 text-sm">月份<select v-model="draft.endMonth" required class="rounded-lg border border-slate-300 px-3 py-2"><option value="">选择月份</option><option v-for="month in 12" :key="month" :value="String(month)">{{ month }} 月</option></select></label>
          </div>
        </fieldset>
      </div>
      <label class="grid gap-2 text-sm font-bold">补充说明<textarea v-model="draft.description" maxlength="10000" rows="4" class="rounded-lg border border-slate-300 px-3 py-2 font-normal" placeholder="课程、研究方向等真实信息；可留空"></textarea></label>
      <div class="flex justify-end gap-3"><button type="button" :disabled="busy" class="rounded-lg border border-slate-300 px-4 py-2 text-sm" @click="reset">取消</button><button type="submit" :disabled="busy" class="rounded-lg bg-emerald-700 px-5 py-2 text-sm font-bold text-white disabled:opacity-60">{{ busy ? '保存中…' : '保存教育经历' }}</button></div>
    </form>

    <section class="mt-6 rounded-2xl border border-slate-200 bg-white p-5 sm:p-7">
      <h2 class="text-lg font-bold">已记录的教育经历（{{ entries.length }}）</h2>
      <p v-if="loading" class="mt-4 text-sm text-slate-500">正在读取…</p>
      <p v-else-if="!entries.length" class="mt-4 text-sm text-slate-500">尚未添加教育经历。</p>
      <ul v-else class="mt-3 divide-y divide-slate-100">
        <li v-for="entry in entries" :key="entry.id" class="py-3">
          <details class="group">
            <summary class="flex cursor-pointer list-none items-center justify-between gap-3 [&::-webkit-details-marker]:hidden"><span><strong>{{ entry.school }}</strong><span class="ml-2 text-sm text-slate-600">{{ entry.degree || '学历未填' }} · {{ entry.major || '专业未填' }}</span></span><span class="text-sm text-emerald-700 group-open:hidden">展开</span><span class="hidden text-sm text-emerald-700 group-open:inline">收起</span></summary>
            <div class="mt-3 border-t border-slate-100 pt-3"><p class="text-sm text-slate-600">{{ period(entry.start_year, entry.start_month) }} — {{ period(entry.end_year, entry.end_month) }}</p><p v-if="entry.description" class="mt-2 whitespace-pre-wrap text-sm text-slate-600">{{ entry.description }}</p><div class="mt-3 flex gap-3 text-sm font-bold"><button class="text-emerald-700" @click="edit(entry)">编辑</button><button class="text-red-700" @click="remove(entry)">删除</button></div></div>
          </details>
        </li>
      </ul>
      <details v-if="legacyOnly" class="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-900"><summary class="cursor-pointer font-bold">查看旧版教育补充文字</summary><p class="mt-2 whitespace-pre-wrap">{{ legacyOnly }}。请核对后手动添加，不会自动生成学校或日期。</p></details>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ApiError } from '../auth'
import { createEducation, deleteEducation, listEducations, updateEducation, type Education, type EducationFields } from '../history'
import { loadProfile } from '../personal'

type Draft = { school: string; major: string; degree: string; startYear: string; startMonth: string; endYear: string; endMonth: string; description: string }
const blank = (): Draft => ({ school: '', major: '', degree: '', startYear: '', startMonth: '', endYear: '', endMonth: '', description: '' })
const draft = ref<Draft>(blank())
const entries = ref<Education[]>([])
const legacyOnly = ref('')
const editingId = ref<number | null>(null)
const showForm = ref(false)
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const message = (cause: unknown) => cause instanceof ApiError ? cause.message : '操作失败，请稍后重试'

function period(year: number | null, month: number | null): string {
  return year === null ? '年月待补充' : month === null ? `${year} 年（月待补充）` : `${year} 年 ${month} 月`
}

function reset() { draft.value = blank(); editingId.value = null; showForm.value = false }
function startCreate() { draft.value = blank(); editingId.value = null; showForm.value = true }
function edit(entry: Education) {
  editingId.value = entry.id
  showForm.value = true
  draft.value = { school: entry.school, major: entry.major ?? '', degree: entry.degree ?? '',
    startYear: entry.start_year?.toString() ?? '', startMonth: entry.start_month?.toString() ?? '',
    endYear: entry.end_year?.toString() ?? '', endMonth: entry.end_month?.toString() ?? '',
    description: entry.description ?? '' }
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
async function reload() { entries.value = await listEducations() }
onMounted(async () => {
  try {
    const [saved, profile] = await Promise.all([listEducations(), loadProfile()])
    entries.value = saved
    // 旧版教育文字没有学校时不能安全地转换成一段教育，仍展示给用户手动整理。
    legacyOnly.value = !profile.school
      ? [profile.major, profile.degree, profile.graduation_year ? `毕业年份 ${profile.graduation_year}` : null,
        profile.education_text].filter(Boolean).join('；') : ''
  } catch (cause) { error.value = message(cause) } finally { loading.value = false }
})
async function save() {
  if (busy.value) return
  const d = draft.value
  const fields: EducationFields = { school: d.school.trim(), major: d.major.trim() || null,
    degree: d.degree.trim() || null, start_year: Number(d.startYear), start_month: Number(d.startMonth),
    end_year: Number(d.endYear), end_month: Number(d.endMonth), description: d.description.trim() || null }
  if (!d.startYear || !d.startMonth || !d.endYear || !d.endMonth) { error.value = '请补齐入学和毕业年月'; return }
  if (fields.end_year! * 12 + fields.end_month! < fields.start_year! * 12 + fields.start_month!) { error.value = '毕业年月不能早于入学年月'; return }
  busy.value = true; error.value = ''; notice.value = ''
  try {
    if (editingId.value === null) await createEducation(fields)
    else await updateEducation(editingId.value, fields)
    await reload(); reset(); notice.value = '教育经历已保存'
  } catch (cause) { error.value = message(cause) } finally { busy.value = false }
}
async function remove(entry: Education) {
  if (!window.confirm(`确定删除“${entry.school}”这条教育经历吗？`)) return
  busy.value = true; error.value = ''; notice.value = ''
  try { await deleteEducation(entry.id); if (editingId.value === entry.id) reset(); await reload(); notice.value = '教育经历已删除' }
  catch (cause) { error.value = message(cause) } finally { busy.value = false }
}
</script>

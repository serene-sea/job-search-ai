<template>
  <main class="grid min-h-[650px] gap-4 p-4 md:h-[calc(100vh-149px)] md:grid-cols-[250px_minmax(0,1fr)] lg:p-6">
    <aside class="rounded-2xl border border-slate-200 bg-white p-4" aria-label="历史会话">
      <div class="flex items-center justify-between gap-2">
        <h2 class="font-bold">历史会话</h2>
        <button class="rounded-lg bg-emerald-700 px-3 py-2 text-sm font-bold text-white" :disabled="busy" @click="newSession">＋ 新建</button>
      </div>
      <p class="mt-3 text-xs leading-5 text-slate-500">岗位报告和后续追问保存在同一会话；每次提问可选择是否使用个人记录。</p>
      <div class="mt-4 max-h-64 space-y-2 overflow-y-auto md:max-h-[70vh]">
        <article v-for="item in sessions" :key="item.id" class="rounded-lg border p-2"
          :class="current?.id === item.id ? 'border-emerald-500 bg-emerald-50' : 'border-slate-200'">
          <button class="block w-full text-left text-sm font-bold" @click="openSession(item.id)">{{ item.title }}</button>
          <p class="mt-1 text-xs text-slate-500">{{ item.job_id ? '关联岗位' : '聊天会话' }}</p>
          <div class="mt-2 flex gap-3 text-xs">
            <button class="text-emerald-800 underline" @click="renameId = item.id; renameText = item.title">重命名</button>
            <button class="text-red-700 underline" @click="deleteId = item.id">删除</button>
          </div>
          <div v-if="renameId === item.id" class="mt-2 flex gap-1">
            <input v-model="renameText" maxlength="120" class="min-w-0 flex-1 rounded border p-1 text-sm" aria-label="会话新名称" />
            <button class="text-xs text-emerald-800" @click="saveRename">保存</button>
            <button class="text-xs text-slate-600" @click="renameId = null">取消</button>
          </div>
          <div v-if="deleteId === item.id" class="mt-2 rounded-lg bg-red-50 p-2 text-xs text-red-800">
            <p>删除该会话及全部消息？</p>
            <div class="mt-2 flex gap-3"><button class="font-bold" @click="confirmDelete">确认删除</button><button @click="deleteId = null">取消</button></div>
          </div>
        </article>
      </div>
    </aside>

    <section class="flex min-h-[650px] min-w-0 flex-col rounded-2xl border border-slate-200 bg-white" aria-label="AI 助手">
      <header class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
        <div>
          <p class="text-xs font-extrabold tracking-widest text-emerald-700">AI 助手</p>
          <h1 class="text-xl font-bold">{{ current?.title || '求职建议' }}</h1>
          <p class="mt-1 text-xs text-slate-500">{{ current?.job_id ? '关联岗位，可在此继续提问' : '聊天会话' }}</p>
        </div>
      </header>
      <div v-if="error && !showReview" class="mx-5 mt-4 flex flex-wrap items-center justify-between gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-700" role="alert">
        <span>{{ error }}</span>
        <button v-if="!current && !loading" class="font-bold underline" @click="loadChat">重试</button>
      </div>
      <div class="min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-5" aria-live="polite">
        <p v-if="loading" class="py-16 text-center text-sm text-slate-500">正在打开聊天…</p>
        <p v-else-if="!current && !error" class="py-16 text-center text-sm text-slate-500">新建普通会话，或从岗位页点击“分析并提问”。</p>
        <p v-else-if="current && !messages.length" class="py-16 text-center text-sm text-slate-500">可以直接提问；关联岗位的会话也可以生成岗位报告。</p>

        <article v-for="message in messages" :key="message.id" class="max-w-3xl rounded-xl border p-4 text-sm leading-6"
          :class="message.role === 'user' ? 'ml-auto border-emerald-100 bg-emerald-50' : 'border-slate-200 bg-white'">
          <p v-if="message.kind === 'text'" class="whitespace-pre-wrap">{{ message.content || (message.status === 'running' ? '正在生成…' : '没有生成内容') }}</p>
          <div v-else-if="message.report_json" class="space-y-3">
            <h2 class="text-lg font-bold">{{ message.report_json.company_name }} · {{ message.report_json.title }}：岗位求职报告</h2>
            <p v-if="message.content.startsWith('报告关注点：')" class="text-slate-600">{{ message.content }}</p>
            <p class="text-xs text-slate-500">基于你填写的招聘要求与个人记录；没有查询外部招聘信息。模型判断和改写草稿需由你核对，“材料未见”不等于不会。</p>
            <p class="text-xs text-slate-500">{{ message.report_json.resume_used ? '已参考确认过的简历文字。' : '未使用简历：只有确认过的简历文字才会进入报告。' }}</p>
            <p v-if="message.report_json.context_limited" class="text-amber-800">材料较长，本次仅选取了部分记录，可能遗漏证据。</p>
            <div v-if="message.report_json.guide?.text" class="whitespace-pre-wrap leading-7">
              <p v-if="message.report_json.guide.limited" class="mb-2 rounded-lg bg-amber-50 p-3 text-amber-900">综合报告暂未生成，下面可查看已核对的岗位要求和个人依据。</p>
              {{ message.report_json.guide.text }}
            </div>
            <details class="rounded-lg border border-slate-200 p-3">
              <summary class="cursor-pointer font-semibold">查看岗位要求与核对依据</summary>
              <div v-for="(item, index) in message.report_json.items" :key="index" class="mt-3 rounded border border-slate-100 p-3">
                <p class="font-bold">{{ index + 1 }}. {{ item.quote }} · {{ statusLabel[item.status] }}</p>
                <p class="mt-2">判断：{{ item.reason }}</p>
                <div v-for="source in item.evidence" :key="source.id" class="mt-2 rounded bg-slate-50 p-2">
                  <p class="font-semibold">{{ evidenceLabel[source.kind] }}</p>
                  <p class="whitespace-pre-wrap">{{ source.text }}</p>
                </div>
                <p v-if="!item.evidence.length" class="mt-2 text-slate-500">本次没有可引用的个人材料。</p>
                <p class="mt-2">下一步：{{ item.next_step }}</p>
              </div>
            </details>
          </div>
          <p v-if="message.status === 'interrupted'" class="mt-2 text-xs text-amber-800">已中断，仅保存收到的内容</p>
          <p v-else-if="message.status === 'failed'" class="mt-2 text-xs text-red-700">生成失败</p>
        </article>
        <article v-if="draftAnswer !== null" class="max-w-3xl rounded-xl border border-slate-200 p-4 text-sm leading-6">
          <p class="whitespace-pre-wrap">{{ draftAnswer || '正在生成…' }}</p>
        </article>
      </div>

      <footer v-if="current" class="border-t border-slate-100 px-4 py-3">
        <div class="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
          <label class="flex items-center gap-2 font-bold">提问模式
            <select v-model="mode" class="rounded-lg border border-slate-300 px-2 py-1.5" :disabled="busy">
              <option value="plain">普通聊天</option>
              <option value="personal">结合个人资料</option>
            </select>
          </label>
          <div v-if="mode === 'personal'" class="flex flex-wrap items-center gap-x-3 gap-y-1" role="group" aria-label="本次使用的资料">
            <span class="text-xs text-slate-500">使用</span>
            <label v-for="source in sourceOptions" :key="source.key" class="flex items-center gap-1 whitespace-nowrap">
              <input v-model="selectedSources[source.key]" type="checkbox" :disabled="busy" />{{ source.label }}
            </label>
            <span v-if="current.job_id" class="text-xs text-slate-500">＋当前岗位</span>
          </div>
        </div>
        <details class="mt-1 text-xs text-slate-500">
          <summary class="cursor-pointer">资料与回答说明</summary>
          <p class="mt-1">普通聊天不读取个人记录；结合个人资料时只发送勾选类别的本人记录和当前岗位。简历须先确认，旧报告会按勾选范围过滤。回答不查询网页，具体薪资和招聘流程请以官方渠道为准。</p>
        </details>
        <textarea v-model="question" class="mt-2 w-full resize-y rounded-lg border border-slate-300 p-3" rows="2" maxlength="2000"
          placeholder="例如：这条岗位要求对应的工作通常做什么？我的证据还缺什么？" :disabled="busy"></textarea>
        <p v-if="current.job_id" class="mt-1 text-xs text-slate-500">生成报告后，输入框中的问题会按当前勾选的资料范围自动提问；报告本身不受问题影响。</p>
        <div class="mt-2 flex items-center justify-between gap-3">
          <p v-if="mode === 'personal' && !selectedSourceNames.length && !current.job_id" class="text-xs text-red-700">请至少选择一类资料</p>
          <div class="ml-auto flex gap-2">
            <button v-if="current.job_id" class="rounded-lg border border-emerald-300 px-4 py-2 text-sm font-bold text-emerald-800 disabled:opacity-50"
              :disabled="busy || !job?.requirements_text" @click="openReview">{{ report ? '重新生成报告' : '生成岗位报告' }}</button>
            <button class="rounded-lg border border-amber-300 px-4 py-2 text-sm font-bold text-amber-800 disabled:opacity-50"
              :disabled="runId === null" @click="stopAnswer">停止生成</button>
            <button class="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-bold text-white disabled:opacity-50"
              :disabled="busy || !question.trim() || (mode === 'personal' && !selectedSourceNames.length && !current.job_id)" @click="send">发送</button>
          </div>
        </div>
      </footer>
      <div v-if="showReview && current?.job_id && job" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" @click.self="closeReview">
        <section class="max-h-[85vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white p-5 shadow-xl" role="dialog" aria-modal="true" aria-label="核对岗位要求">
          <div class="flex items-center justify-between gap-3">
            <h2 class="text-lg font-bold">核对岗位要求</h2>
            <button class="text-sm text-slate-600 underline disabled:opacity-50" :disabled="busy" @click="closeReview">关闭</button>
          </div>
          <p class="mt-2 text-xs text-slate-600">先用岗位原文提取要求；生成报告时使用当前本人记录和已确认简历，不读取此前对话。</p>
          <p v-if="reportQuestion" class="mt-2 rounded-lg bg-emerald-50 p-3 text-sm">报告生成后提问：{{ reportQuestion }}</p>
          <details class="mt-3 rounded-lg bg-slate-50 p-3 text-sm">
            <summary class="cursor-pointer font-semibold">查看招聘原文</summary>
            <p class="mt-2 whitespace-pre-wrap">{{ job.requirements_text }}</p>
          </details>
          <RouterLink to="/app/jobs" class="mt-2 inline-block text-sm text-emerald-800 underline">编辑招聘原文</RouterLink>
          <p v-if="error" class="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700" role="alert">{{ error }}</p>
          <p v-if="busy && !extraction" class="mt-4 text-sm text-slate-600">正在提取岗位要求…</p>
          <button v-if="!busy && (error || extraction)" class="mt-3 text-sm text-emerald-800 underline" @click="extract">重新提取</button>
          <div v-if="extraction" class="mt-4 space-y-3 text-sm">
            <p class="font-bold">逐条对照原文；删除误提项或调整优先级</p>
            <div v-for="(item, index) in extraction.items" :key="`${index}-${item.quote}`" class="rounded-lg border border-slate-200 p-3">
              <p class="whitespace-pre-wrap font-semibold">{{ index + 1 }}. {{ item.quote }}</p>
              <div class="mt-2 flex flex-wrap items-center gap-2">
                <select v-model="item.priority" class="rounded border p-2" aria-label="要求优先级">
                  <option value="required">必须要求</option><option value="preferred">优先条件</option><option value="unspecified">未标注</option>
                </select>
                <button class="text-red-700 underline" @click="extraction.items.splice(index, 1)">删除误提项</button>
              </div>
            </div>
            <button class="rounded-lg bg-emerald-700 px-4 py-2 font-bold text-white disabled:opacity-50"
              :disabled="busy || !extraction.items.length" @click="generateReport">{{ busy ? '正在生成报告…' : '按核对结果生成报告' }}</button>
          </div>
        </section>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError } from '../auth'
import { extractRequirements, type RequirementExtractionResult } from '../analysis'
import { createSession, deleteSession, listMessages, listSessions, renameSession, saveReport, stopRun, streamAnswer,
  type ChatMessage, type ChatSession, type ChatSource } from '../chat'
import { getJob, type Job } from '../jobs'

const route = useRoute()
const router = useRouter()
const sessions = ref<ChatSession[]>([])
const current = ref<ChatSession | null>(null)
const messages = ref<ChatMessage[]>([])
const job = ref<Job | null>(null)
const extraction = ref<RequirementExtractionResult | null>(null)
const question = ref('')
const mode = ref<'plain' | 'personal'>('plain')
const selectedSources = ref<Record<ChatSource, boolean>>({
  profile: true, education: true, projects: true, skills: true, resume: true,
})
const error = ref('')
const busy = ref(false)
const loading = ref(false)
const runId = ref<number | null>(null)
const draftAnswer = ref<string | null>(null)
const renameId = ref<number | null>(null)
const renameText = ref('')
const deleteId = ref<number | null>(null)
const showReview = ref(false)
const reportQuestion = ref('')
let controller: AbortController | null = null
let loadVersion = 0

const report = computed(() => [...messages.value].reverse().find(item => item.kind === 'report') ?? null)
const sourceOptions = computed<{ key: ChatSource; label: string }[]>(() => [
  { key: 'profile', label: '基本信息' }, { key: 'education', label: '教育经历' },
  { key: 'projects', label: '项目经历' }, { key: 'skills', label: '技能' },
  { key: 'resume', label: '已确认简历' },
])
const selectedSourceNames = computed(() => sourceOptions.value.filter(item => selectedSources.value[item.key]).map(item => item.key))
const statusLabel = { supported: '有明确证据', partial: '部分匹配', no_evidence: '未见足够证据' }
const evidenceLabel = { skill: '技能自评', profile: '个人资料', education: '教育经历', project: '项目经历', resume: '已确认简历' }
function showError(cause: unknown) { error.value = cause instanceof ApiError ? cause.message : '操作失败，请稍后重试' }
async function refreshSessions() { sessions.value = await listSessions() }

async function loadChat() {
  const version = ++loadVersion
  loading.value = true
  controller?.abort()
  current.value = null; messages.value = []; job.value = null; extraction.value = null; showReview.value = false; reportQuestion.value = ''; error.value = ''
  question.value = ''
  for (const key of Object.keys(selectedSources.value) as ChatSource[]) selectedSources.value[key] = true
  try {
    await refreshSessions()
    const id = Number(route.query.session_id)
    let selected = Number.isSafeInteger(id) && id > 0 ? sessions.value.find(item => item.id === id) : undefined
    if (!selected && route.query.job_id) {
      const jobId = Number(route.query.job_id)
      if (!Number.isSafeInteger(jobId) || jobId <= 0) throw new Error('岗位编号无效')
      selected = sessions.value.find(item => item.job_id === jobId) ?? await createSession(jobId)
      await router.replace({ path: '/app/chat', query: { session_id: selected.id } })
      return
    }
    if (!selected) return
    current.value = selected
    messages.value = await listMessages(selected.id)
    mode.value = selected.job_id && report.value ? 'personal' : 'plain'
    if (selected.job_id) job.value = await getJob(selected.job_id).catch(() => null)
  } catch (cause) { if (version === loadVersion) showError(cause) }
  finally { if (version === loadVersion) loading.value = false }
}
watch(() => [route.query.session_id, route.query.job_id], () => { void loadChat() }, { immediate: true })

async function newSession() {
  try { const item = await createSession(); await router.push({ path: '/app/chat', query: { session_id: item.id } }) }
  catch (cause) { showError(cause) }
}
function openSession(id: number) { void router.push({ path: '/app/chat', query: { session_id: id } }) }
async function saveRename() {
  if (renameId.value === null || !renameText.value.trim()) return
  try {
    const updated = await renameSession(renameId.value, renameText.value.trim())
    if (current.value?.id === updated.id) current.value = updated
    renameId.value = null; await refreshSessions()
  } catch (cause) { showError(cause) }
}
async function confirmDelete() {
  if (deleteId.value === null) return
  try {
    const id = deleteId.value; await deleteSession(id); deleteId.value = null
    if (current.value?.id === id) await router.push('/app/chat')
    else await refreshSessions()
  } catch (cause) { showError(cause) }
}
function openReview() {
  if (!job.value?.requirements_text || busy.value) return
  reportQuestion.value = question.value.trim()
  // 报告后的自动提问需要当前岗位与所选本人资料，所以使用现有个人模式。
  mode.value = 'personal'
  showReview.value = true
  extraction.value = null
  error.value = ''
  // “生成岗位报告”是显式操作；打开核对窗口后自动开始第一步提取。
  void extract()
}
function closeReview() {
  if (busy.value) return
  showReview.value = false
  extraction.value = null
  reportQuestion.value = ''
  error.value = ''
}
async function extract() {
  if (!job.value || busy.value) return
  busy.value = true; error.value = ''; extraction.value = null
  try {
    const jobId = job.value.id
    job.value = await getJob(jobId)
    if (!job.value.requirements_text) { error.value = '请先在岗位页填写招聘要求'; return }
    const result = await extractRequirements(jobId)
    if (showReview.value && current.value?.job_id === jobId) extraction.value = result
  }
  catch (cause) { showError(cause) }
  finally { busy.value = false }
}
async function generateReport() {
  if (!current.value || !extraction.value?.items.length || busy.value) return
  const sessionId = current.value.id
  const pendingQuestion = reportQuestion.value
  let askAfterReport = false
  busy.value = true; error.value = ''
  try {
    await saveReport(sessionId, extraction.value.snapshot_version, extraction.value.items)
    messages.value = await listMessages(sessionId)
    extraction.value = null; showReview.value = false; reportQuestion.value = ''; await refreshSessions()
    // 报告保存完成后才发送问题；走原有聊天流，问题和回答各自成为一条消息。
    askAfterReport = Boolean(pendingQuestion && current.value?.id === sessionId && question.value.trim() === pendingQuestion)
  } catch (cause) {
    if (cause instanceof ApiError && cause.status === 409) extraction.value = null
    showError(cause)
  } finally { busy.value = false }
  if (askAfterReport) await send()
}
async function send() {
  if (!current.value || !question.value.trim() || busy.value ||
      (mode.value === 'personal' && !selectedSourceNames.value.length && !current.value.job_id)) return
  const sessionId = current.value.id; const asked = question.value.trim()
  const sources = mode.value === 'personal' ? [...selectedSourceNames.value] : []
  busy.value = true; error.value = ''; draftAnswer.value = ''; runId.value = null
  controller = new AbortController()
  try {
    await streamAnswer(sessionId, asked, mode.value, sources, controller.signal, (event, data) => {
      if (event === 'start' && typeof data.run_id === 'number') runId.value = data.run_id
      if (event === 'delta' && typeof data.text === 'string') draftAnswer.value = (draftAnswer.value ?? '') + data.text
      if (event === 'error' && typeof data.detail === 'string') error.value = data.detail
    })
    question.value = ''
  } catch (cause) { if (!controller.signal.aborted) showError(cause) }
  finally {
    // 服务端保存中断状态与浏览器刷新可能有短暂竞态，以数据库结果为准。
    await new Promise(resolve => window.setTimeout(resolve, 150))
    try { messages.value = await listMessages(sessionId); await refreshSessions() } catch (cause) { showError(cause) }
    draftAnswer.value = null; runId.value = null; busy.value = false; controller = null
  }
}
async function stopAnswer() {
  if (runId.value === null) return
  try { await stopRun(runId.value); controller?.abort() }
  catch (cause) { showError(cause) }
}
onBeforeUnmount(() => controller?.abort())
</script>

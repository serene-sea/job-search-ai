<template>
  <main class="mx-auto max-w-[1300px] px-4 py-6 sm:px-8 sm:py-8">
    <div class="mb-6 flex flex-wrap items-center justify-between gap-3">
      <div>
        <p class="text-xs font-extrabold tracking-widest text-emerald-700">个人资料 / 岗位</p>
        <h1 class="mb-2 text-3xl font-bold">岗位记录</h1>
        <p class="text-slate-500">按公司整理岗位，用一个当前状态记录求职进度。</p>
      </div>
      <button class="rounded-lg bg-emerald-700 px-4 py-3 font-bold text-white disabled:opacity-60"
        :disabled="statuses.length === 0 || busy" @click="startCreate">新建岗位</button>
    </div>

    <p v-if="error" role="alert" class="mb-4 rounded-lg bg-red-50 p-3 text-red-700">{{ error }}</p>
    <p v-if="notice" role="status" class="mb-4 rounded-lg bg-emerald-50 p-3 text-emerald-800">{{ notice }}</p>

    <div class="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
      <section class="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
        <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 class="font-bold">公司与岗位 <span class="text-sm font-normal text-slate-500">{{ list.total }} 条</span></h2>
          <button class="text-sm text-emerald-700 underline disabled:opacity-50" :disabled="loading" @click="loadAll">刷新</button>
        </div>
        <div class="mb-5 flex flex-wrap gap-3">
          <label class="grid gap-1 text-sm text-slate-600">公司
            <select v-model="companyFilter" class="rounded-lg border border-slate-200 bg-white p-2" @change="applyFilters">
              <option value="">全部公司</option>
              <option v-for="group in companies" :key="group.company_name" :value="group.company_name">
                {{ group.company_name }}（{{ group.total }}）
              </option>
            </select>
          </label>
          <label class="grid gap-1 text-sm text-slate-600">当前状态
            <select v-model.number="statusFilter" class="rounded-lg border border-slate-200 bg-white p-2" @change="applyFilters">
              <option :value="0">全部状态</option>
              <option v-for="status in statuses" :key="status.id" :value="status.id">{{ status.name }}</option>
            </select>
          </label>
        </div>
        <p v-if="loading" class="py-10 text-center text-slate-500">正在读取岗位…</p>
        <p v-else-if="list.items.length === 0" class="py-10 text-center text-slate-500">当前筛选下暂无岗位。</p>
        <div v-else class="space-y-3">
          <!-- details 默认收起；summary 只放总览信息，点开后才显示长篇招聘原文和操作。 -->
          <details v-for="job in list.items" :key="job.id" class="group rounded-xl border border-slate-200 p-4">
            <summary class="flex cursor-pointer list-none flex-wrap items-start justify-between gap-3 [&::-webkit-details-marker]:hidden">
              <div>
                <h3 class="font-bold">{{ job.company_name }} · {{ job.title }}</h3>
                <p class="mt-1 text-sm text-slate-500">{{ job.location || '地点未填' }}</p>
              </div>
              <span class="flex items-center gap-3"><span class="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-800">{{ job.status_name }}</span><span class="text-sm text-emerald-700 group-open:hidden">展开</span><span class="hidden text-sm text-emerald-700 group-open:inline">收起</span></span>
            </summary>
            <div class="mt-4 border-t border-slate-100 pt-1">
            <p v-if="job.requirements_text" class="mt-3 whitespace-pre-wrap text-sm text-slate-600">{{ job.requirements_text }}</p>
            <p v-if="job.notes" class="mt-2 whitespace-pre-wrap text-sm text-slate-500">备注：{{ job.notes }}</p>
            <a v-if="job.source_url" :href="job.source_url" target="_blank" rel="noopener noreferrer"
              class="mt-2 inline-block text-sm text-emerald-700 underline">招聘链接</a>
            <div class="mt-4 flex gap-4 text-sm">
              <RouterLink :to="{ path: '/app/chat', query: { job_id: job.id } }" class="text-emerald-700 underline">分析并提问</RouterLink>
              <button class="text-emerald-700 underline" @click="startEdit(job)">编辑</button>
              <button class="text-red-700 underline" @click="removeJob(job)">删除</button>
            </div>
            </div>
          </details>
        </div>
        <div v-if="list.total > list.limit" class="mt-5 flex items-center justify-between text-sm">
          <button class="text-emerald-700 disabled:opacity-40" :disabled="offset === 0 || loading" @click="changePage(-1)">上一页</button>
          <span>{{ offset + 1 }}–{{ Math.min(offset + list.limit, list.total) }} / {{ list.total }}</span>
          <button class="text-emerald-700 disabled:opacity-40"
            :disabled="offset + list.limit >= list.total || loading" @click="changePage(1)">下一页</button>
        </div>
      </section>

      <aside class="self-start rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
        <h2 class="font-bold">公司概览</h2>
        <p class="my-3 text-xs leading-5 text-slate-500">公司名来自你填写的岗位；不会核验招聘链接，也不会自动合并同名岗位。</p>
        <div v-if="companies.length" class="space-y-2">
          <button v-for="group in companies" :key="group.company_name"
            class="block w-full rounded-lg border border-slate-200 p-3 text-left text-sm hover:bg-slate-50"
            @click="selectCompany(group.company_name)">
            <span class="font-bold">{{ group.company_name }}</span>
            <span class="mt-1 block text-slate-500">{{ group.total }} 个岗位</span>
          </button>
        </div>
        <p v-else class="text-sm text-slate-500">暂无公司</p>
        <button class="mt-6 text-sm font-bold text-emerald-700 underline" @click="showStatuses = !showStatuses">
          {{ showStatuses ? '收起状态设置' : '管理状态' }}
        </button>
        <div v-if="showStatuses" class="mt-4 border-t border-slate-200 pt-4">
          <p class="mb-3 text-xs text-slate-500">排序数字越小越靠前；使用中的状态须先修改岗位才能删除。</p>
          <div class="max-h-80 space-y-3 overflow-y-auto">
            <div v-for="status in statuses" :key="status.id" class="rounded-lg border border-slate-200 p-2">
              <div v-if="statusDrafts[status.id]" class="grid grid-cols-[1fr_65px] gap-2">
                <input v-model="statusDrafts[status.id]!.name" aria-label="状态名称" class="min-w-0 rounded border border-slate-200 p-2 text-sm" />
                <input v-model.number="statusDrafts[status.id]!.sort_order" aria-label="排序" type="number" min="1" max="10000"
                  class="min-w-0 rounded border border-slate-200 p-2 text-sm" />
              </div>
              <div class="mt-2 flex gap-3 text-xs">
                <button class="text-emerald-700 underline" :disabled="busy" @click="saveStatus(status.id)">保存</button>
                <button class="text-red-700 underline" :disabled="busy" @click="removeStatus(status)">删除</button>
              </div>
            </div>
          </div>
          <form class="mt-4 space-y-2" @submit.prevent="addStatus">
            <input v-model="newStatusName" required maxlength="100" placeholder="新状态名称"
              class="w-full rounded border border-slate-200 p-2 text-sm" />
            <label class="flex items-center gap-2 text-xs">排序
              <input v-model.number="newStatusOrder" required type="number" min="1" max="10000"
                class="w-20 rounded border border-slate-200 p-2" />
            </label>
            <button class="rounded-lg bg-emerald-50 px-3 py-2 text-sm font-bold text-emerald-800 disabled:opacity-50"
              :disabled="busy">添加状态</button>
          </form>
        </div>
      </aside>
    </div>

    <!-- 本窗口改动：表单从列表下方移入原生 dialog。showModal() 打开后，列表留在原位，长表单在弹窗内滚动。 -->
    <dialog v-if="showForm" ref="jobDialog" aria-labelledby="job-dialog-title" @cancel.prevent="closeForm()"
      class="m-auto max-h-[90vh] w-[calc(100%-2rem)] max-w-3xl overflow-y-auto rounded-2xl border border-emerald-200 bg-white p-5 shadow-2xl backdrop:bg-slate-900/60 sm:p-6">
      <div class="mb-4 flex items-center justify-between">
        <h2 id="job-dialog-title" class="text-lg font-bold">{{ editingId === null ? '新建岗位' : '编辑岗位' }}</h2>
        <button type="button" class="text-sm text-slate-500 underline disabled:opacity-50" :disabled="busy" @click="closeForm()">关闭</button>
      </div>
      <!-- 背后的页面被模态层盖住；请求失败时要在弹窗内再显示一次错误，用户才能看见。 -->
      <p v-if="error" role="alert" class="mb-4 rounded-lg bg-red-50 p-3 text-red-700">{{ error }}</p>
      <p v-if="notice" role="status" class="mb-4 rounded-lg bg-emerald-50 p-3 text-emerald-800">{{ notice }}</p>
      <form class="space-y-4" @submit.prevent="saveJob">
        <div class="grid gap-4 sm:grid-cols-2">
          <label class="grid gap-1 text-sm font-bold">公司名 *
            <!-- 打开弹窗后直接定位到第一个必填项，省去一次点击。 -->
            <input v-model="form.company_name" autofocus required maxlength="200" class="rounded-lg border border-slate-200 p-3" />
          </label>
          <label class="grid gap-1 text-sm font-bold">岗位名 *
            <input v-model="form.title" required maxlength="200" class="rounded-lg border border-slate-200 p-3" />
          </label>
          <label class="grid gap-1 text-sm font-bold">地点
            <input v-model="form.location" maxlength="200" class="rounded-lg border border-slate-200 p-3" />
          </label>
          <label class="grid gap-1 text-sm font-bold">当前状态 *
            <select v-model.number="form.status_id" required class="rounded-lg border border-slate-200 bg-white p-3" @change="onStatusSelection">
              <option v-for="status in statuses" :key="status.id" :value="status.id">{{ status.name }}</option>
              <option :value="0">＋ 新增自定义状态…</option>
            </select>
          </label>
        </div>
        <div v-if="showInlineStatus" class="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
          <label class="grid gap-1 text-sm font-bold" for="inline-status-name">新状态名称
            <input id="inline-status-name" v-model="inlineStatusName" maxlength="100" placeholder="例如：等待内推"
              class="rounded-lg border border-slate-200 bg-white p-3" @keydown.enter.prevent="createInlineStatus" />
          </label>
          <p class="mt-2 text-xs text-slate-600">创建后会自动选中；岗位仍需点击“保存岗位”才会保存。</p>
          <div class="mt-3 flex gap-3 text-sm">
            <button type="button" class="rounded-lg bg-emerald-700 px-3 py-2 font-bold text-white disabled:opacity-50"
              :disabled="busy || !inlineStatusName.trim()" @click="createInlineStatus">{{ busy ? '创建中…' : '创建并选中' }}</button>
            <button type="button" class="text-slate-600 underline" :disabled="busy" @click="showInlineStatus = false">取消</button>
          </div>
        </div>
        <label class="grid gap-1 text-sm font-bold">招聘链接（可选）
          <input v-model="form.source_url" type="url" maxlength="2048" class="rounded-lg border border-slate-200 p-3" />
        </label>
        <label class="grid gap-1 text-sm font-bold">招聘要求（手动粘贴）
          <textarea v-model="form.requirements_text" rows="5" maxlength="30000" class="rounded-lg border border-slate-200 p-3"></textarea>
        </label>
        <label class="grid gap-1 text-sm font-bold">备注
          <textarea v-model="form.notes" rows="3" maxlength="10000" class="rounded-lg border border-slate-200 p-3"></textarea>
        </label>
        <p class="text-xs text-slate-500">岗位进度只由“当前状态”决定；自定义状态会按名称原样显示。</p>
        <div class="flex flex-wrap gap-3">
          <button class="rounded-lg bg-emerald-700 px-5 py-3 font-bold text-white disabled:opacity-50" :disabled="busy || showInlineStatus">
            {{ busy ? '保存中…' : '保存岗位' }}
          </button>
          <button type="button" class="rounded-lg border border-slate-200 px-5 py-3 text-slate-600 disabled:opacity-50"
            :disabled="busy" @click="closeForm()">取消</button>
        </div>
      </form>
    </dialog>
  </main>
</template>













<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { ApiError } from '../auth'
import {
  createJob, createStatus, deleteJob, deleteStatus, listCompanies, listJobs, listStatuses,
  updateJob, updateStatus, type CompanyGroup, type Job, type JobForm, type JobList, type JobStatus,
} from '../jobs'

const statuses = ref<JobStatus[]>([])
const companies = ref<CompanyGroup[]>([])
const list = ref<JobList>({ items: [], total: 0, limit: 20, offset: 0 })
const statusDrafts = ref<Record<number, { name: string; sort_order: number }>>({})
const companyFilter = ref('')
const statusFilter = ref(0)
const offset = ref(0)
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const showForm = ref(false)
// 本窗口改动：showForm 负责创建/移除节点；这个 ref 才能调用原生 dialog 的 showModal()/close()。
const jobDialog = ref<HTMLDialogElement | null>(null)
// 记住打开弹窗前的按钮，关闭后把键盘焦点还给它，方便继续操作列表。
let previousFocus: HTMLElement | null = null
const showStatuses = ref(false)
const showInlineStatus = ref(false)
const editingId = ref<number | null>(null)
const newStatusName = ref('')
const newStatusOrder = ref(16)
const inlineStatusName = ref('')
const statusBeforeCustom = ref(0)

function emptyForm(): JobForm {
  return {
    company_name: '', title: '', location: '', source_url: '', requirements_text: '', notes: '',
    status_id: statuses.value[0]?.id ?? 0,
  }
}
const form = ref<JobForm>(emptyForm())

function showError(cause: unknown) {
  error.value = cause instanceof ApiError ? cause.message : '操作失败，请稍后重试'
  notice.value = ''
}

async function loadJobsOnly() {
  loading.value = true
  error.value = ''
  try {
    list.value = await listJobs(companyFilter.value, statusFilter.value, offset.value)
  } catch (cause) {
    showError(cause)
  } finally {
    loading.value = false
  }
}

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const [nextStatuses, nextCompanies, nextList] = await Promise.all([
      listStatuses(), listCompanies(), listJobs(companyFilter.value, statusFilter.value, offset.value),
    ])
    statuses.value = nextStatuses
    const invalidStatusFilter = statusFilter.value > 0 && !nextStatuses.some(item => item.id === statusFilter.value)
    if (invalidStatusFilter) {
      // 删除了正在筛选的状态后回到“全部”，避免页面一直停在无效筛选。
      statusFilter.value = 0
    }
    companies.value = nextCompanies
    list.value = invalidStatusFilter
      ? await listJobs(companyFilter.value, 0, offset.value) : nextList
    // 草稿只由本次服务端结果生成；状态保存后不会显示已过期的旧名称。
    statusDrafts.value = Object.fromEntries(nextStatuses.map(item => [item.id, {
      name: item.name, sort_order: item.sort_order,
    }]))
    newStatusOrder.value = Math.max(0, ...nextStatuses.map(item => item.sort_order)) + 1
    if (!nextStatuses.some(item => item.id === form.value.status_id)) {
      form.value.status_id = nextStatuses[0]?.id ?? 0
    }
    if (!showInlineStatus.value) statusBeforeCustom.value = form.value.status_id
  } catch (cause) {
    showError(cause)
  } finally {
    loading.value = false
  }
}

async function openForm() {
  // v-if 先把 dialog 加入页面；nextTick 等 Vue 更新 DOM，否则 jobDialog.value 仍是 null。
  previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
  showForm.value = true
  await nextTick()
  // showModal 才是真正打开模态层；只把 showForm 设为 true 不会自动弹出原生 dialog。
  jobDialog.value?.showModal()
}

function closeForm() {
  // “关闭”、"取消" 和 Esc 都走这里；请求中不关闭，避免用户误以为保存已取消。
  if (busy.value) return
  jobDialog.value?.close()
  showForm.value = false
  // 等节点移除后再聚焦原按钮；这一步不会向后端删除或保存岗位。
  void nextTick(() => previousFocus?.focus())
}

function startCreate() {
  // 每次新建都重置旧草稿；编辑则在 startEdit 中用该岗位的数据填充同一弹窗。
  editingId.value = null
  form.value = emptyForm()
  statusBeforeCustom.value = form.value.status_id
  showInlineStatus.value = false
  inlineStatusName.value = ''
  error.value = ''
  notice.value = ''
  void openForm()
}

function startEdit(job: Job) {
  editingId.value = job.id
  form.value = {
    company_name: job.company_name, title: job.title, location: job.location ?? '',
    source_url: job.source_url ?? '', requirements_text: job.requirements_text ?? '',
    notes: job.notes ?? '', status_id: job.status_id,
  }
  statusBeforeCustom.value = form.value.status_id
  showInlineStatus.value = false
  inlineStatusName.value = ''
  error.value = ''
  notice.value = ''
  void openForm()
}

function onStatusSelection() {
  if (form.value.status_id === 0) {
    // 0 只是下拉菜单的“新增”入口，不能作为岗位的 status_id 发给后端。
    form.value.status_id = statusBeforeCustom.value || statuses.value[0]?.id || 0
    showInlineStatus.value = true
    return
  }
  statusBeforeCustom.value = form.value.status_id
  showInlineStatus.value = false
}

async function createInlineStatus() {
  const name = inlineStatusName.value.trim()
  if (!name || busy.value) return
  busy.value = true
  error.value = ''
  try {
    // 先单独保存状态；成功后再放入下拉菜单，避免用户选到只在前端存在的假状态。
    const created = await createStatus(name, Math.max(1, newStatusOrder.value))
    statuses.value = [...statuses.value, created].sort((a, b) => a.sort_order - b.sort_order || a.id - b.id)
    statusDrafts.value[created.id] = { name: created.name, sort_order: created.sort_order }
    newStatusOrder.value = Math.max(newStatusOrder.value, created.sort_order) + 1
    form.value.status_id = created.id
    statusBeforeCustom.value = created.id
    showInlineStatus.value = false
    inlineStatusName.value = ''
    notice.value = '自定义状态已创建，请继续保存岗位'
  } catch (cause) {
    showError(cause)
  } finally {
    busy.value = false
  }
}

async function saveJob() {
  if (showInlineStatus.value || busy.value) return
  busy.value = true
  error.value = ''
  try {
    const data = { ...form.value }
    const targetId = editingId.value
    // null 表示新建；有编号则更新已有岗位。两条路径共用同一份表单数据。
    if (targetId === null) await createJob(data)
    else await updateJob(targetId, data)
    // 只有 API 成功才走到这里；失败会进 catch，弹窗保持打开并显示错误。
    jobDialog.value?.close()
    showForm.value = false
    void nextTick(() => previousFocus?.focus())
    if (targetId === null) {
      // 新岗位可能不符合旧筛选；回到全部岗位第一页。列表按公司排序，岗位很多时新记录仍可能在后续页。
      companyFilter.value = ''
      statusFilter.value = 0
      offset.value = 0
    }
    notice.value = '岗位已保存'
    await loadAll()
  } catch (cause) {
    showError(cause)
  } finally {
    busy.value = false
  }
}

async function removeJob(job: Job) {
  if (!window.confirm(`确定删除“${job.company_name} · ${job.title}”吗？`)) return
  busy.value = true
  try {
    await deleteJob(job.id)
    // 删除本页最后一条后退一页，避免显示一个空页。
    if (list.value.items.length === 1 && offset.value > 0) offset.value -= list.value.limit
    notice.value = '岗位已删除'
    await loadAll()
  } catch (cause) {
    showError(cause)
  } finally {
    busy.value = false
  }
}

function applyFilters() {
  offset.value = 0
  void loadJobsOnly()
}

function selectCompany(name: string) {
  companyFilter.value = name
  applyFilters()
}

function changePage(direction: -1 | 1) {
  offset.value += direction * list.value.limit
  void loadJobsOnly()
}

async function addStatus() {
  busy.value = true
  try {
    await createStatus(newStatusName.value, newStatusOrder.value)
    newStatusName.value = ''
    notice.value = '状态已添加'
    await loadAll()
  } catch (cause) {
    showError(cause)
  } finally {
    busy.value = false
  }
}

async function saveStatus(id: number) {
  const draft = statusDrafts.value[id]
  if (!draft) return
  busy.value = true
  try {
    await updateStatus(id, draft.name, draft.sort_order)
    notice.value = '状态已保存'
    await loadAll()
  } catch (cause) {
    showError(cause)
  } finally {
    busy.value = false
  }
}

async function removeStatus(status: JobStatus) {
  if (!window.confirm(`确定删除状态“${status.name}”吗？`)) return
  busy.value = true
  try {
    await deleteStatus(status.id)
    notice.value = '状态已删除'
    await loadAll()
  } catch (cause) {
    showError(cause)
  } finally {
    busy.value = false
  }
}

onMounted(() => { void loadAll() })  // 页面加载时读取状态、公司和岗位列表
</script>

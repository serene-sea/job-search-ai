<template>
  <main class="mx-auto max-w-[1100px] px-4 py-6 sm:px-8 sm:py-8">
    <p class="text-xs font-extrabold tracking-widest text-emerald-700">个人资料</p>
    <h1 class="mt-1 text-3xl font-bold">当前简历</h1>
    <p class="mt-2 text-sm leading-7 text-slate-600">只保存一份简历文字。PDF、DOCX、TXT 原文件仅用于提取文字，不会长期保存。</p>
    <p v-if="error" class="mt-5 rounded-lg bg-red-50 p-3 text-sm text-red-800" role="alert">{{ error }}</p>
    <p v-if="notice" class="mt-5 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800" role="status">{{ notice }}</p>
    <p v-if="loading" class="mt-6 rounded-2xl bg-white p-6 text-sm text-slate-500">正在读取简历…</p>

    <template v-else>
      <section class="mt-6 rounded-2xl border border-slate-200 bg-white p-5 sm:p-7">
        <h2 class="text-lg font-bold">上传简历</h2>
        <p class="mt-1 text-sm text-slate-500">支持 PDF、DOCX、TXT，最大 10 MB。扫描版 PDF 可能提取不到文字，可在下方手动粘贴。</p>
        <div class="mt-4 rounded-xl border-2 border-dashed p-6 text-center transition-colors"
          :class="dragging ? 'border-emerald-600 bg-emerald-50' : 'border-slate-300 bg-slate-50'"
          @dragenter.prevent="dragging = true" @dragover.prevent="dragging = true" @dragleave.prevent="leaveDropZone" @drop.prevent="dropFile">
          <p class="font-bold text-slate-700">将简历拖到这里</p>
          <p class="my-3 text-sm text-slate-500">或</p>
          <button type="button" :disabled="busy" class="rounded-lg border-2 border-emerald-700 bg-white px-5 py-3 text-sm font-bold text-emerald-800 shadow-sm hover:bg-emerald-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 disabled:opacity-60" @click="fileInput?.click()">选择简历文件</button>
          <input ref="fileInput" type="file" accept=".pdf,.docx,.txt" aria-hidden="true" tabindex="-1" class="sr-only" @change="chooseFile" />
          <p v-if="selectedFile" class="mt-4 text-sm font-bold text-slate-700">已选：{{ selectedFile.name }}</p>
        </div>
        <div class="mt-4 flex flex-wrap items-center justify-between gap-3">
          <span class="text-xs text-slate-500">再次提取会替换当前简历文字，并取消旧确认状态。</span>
          <button type="button" :disabled="busy || !selectedFile" class="rounded-lg bg-emerald-700 px-5 py-3 text-sm font-bold text-white shadow-sm hover:bg-emerald-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 disabled:opacity-50" @click="submitUpload">{{ busy ? '处理中…' : '提取简历信息' }}</button>
        </div>
      </section>

      <section class="mt-6 rounded-2xl border border-slate-200 bg-white p-5 sm:p-7">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div><h2 class="text-lg font-bold">简历文字</h2><p class="mt-1 text-sm text-slate-500">{{ resume?.source_filename ? `来源：${resume.source_filename}` : '尚未上传文件，也可以直接粘贴文字' }}</p></div>
          <span class="rounded-full px-3 py-1 text-xs font-bold" :class="resume?.confirmed_at && !dirty ? 'bg-emerald-50 text-emerald-800' : 'bg-amber-50 text-amber-800'">{{ dirty ? '有未保存修改' : resume?.confirmed_at ? '已确认' : '待核对' }}</span>
        </div>

        <template v-if="editing">
          <p class="mt-4 text-sm text-slate-600">请对照提取原文核对姓名、时间、项目与技术细节；确认前不会把未确认的简历交给岗位分析。</p>
          <div class="mt-4 grid gap-5 lg:grid-cols-2">
            <div v-if="resume?.source_filename" class="min-w-0"><h3 class="text-sm font-bold">文件提取结果（只读）</h3><pre class="mt-2 max-h-[34rem] min-h-72 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm leading-6">{{ resume.raw_extracted_text || '未提取到文字。扫描件请自行核对并粘贴。' }}</pre></div>
            <label class="grid min-w-0 gap-2 text-sm font-bold">人工核对后的文字<textarea v-model="draft" maxlength="200000" rows="18" class="min-h-72 w-full rounded-lg border border-slate-300 p-4 font-normal leading-6" placeholder="在这里修改提取错误，或直接粘贴简历文字"></textarea></label>
          </div>
          <p class="mt-3 text-xs leading-6 text-slate-500">先保存文字，再确认。修改或重新上传后，原确认状态失效。</p>
          <div class="mt-5 flex flex-wrap justify-end gap-3">
            <button v-if="resume?.confirmed_at" type="button" :disabled="busy" class="rounded-lg border border-slate-300 px-4 py-2 text-sm font-bold" @click="cancelEdit">取消编辑</button>
            <button type="button" :disabled="busy || (!dirty && !!resume) || (!resume && !draft.trim())" class="rounded-lg border-2 border-emerald-700 px-4 py-2 text-sm font-bold text-emerald-800 disabled:opacity-50" @click="saveDraft">保存文字</button>
            <button type="button" :disabled="busy || dirty || !resume || !draft.trim() || !!resume.confirmed_at" class="rounded-lg bg-emerald-700 px-5 py-2 text-sm font-bold text-white disabled:opacity-50" @click="confirm">确认已核对</button>
          </div>
        </template>
        <template v-else>
          <p class="mt-4 text-sm text-emerald-800">已核对并锁定编辑；岗位分析可读取这份已确认文字。</p>
          <details class="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4"><summary class="cursor-pointer font-bold text-slate-700">查看已确认的简历文字</summary><pre class="mt-3 max-h-[34rem] overflow-auto whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">{{ resume?.reviewed_text }}</pre></details>
          <button type="button" :disabled="busy" class="mt-4 rounded-lg border-2 border-emerald-700 px-4 py-2 text-sm font-bold text-emerald-800" @click="editing = true">编辑文字</button>
        </template>
        <div v-if="resume" class="mt-6 border-t border-slate-100 pt-4"><button type="button" :disabled="busy" class="text-sm font-bold text-red-700 disabled:opacity-60" @click="remove">删除当前简历文字</button></div>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ApiError } from '../auth'
import { confirmResume, deleteResume, loadResume, saveResumeText, uploadResume, type Resume } from '../resume'

const resume = ref<Resume | null>(null)
const draft = ref('')
const selectedFile = ref<File | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const dragging = ref(false)
const editing = ref(true)
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const dirty = computed(() => draft.value !== (resume.value?.reviewed_text ?? ''))
const message = (cause: unknown) => cause instanceof ApiError ? cause.message : '操作失败，请稍后重试'

function show(saved: Resume | null) {
  resume.value = saved
  draft.value = saved?.reviewed_text ?? ''
  editing.value = !saved?.confirmed_at
}
onMounted(async () => { try { show(await loadResume()) } catch (cause) { error.value = message(cause) } finally { loading.value = false } })

function acceptFile(file: File | null) {
  if (!file) return
  if (!/\.(pdf|docx|txt)$/i.test(file.name)) { selectedFile.value = null; error.value = '仅支持 PDF、DOCX、TXT'; return }
  if (file.size > 10 * 1024 * 1024) { selectedFile.value = null; error.value = '文件不能超过 10 MB'; return }
  selectedFile.value = file
  error.value = ''
}
function chooseFile(event: Event) { acceptFile((event.target as HTMLInputElement).files?.[0] ?? null) }
function leaveDropZone(event: DragEvent) {
  if (!event.currentTarget || !(event.currentTarget as HTMLElement).contains(event.relatedTarget as Node | null)) dragging.value = false
}
function dropFile(event: DragEvent) {
  dragging.value = false
  if (!busy.value) acceptFile(event.dataTransfer?.files?.[0] ?? null)
}
function cancelEdit() { draft.value = resume.value?.reviewed_text ?? ''; editing.value = false }

async function submitUpload() {
  if (!selectedFile.value || busy.value) return
  if ((resume.value || dirty.value) && !window.confirm('提取新文件会替换当前简历文字，确定继续吗？')) return
  busy.value = true; error.value = ''; notice.value = ''
  try {
    const saved = await uploadResume(selectedFile.value)
    show(saved)
    selectedFile.value = null
    if (fileInput.value) fileInput.value.value = ''
    notice.value = saved.raw_extracted_text ? '已提取文字，结果显示在下方，请人工核对' : '未提取到文字；请人工粘贴后核对'
  } catch (cause) { error.value = message(cause) } finally { busy.value = false }
}
async function saveDraft() {
  if (busy.value) return
  busy.value = true; error.value = ''; notice.value = ''
  try { show(await saveResumeText(draft.value)); notice.value = '文字已保存，请核对后点击确认' }
  catch (cause) { error.value = message(cause) } finally { busy.value = false }
}
async function confirm() {
  if (busy.value || dirty.value) return
  busy.value = true; error.value = ''; notice.value = ''
  try { show(await confirmResume()); notice.value = '简历文字已确认；需要修改时点击“编辑文字”' }
  catch (cause) { error.value = message(cause) } finally { busy.value = false }
}
async function remove() {
  if (!window.confirm('确定删除当前简历文字吗？原文件不在应用中保存。')) return
  busy.value = true; error.value = ''; notice.value = ''
  try { await deleteResume(); show(null); notice.value = '简历文字已删除' }
  catch (cause) { error.value = message(cause) } finally { busy.value = false }
}
</script>

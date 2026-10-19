<template>
  <main class="mx-auto max-w-[1000px] px-4 py-6 sm:px-8 sm:py-8">
    <RouterLink to="/app/jobs" class="text-sm text-emerald-700 underline">← 返回岗位</RouterLink>
    <h1 class="mt-5 text-3xl font-bold">单岗位证据分析</h1>
    <p class="mt-2 text-sm text-slate-600">逐条对照招聘要求与本人记录。结果仅用于准备求职，不代表真实能力评定。</p>

    <p v-if="error" role="alert" class="mt-5 rounded-lg bg-red-50 p-3 text-red-700">{{ error }}</p>
    <p v-if="loading" role="status" class="mt-5 text-slate-500">正在读取岗位…</p>

    <section v-if="job" class="mt-6 rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
      <h2 class="text-xl font-bold">{{ job.company_name }} · {{ job.title }}</h2>
      <p class="mt-3 text-sm font-bold text-slate-700">已录入的招聘要求</p>
      <p v-if="job.requirements_text" class="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-600">{{ job.requirements_text }}</p>
      <p v-else class="mt-2 text-sm text-amber-800">该岗位还没有招聘要求，请返回岗位页编辑。</p>
    </section>

    <section v-if="job?.requirements_text" class="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-5 text-sm leading-6 text-amber-950">
      <p>第一步只发送岗位名称与招聘要求；你核对后，第二步才发送本人填写的教育、项目、其他经历、技能和<strong>已确认</strong>的简历文字。未确认的简历不会发送，结果不保存。</p>
      <button class="mt-4 rounded-lg bg-emerald-700 px-5 py-3 font-bold text-white disabled:opacity-50"
        :disabled="busy" @click="extract">
        {{ busy ? '处理中…' : extraction ? '重新提取岗位要求' : '提取岗位要求' }}
      </button>
    </section>

    <section v-if="extraction" class="mt-6 rounded-2xl border border-slate-200 bg-white p-5 sm:p-6" aria-label="核对岗位要求">
      <h2 class="text-xl font-bold">核对岗位要求</h2>
      <p class="mt-2 text-sm leading-6 text-slate-600">模型可能提错。请逐条对照上方原文，删除误提项并调整优先级；遗漏或有误的原文可先返回岗位页修改，再重新提取。保留至少一条要求。</p>
      <div v-for="(item, index) in extraction.items" :key="`${index}-${item.quote}`" class="mt-4 rounded-xl border border-slate-200 p-4">
        <p class="whitespace-pre-wrap text-sm font-bold">{{ index + 1 }}. {{ item.quote }}</p>
        <div class="mt-3 flex flex-wrap items-center gap-3">
          <label class="text-sm">优先级
            <select v-model="item.priority" class="ml-2 rounded-lg border border-slate-300 bg-white px-3 py-2">
              <option value="required">必须要求</option>
              <option value="preferred">优先条件</option>
              <option value="unspecified">未标注</option>
            </select>
          </label>
          <button type="button" class="rounded-lg border border-red-200 px-3 py-2 text-sm text-red-700 disabled:opacity-50"
            :disabled="busy" @click="extraction.items.splice(index, 1)">删除误提项</button>
        </div>
      </div>
      <p v-if="!extraction.items.length" class="mt-4 text-sm text-amber-800">已删除全部要求。请重新提取，或返回岗位页调整招聘原文。</p>
      <button type="button" class="mt-5 rounded-lg bg-emerald-700 px-5 py-3 font-bold text-white disabled:opacity-50"
        :disabled="busy || !extraction.items.length" @click="runAnalysis">
        {{ busy ? '分析中…' : '按已核对要求分析' }}
      </button>
    </section>

    <section v-if="result" class="mt-6 space-y-4" aria-label="分析结果">
      <div class="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-700">
        <p>依据来自你自行填写的岗位和个人资料，系统没有核实岗位或经历的真实性；模型的语义判断也可能出错。</p>
        <p>{{ result.resume_used ? '本次使用了已确认的简历文字。' : '本次没有使用简历：请先核对并确认简历文字。' }}</p>
        <p v-if="result.context_limited" class="font-bold text-amber-800">材料较长，本次只选取了部分教育、项目、技能或简历段落；遗漏的证据需人工补查。</p>
        <p>“未见证据”只表示本次材料不足，不能推断你不会这项技能。</p>
      </div>
      <article v-for="(item, index) in result.items" :key="index" class="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <h2 class="font-bold">{{ index + 1 }}. {{ item.quote }}</h2>
          <span class="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-900">{{ statusLabel[item.status] }}</span>
        </div>
        <p class="mt-2 text-xs text-slate-500">{{ priorityLabel[item.priority] }}</p>
        <p class="mt-4 whitespace-pre-wrap text-sm leading-6"><strong>判断：</strong>{{ item.reason }}</p>
        <div v-if="item.evidence.length" class="mt-4 rounded-lg bg-slate-50 p-4">
          <h3 class="text-sm font-bold">引用的个人材料</h3>
          <div v-for="source in item.evidence" :key="source.id" class="mt-3 border-t border-slate-200 pt-3 text-sm">
            <span class="font-bold">{{ evidenceLabel[source.kind] }} · {{ source.id }}</span>
            <p class="mt-1 whitespace-pre-wrap text-slate-700">{{ source.text }}</p>
          </div>
        </div>
        <p v-else class="mt-3 text-sm text-slate-500">没有可引用的个人材料。</p>
        <p class="mt-4 text-sm leading-6"><strong>下一步：</strong>{{ item.next_step }}</p>
      </article>
    </section>
  </main>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ApiError } from '../auth'
import { analyzeJob, extractRequirements, type JobAnalysisResult, type RequirementExtractionResult } from '../analysis'
import { getJob, type Job } from '../jobs'

const route = useRoute()
const job = ref<Job | null>(null)
const result = ref<JobAnalysisResult | null>(null)
const extraction = ref<RequirementExtractionResult | null>(null)
const loading = ref(false)
const busy = ref(false)
const error = ref('')

const priorityLabel = { required: '必须要求', preferred: '优先条件', unspecified: '未标注优先级' }
const statusLabel = { supported: '有明确证据', partial: '部分匹配', no_evidence: '未见足够证据' }
const evidenceLabel = { skill: '技能自评', profile: '个人资料', education: '教育经历', project: '项目经历', resume: '已确认简历' }

function message(cause: unknown): string {
  return cause instanceof ApiError ? cause.message : '操作失败，请稍后重试'
}

// 路由参数变化时重读岗位，避免浏览器复用组件后显示上一个岗位的结果。
watch(() => route.params.jobId, async (rawId) => {
  job.value = null
  result.value = null
  extraction.value = null
  error.value = ''
  const id = Number(rawId)
  if (!Number.isSafeInteger(id) || id <= 0) {
    error.value = '岗位编号无效'
    return
  }
  loading.value = true
  try {
    job.value = await getJob(id)
  } catch (cause) {
    error.value = message(cause)
  } finally {
    loading.value = false
  }
}, { immediate: true })

async function extract() {
  if (!job.value || busy.value) return
  busy.value = true
  error.value = ''
  result.value = null
  extraction.value = null
  try {
    // 同一岗位可能已在另一标签页修改；先刷新显示的原文，再提取当前版本。
    job.value = await getJob(job.value.id)
    if (!job.value.requirements_text) {
      error.value = '该岗位还没有招聘要求，请返回岗位页编辑'
      return
    }
    extraction.value = await extractRequirements(job.value.id)
  } catch (cause) {
    error.value = message(cause)
  } finally {
    busy.value = false
  }
}

async function runAnalysis() {
  if (!job.value || !extraction.value?.items.length || busy.value) return
  busy.value = true
  error.value = ''
  result.value = null
  try {
    result.value = await analyzeJob(job.value.id, extraction.value.snapshot_version, extraction.value.items)
  } catch (cause) {
    if (cause instanceof ApiError && cause.status === 409) {
      extraction.value = null
      try { job.value = await getJob(job.value.id) } catch { /* 原错误仍提示用户重新核对。 */ }
    }
    error.value = message(cause)
  } finally {
    busy.value = false
  }
}
</script>

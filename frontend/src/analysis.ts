import { request } from './auth'

export interface Evidence {
  id: string
  kind: 'skill' | 'profile' | 'education' | 'project' | 'resume'
  text: string
}

export interface RequirementDraft {
  quote: string
  priority: 'required' | 'preferred' | 'unspecified'
}

export interface RequirementExtractionResult {
  snapshot_version: string
  items: RequirementDraft[]
}

export interface AnalysisItem {
  quote: string
  priority: 'required' | 'preferred' | 'unspecified'
  status: 'supported' | 'partial' | 'no_evidence'
  evidence: Evidence[]
  reason: string
  next_step: string
}

export interface JobGuide {
  text: string
  limited: boolean
  // 内部引用编号仅用于服务端核对，不在报告正文展示。
  used_evidence_ids?: string[]
}

export interface JobAnalysisResult {
  job_id: number
  company_name: string
  title: string
  resume_used: boolean
  context_limited: boolean
  items: AnalysisItem[]
  // 旧报告没有 guide；页面保留兼容展示。
  guide?: JobGuide
}

export function extractRequirements(jobId: number): Promise<RequirementExtractionResult> {
  // 点击按钮才调用；第一步只发送岗位名称和招聘原文。
  return request(`/api/jobs/${jobId}/requirements/extract`, {}, 'POST', 60_000)
}

export function analyzeJob(jobId: number, snapshotVersion: string, items: RequirementDraft[]): Promise<JobAnalysisResult> {
  // 第二步传回人工保留的原文要求；后端重新读库、比对版本并核对每段原文。
  return request(`/api/jobs/${jobId}/analysis`, {
    snapshot_version: snapshotVersion, items,
  }, 'POST', 60_000)
}

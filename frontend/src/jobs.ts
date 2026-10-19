import { request } from './auth'

export interface JobStatus {
  id: number
  name: string
  sort_order: number
}

export interface JobForm {
  // 这里只传岗位字段；所属用户由后端根据登录会话确定，页面不能自己指定 user_id。
  company_name: string
  title: string
  location: string
  source_url: string
  requirements_text: string
  notes: string
  status_id: number
}

export interface Job extends Omit<JobForm, 'location' | 'source_url' | 'requirements_text' | 'notes'> {
  id: number
  location: string | null
  source_url: string | null
  requirements_text: string | null
  notes: string | null
  status_name: string
}

export interface CompanyGroup {
  company_name: string
  total: number
}

export interface JobList {
  items: Job[]
  total: number
  limit: number
  offset: number
}

export function listStatuses(): Promise<JobStatus[]> {
  return request('/api/job-statuses')
}

export function createStatus(name: string, sortOrder: number): Promise<JobStatus> {
  return request('/api/job-statuses', { name, sort_order: sortOrder })
}

export function updateStatus(id: number, name: string, sortOrder: number): Promise<JobStatus> {
  return request(`/api/job-statuses/${id}`, { name, sort_order: sortOrder }, 'PATCH')
}

export function deleteStatus(id: number): Promise<void> {
  // 后端删除接口仍要求 JSON 写入头，所以传空对象而非无内容请求。
  return request(`/api/job-statuses/${id}`, {}, 'DELETE')
}

export function listCompanies(): Promise<CompanyGroup[]> {
  return request('/api/jobs/companies')
}

export function listJobs(companyName: string, statusId: number, offset: number): Promise<JobList> {
  // URLSearchParams 会编码公司名中的空格、中文等字符；0 代表“全部状态”，不作为真实状态编号发给后端。
  const params = new URLSearchParams({ limit: '20', offset: String(offset) })
  if (companyName) params.set('company_name', companyName)
  if (statusId > 0) params.set('status_id', String(statusId))
  return request(`/api/jobs?${params}`)
}

export function getJob(id: number): Promise<Job> {
  return request(`/api/jobs/${id}`)
}

export function createJob(form: JobForm): Promise<Job> {
  // request 统一处理 Cookie 和写入请求头；成功返回后，页面才关闭弹窗并重新读库。
  return request('/api/jobs', form)
}

export function updateJob(id: number, form: JobForm): Promise<Job> {
  return request(`/api/jobs/${id}`, form, 'PATCH')
}

export function deleteJob(id: number): Promise<void> {
  return request(`/api/jobs/${id}`, {}, 'DELETE')
}

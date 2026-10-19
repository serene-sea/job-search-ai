import { ApiError, request } from './auth'

export interface Resume {
  source_filename: string | null
  source_format: string | null
  raw_extracted_text: string
  reviewed_text: string
  confirmed_at: string | null
  updated_at: string
}

export function loadResume(): Promise<Resume | null> {
  return request('/api/resume')
}

export function saveResumeText(text: string): Promise<Resume> {
  return request('/api/resume', { reviewed_text: text }, 'PATCH')
}

export function confirmResume(): Promise<Resume> {
  return request('/api/resume/confirm', {})
}

export function deleteResume(): Promise<void> {
  return request('/api/resume', {}, 'DELETE')
}

export async function uploadResume(file: File): Promise<Resume> {
  // 上传是 multipart；浏览器自动设置包含 boundary 的 Content-Type。
  // 服务端仍检查 Origin 和自定义请求头，不能套用 JSON 请求函数。
  const form = new FormData()
  form.append('file', file)
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 30_000)
  try {
    const response = await fetch('/api/resume/upload', {
      method: 'POST', body: form, credentials: 'same-origin', cache: 'no-store',
      headers: { 'X-Job-App-Request': '1' }, signal: controller.signal,
    })
    const body: unknown = await response.json().catch(() => null)
    if (!response.ok) {
      const detail = body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string'
        ? body.detail : '上传失败，请稍后重试'
      throw new ApiError(response.status, response.status >= 500 ? '上传暂时无法完成，请稍后重试' : detail)
    }
    return body as Resume
  } catch (cause) {
    if (cause instanceof ApiError) throw cause
    throw new ApiError(0, controller.signal.aborted ? '上传等待时间较长，请稍后查看结果' : '暂时无法连接服务，请稍后重试')
  } finally {
    window.clearTimeout(timeout)
  }
}

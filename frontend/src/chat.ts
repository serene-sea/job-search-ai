import { ApiError, request } from './auth'
import type { JobAnalysisResult, RequirementDraft } from './analysis'

export type ChatSource = 'profile' | 'education' | 'projects' | 'skills' | 'resume'

export interface ChatSession {
  id: number
  job_id: number | null
  title: string
  updated_at: string
}

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  kind: 'text' | 'report'
  content: string
  report_json: JobAnalysisResult | null
  snapshot_version: string | null
  status: 'completed' | 'running' | 'interrupted' | 'failed'
  created_at: string
}

export const listSessions = () => request<ChatSession[]>('/api/chat/sessions')
export const createSession = (jobId: number | null = null) =>
  request<ChatSession>('/api/chat/sessions', { job_id: jobId })
export const renameSession = (id: number, title: string) =>
  request<ChatSession>(`/api/chat/sessions/${id}`, { title }, 'PATCH')
export const deleteSession = (id: number) =>
  request<void>(`/api/chat/sessions/${id}`, {}, 'DELETE')
export const listMessages = (id: number) =>
  request<ChatMessage[]>(`/api/chat/sessions/${id}/messages`)
export const saveReport = (id: number, version: string, items: RequirementDraft[]) =>
  request<ChatMessage>(`/api/chat/sessions/${id}/report`, {
    snapshot_version: version, items,
  }, 'POST', 150_000)
export const stopRun = (id: number) =>
  request<{ status: string }>(`/api/chat/runs/${id}/stop`, {})

export async function streamAnswer(
  sessionId: number,
  question: string,
  mode: 'plain' | 'personal',
  sources: ChatSource[],
  signal: AbortSignal,
  onEvent: (event: string, data: Record<string, unknown>) => void,
): Promise<void> {
  // 流式接口用 fetch 直接读取 ReadableStream
  const response = await fetch(`/api/chat/sessions/${sessionId}/ask`, {
    method: 'POST', credentials: 'same-origin', cache: 'no-store', signal,
    headers: { 'Content-Type': 'application/json', 'X-Job-App-Request': '1' },
    body: JSON.stringify({ question, mode, sources, request_key: crypto.randomUUID() }),
  })
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    const detail = body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string'
      ? body.detail : '提问失败'
    throw new ApiError(response.status, response.status >= 500 ? 'AI 助手暂时无法回答，请稍后重试' : detail)
  }
  if (!response.body) throw new ApiError(0, '浏览器无法读取流式响应')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finished = false
  let streamError = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n')
      while (buffer.includes('\n\n')) {
        const end = buffer.indexOf('\n\n')
        const block = buffer.slice(0, end)
        buffer = buffer.slice(end + 2)
        const event = block.match(/^event: (.+)$/m)?.[1]
        const data = block.match(/^data: (.+)$/m)?.[1]
        if (event && data) {
          onEvent(event, JSON.parse(data) as Record<string, unknown>)
          if (event === 'done' || event === 'error') finished = true
          if (event === 'error') streamError = '模型回答失败，已保留当前收到的内容'
        }
      }
      if (done) break
    }
  } finally {
    reader.releaseLock()
  }
  if (!finished && !signal.aborted) throw new ApiError(0, '回答意外中断，请刷新查看保存状态')
  if (streamError) throw new ApiError(502, streamError)
}

import { ref } from 'vue'

export interface UserInfo {
  id: number
  username: string
}

export class ApiError extends Error {
  // 让页面能区分后端返回的错误和网络/超时错误（后者用状态 0）。
  constructor(public status: number, message: string) {
    super(message)
  }
}

// 这里只保存用于显示的用户信息；真正的登录凭证由浏览器 Cookie 保存。
export const currentUser = ref<UserInfo | null>(null)

const requestTimeoutMs = 12_000

export async function request<T>(
  path: string,
  body?: object,
  method: 'GET' | 'POST' | 'PATCH' | 'DELETE' = body === undefined ? 'GET' : 'POST',
  timeoutMs = requestTimeoutMs,
): Promise<T> {
  // 普通接口默认 12 秒；两次模型调用的分析接口可单独传入更长的等待时间。
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(path, {
      // /api 由 Vite 转给后端；同源请求会自动带上登录 Cookie。
      credentials: 'same-origin',
      cache: 'no-store',
      // 岗位编辑使用 PATCH、删除使用 DELETE；方法由调用处明确指定。
      method,
      signal: controller.signal,
      // 写入请求统一带这个头；后端会检查页面来源和这个头。
      headers: body === undefined ? undefined : {
        'Content-Type': 'application/json',
        'X-Job-App-Request': '1',
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    })

    const data: unknown = await response.json().catch((error: unknown) => {
      if (controller.signal.aborted) throw error
      return null
    })
    if (!response.ok) {
      // 服务器故障只给用户可理解的提示；具体状态码留在开发者工具的 Network 中。
      if (response.status >= 500) {
        const aiRequest = path.endsWith('/analysis') || path.endsWith('/requirements/extract') ||
          path.endsWith('/report')
        const chatRequest = path === '/api/chat/sessions'
        // AI 路由的 502/503 由后端写入不含密钥和材料的短提示；保留具体原因便于用户处理。
        const safeAiDetail = aiRequest && (response.status === 502 || response.status === 503) &&
          data && typeof data === 'object' && 'detail' in data && typeof data.detail === 'string' &&
          data.detail.length <= 120 ? data.detail : null
        throw new ApiError(response.status, safeAiDetail || (aiRequest ? 'AI 分析暂时无法完成，请稍后重试' :
          chatRequest ? '聊天暂时无法打开，请稍后重试' : '操作暂时无法完成，请稍后重试'))
      }
      const detail =
        data && typeof data === 'object' && 'detail' in data && typeof data.detail === 'string'
          ? data.detail
          : '请求失败，请稍后再试'
      throw new ApiError(response.status, detail)
    }
    return data as T
  } catch (error) {
    // 已整理好的接口错误直接交给页面显示。
    if (error instanceof ApiError) throw error
    if (controller.signal.aborted) {
      // 浏览器结束等待；服务端是否已经完成写入仍要以后端结果为准。
      throw new ApiError(0, '等待时间较长，请稍后查看结果')
    }
    throw new ApiError(0, '暂时无法连接服务，请稍后重试')
  } finally {
    window.clearTimeout(timeout)
  }
}

export function register(username: string, password: string): Promise<UserInfo> {
  // 注册只创建账号；这里不会把用户标记成已登录。
  return request<UserInfo>('/api/auth/register', { username, password })
}

export async function login(username: string, password: string): Promise<UserInfo> {
  // 后端验证成功并写入 Cookie 后，才更新页面上显示的用户。
  const user = await request<UserInfo>('/api/auth/login', { username, password })
  currentUser.value = user
  return user
}

export async function loadCurrentUser(): Promise<UserInfo | null> {
  // 刷新页面后，向后端询问 Cookie 是否仍对应有效会话。
  try {
    const user = await request<UserInfo>('/api/me')
    currentUser.value = user
    return user
  } catch (error) {
    currentUser.value = null
    // 401 表示没登录；其他错误（如数据库断开）继续抛出，让页面提示故障。
    if (error instanceof ApiError && error.status === 401) return null
    throw error
  }
}

export async function logout(): Promise<void> {
  // 退出要通知后端撤销会话，不能只清空页面上的用户名。
  try {
    await request<void>('/api/auth/logout', {})
  } catch (error) {
    // 会话本来就失效时，前端也应退出；其他错误则保留页面供重试。
    if (!(error instanceof ApiError) || error.status !== 401) throw error
  }
  currentUser.value = null
}

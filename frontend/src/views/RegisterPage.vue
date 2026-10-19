<template>
  <main class="grid min-h-screen items-center gap-10 bg-[#f5f7f4] px-8 py-12 lg:grid-cols-[minmax(0,1.1fr)_minmax(350px,.9fr)] lg:gap-20 lg:px-[7vw]">
    <div class="max-w-2xl">
      <p class="text-xs font-extrabold tracking-widest text-emerald-700">求职过程记清楚<br />AI助力指方向</p>
      <h1 class="mb-6 text-5xl font-bold tracking-tight lg:text-7xl">求职帮</h1>
      <p class="max-w-lg leading-8 text-slate-600">
        按公司整理岗位与进度，维护技能和简历。<br />可在聊天中结合自己的记录分析岗位匹配与能力差距。
      </p>
      <div class="mt-8 grid gap-1 border-l-4 border-emerald-400 py-2 pl-4 text-sm leading-7 text-emerald-900">
        <strong>创建账号</strong>
        <span>注册完成后回到登录页，再使用新账号登录。</span>
      </div>
    </div>

    <section class="rounded-2xl border border-emerald-100 bg-white p-8 shadow-xl lg:p-12" aria-labelledby="register-title">
      <HealthStatus />
      <h2 id="register-title" class="mt-7 mb-2 text-2xl font-bold">注册账号</h2>
      <p class="leading-7 text-slate-500">用户名使用 3–50 位字母、数字或下划线；密码至少 12 位。</p>
      <p v-if="errorMessage" class="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-800" role="alert">{{ errorMessage }}</p>
      <!-- 三个输入框只属于注册页；提交前先在下面的函数里核对两次密码。 -->
      <form class="mt-7 grid gap-3" @submit.prevent="submitRegister">
        <label class="text-sm font-bold" for="register-username">用户名</label>  <!-- for 属性关联输入框。用户点击标签时，输入框获得焦点，提升可访问性。 -->
        <input
          id="register-username"
          v-model="username"
          autocomplete="username"
          placeholder="请输入用户名"
          class="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
        />
        <label class="text-sm font-bold" for="register-password">密码</label>
        <input
          id="register-password"
          v-model="password"
          type="password"
          autocomplete="new-password"
          placeholder="至少 12 位"
          class="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
        />  <!-- 注册页的autocomplete也能在登录的时候让浏览器记住密码，但不会在登录页里自动填充，因为登录页的autocomplete是current-password -->
        <label class="text-sm font-bold" for="register-confirm-password">再次输入密码</label>
        <input
          id="register-confirm-password"
          v-model="confirmPassword"
          type="password"
          autocomplete="new-password"
          placeholder="请再输入一次密码"
          class="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
        />
        <button type="submit" class="mt-2 rounded-lg bg-emerald-700 px-4 py-3 font-bold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60" :disabled="busy">{{ busy ? '注册中…' : '注册' }}</button>
      </form>
      <RouterLink class="mt-5 inline-block text-sm font-bold text-emerald-700 hover:underline" to="/">已有账号？返回登录</RouterLink>
    </section>
  </main>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import HealthStatus from '../components/HealthStatus.vue'
import { ApiError, register } from '../auth'

// 注册页使用自己的输入值，切回登录页时不会把密码带过去。
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const busy = ref(false)
const errorMessage = ref('')
const router = useRouter()

function validateInput(): string | null {
  // 按顺序只返回第一条错误，让用户知道眼下该改什么。
  const name = username.value.trim()
  if (!name) return '请输入用户名'
  if (name.length < 3 || name.length > 50) return '用户名需要 3–50 位'
  if (!/^[a-z0-9_]+$/i.test(name)) return '用户名只能使用字母、数字和下划线'
  if (!password.value) return '请输入密码'
  if (password.value.length < 12) return '密码至少需要 12 位'
  if (password.value.length > 128) return '密码不能超过 128 位'
  if (!confirmPassword.value) return '请再次输入密码'
  // 两次输入只在浏览器里比较；后端只接收一份密码。
  if (password.value !== confirmPassword.value) return '两次输入的密码不一致'
  return null
}

async function submitRegister() {
  // 正在等待上一条注册请求时，不再发送第二条。
  if (busy.value) return
  errorMessage.value = ''
  const validationError = validateInput()
  if (validationError) {
    errorMessage.value = validationError
    return
  }

  busy.value = true
  try {
    // 校验通过后才请求后端；确认密码无需发送给后端。
    await register(username.value, password.value)
    password.value = ''
    confirmPassword.value = ''
    // 注册接口不建立登录状态；用户回到登录页后再登录。
    await router.replace({ path: '/', query: { registered: '1' } })
  } catch (error) {
    // 超时不等于注册失败：请求可能已被后端保存，因此不要自动重试。
    if (error instanceof ApiError && error.status === 0 && error.message.includes('超时')) {
      errorMessage.value = '注册请求超时，结果暂时无法确认。请先尝试登录，再决定是否重试注册。'
    } else {
      errorMessage.value = error instanceof ApiError ? error.message : '注册失败，请稍后再试'
    }
  } finally {
    // 无论成功或失败，等待状态都要结束。
    busy.value = false
  }
}
</script>

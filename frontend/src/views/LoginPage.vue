<template>
  <main class="grid min-h-screen items-center gap-10 bg-[#f5f7f4] px-8 py-12 lg:grid-cols-[minmax(0,1.1fr)_minmax(350px,.9fr)] lg:gap-20 lg:px-[7vw]">
    <div class="max-w-2xl">
      <p class="text-xs font-extrabold tracking-widest text-emerald-700">求职过程记清楚<br/>AI助力指方向</p>
      <h1 class="mb-6 text-5xl font-bold tracking-tight lg:text-7xl">求职帮</h1>
      <p class="max-w-lg leading-8 text-slate-600">
        按公司整理岗位与进度，维护技能和简历。<br/>可在聊天中结合自己的记录分析岗位匹配与能力差距。
      </p>
    </div>

    <section class="rounded-2xl border border-emerald-100 bg-white p-8 shadow-xl lg:p-12" aria-labelledby="login-title">
      <HealthStatus />
      <h2 id="login-title" class="mt-7 mb-2 text-2xl font-bold">登录</h2>
      <p class="leading-7 text-slate-500">输入账号密码登录，没有账号可免费注册</p>
      <p v-if="route.query.reason === 'unavailable'" class="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-800" role="alert">
        暂时无法验证登录状态，请稍后重试。
      </p>
      <p v-if="errorMessage" class="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-800" role="alert">{{ errorMessage }}</p>
      <!-- 注册页返回时只提示成功，仍要在这里真正登录。 -->
      <p v-if="!errorMessage && route.query.registered === '1'" class="mt-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800" role="status">
        注册成功，请用新账号登录。
      </p>

      <form class="mt-7 grid gap-3" @submit.prevent="submitLogin">
        <label class="text-sm font-bold" for="username">用户名</label>
        <input
            id="username"
            v-model="username"
            autocomplete="username"
            placeholder="请输入用户名"
            class="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
        />  <!-- autocomplete="username" 让浏览器记住用户名，方便下次登录 -->
        <label class="text-sm font-bold" for="password">密码</label>
        <input
          id="password"
          v-model="password"
          type="password"
          autocomplete="current-password"
          placeholder="请输入密码"
          class="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
        />
        <button type="submit" class="mt-2 rounded-lg bg-emerald-700 px-4 py-3 font-bold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60" :disabled="busy">{{ busy ? '登录中…' : '登录' }}</button>
      </form>
      <!-- 注册使用独立页面，不复用登录框里的密码
      RouterLink to="/register" 让用户点击时跳转到注册页
       -->
      <RouterLink class="mt-5 inline-block text-sm font-bold text-emerald-700 hover:underline" to="/register">没有账号？注册账号</RouterLink>
    </section>
  </main>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import HealthStatus from '../components/HealthStatus.vue'
import { ApiError, login } from '../auth'

// 输入框的值和请求状态放在这里；busy 为 true 时不能重复提交。
const username = ref('')
const password = ref('')
const busy = ref(false)
const errorMessage = ref('')
const route = useRoute()
const router = useRouter()

function showError(error: unknown) {
  errorMessage.value = error instanceof ApiError ? error.message : '操作失败，请稍后再试'
}

function validateInput(): string | null {
  // 先在页面上指出明显的输入问题；后端仍会再次检查，不能只靠页面。
  const name = username.value.trim()
  if (!name) return '请输入用户名'
  if (name.length < 3 || name.length > 50) return '用户名需要 3–50 位'
  if (!/^[a-z0-9_]+$/i.test(name)) return '用户名只能使用字母、数字和下划线'
  if (!password.value) return '请输入密码'
  if (password.value.length > 128) return '密码不能超过 128 位'
  return null
}

async function submitLogin() {
  if (busy.value) return
  errorMessage.value = ''
  const validationError = validateInput()
  if (validationError) {
    errorMessage.value = validationError
    return
  }
  busy.value = true
  try {
    // 后端验证密码并设置登录 Cookie，成功后才进入个人页。
    await login(username.value, password.value)
    password.value = ''
    // 如果用户原本想打开某个个人页，登录后回到那个页面。
    // 只接受本站 /app 下的地址，避免被带到外部网站。
    const redirect = route.query.redirect
    const target =
      typeof redirect === 'string' && (redirect === '/app' || redirect.startsWith('/app/'))
        ? redirect
        : '/app/jobs'
    await router.push(target)
  } catch (error) {
    showError(error)
  } finally {
    busy.value = false
  }
}
</script>

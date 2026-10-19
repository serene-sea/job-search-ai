<template>
  <div class="min-h-screen">
    <!-- 本窗口改动：sm 起用 fixed + inset-y-0 固定在视口左侧，页面向下滚动时菜单不动。
         overflow-y-auto 只在菜单本身高过屏幕时滚动；窄屏没有 sm:fixed，仍是顶部菜单。 -->
    <aside class="flex flex-col border-b border-slate-200 bg-white p-4 sm:fixed sm:inset-y-0 sm:left-0 sm:z-20 sm:w-[228px] sm:overflow-y-auto sm:border-r sm:border-b-0">
      <div class="flex items-center gap-3 px-2">
        <span class="grid h-9 w-9 place-items-center rounded-lg bg-emerald-700 text-lg font-extrabold text-white">求</span>
        <span><strong class="block text-sm">求职帮</strong><small class="block text-xs text-slate-400">岗位记录与 AI 建议</small></span>
      </div>
      <nav class="mt-4 flex flex-wrap gap-1 sm:mt-12 sm:grid" aria-label="个人页菜单">
        <RouterLink v-for="item in menu" :key="item.to" :to="item.to" class="rounded-lg px-3 py-2 text-sm font-bold text-slate-600 hover:bg-emerald-50 hover:text-emerald-800 [&.router-link-active]:bg-emerald-50 [&.router-link-active]:text-emerald-800">{{ item.label }}</RouterLink>
      </nav>
      <div class="mt-auto hidden gap-4 px-2 py-4 text-xs text-slate-500 sm:grid">
        <button class="w-fit rounded-lg px-2 py-2 font-bold text-emerald-800 hover:bg-emerald-50 disabled:cursor-not-allowed disabled:opacity-60" :disabled="loggingOut" @click="submitLogout">退出登录</button>
      </div>
    </aside>

    <!-- sm:ml-[228px] 必须与左侧 sm:w-[228px] 一致；fixed 元素不占文档宽度，不留空就会盖住主页面。 -->
    <div class="min-w-0 sm:ml-[228px]">
      <header class="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-4 text-sm font-bold text-slate-600 sm:h-[74px] sm:px-8">
        <span>{{ currentUser?.username }} 的工作台</span>
        <div class="flex items-center gap-2"><HealthStatus /><button class="rounded-lg px-2 py-2 text-xs font-bold text-emerald-800 hover:bg-emerald-50 disabled:opacity-60 sm:hidden" :disabled="loggingOut" @click="submitLogout">退出</button></div>
      </header>
      <p v-if="logoutError" class="mx-4 mt-4 text-sm text-red-800 sm:mx-8" role="alert">{{ logoutError }}</p>
      <RouterView />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import HealthStatus from '../components/HealthStatus.vue'
import { ApiError, currentUser, logout } from '../auth'

const router = useRouter()
const logoutError = ref('')
const loggingOut = ref(false)

const menu = [
  { to: '/app/jobs', label: '岗位' },
  { to: '/app/profile', label: '个人信息' },
  { to: '/app/educations', label: '教育经历' },
  { to: '/app/projects', label: '项目经历' },
  { to: '/app/skills', label: '技能' },
  { to: '/app/resumes', label: '简历' },
  { to: '/app/chat', label: 'AI 助手' },
]

async function submitLogout() {
  // 先让后端撤销会话，再把页面带回登录页。
  if (loggingOut.value) return
  loggingOut.value = true
  logoutError.value = ''
  try {
    await logout()
    await router.replace('/')
  } catch (error) {
    // 网络失败时不能声称服务端会话已吊销。
    logoutError.value = error instanceof ApiError ? error.message : '退出失败，请重试'
  } finally {
    loggingOut.value = false
  }
}
</script>

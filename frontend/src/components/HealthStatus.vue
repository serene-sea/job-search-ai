<!-- 展示后端健康状态的组件，只有在后端无法连接时才会显示提示。 -->
<template>
  <span v-if="state === 'offline'" class="inline-flex items-center gap-2 rounded-full bg-orange-50 px-3 py-2 text-xs font-bold whitespace-nowrap text-orange-800" role="alert">
    <span class="h-2 w-2 rounded-full bg-orange-500" aria-hidden="true"></span>
    <span>服务暂时无法连接，请稍后重试</span>
  </span>
</template>


<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'

type HealthState = 'checking' | 'online' | 'offline'

// 这里只检查后端能否响应，不代表 MySQL 可用或用户已登录。
const state = ref<HealthState>('checking')
const controller = new AbortController()  // AbortController 用于在组件卸载时取消未完成的请求，避免内存泄漏和不必要的状态更新⭐

onMounted(async () => {
  try {
    // 请求走当前前端域名的 /api，再由 Vite 开发代理转发给 FastAPI。
    const response = await fetch('/api/health', { signal: controller.signal })  // 向后端发送 GET 请求，检查健康状态。signal: controller.signal 用于在组件卸载时取消请求。
    const body: unknown = await response.json()
    if (
      response.ok &&
      typeof body === 'object' &&
      body !== null &&
      'status' in body &&
      body.status === 'ok'
    ) {
      state.value = 'online'
    } else {
      state.value = 'offline'  // 如果响应不符合预期，设置状态为 offline。
    }
  } catch {
    if (!controller.signal.aborted) state.value = 'offline'  // 如果请求被取消（组件卸载），不改变状态；否则设置状态为 offline。
  }
})

onUnmounted(() => controller.abort())  // 组件卸载时取消未完成的请求，避免内存泄漏和不必要的状态更新。
</script>

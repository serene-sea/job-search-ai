import { createRouter, createWebHistory } from 'vue-router'
import LoginPage from './views/LoginPage.vue'
import RegisterPage from './views/RegisterPage.vue'
import WorkspaceLayout from './views/WorkspaceLayout.vue'
import ProfilePage from './views/ProfilePage.vue'
import EducationPage from './views/EducationPage.vue'
import ProjectsPage from './views/ProjectsPage.vue'
import SkillsPage from './views/SkillsPage.vue'
import ResumePage from './views/ResumePage.vue'
import JobPage from './views/JobPage.vue'
import ChatPage from './views/ChatPage.vue'
import { loadCurrentUser } from './auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // 登录和注册是两个独立页面，都不要求先登录。
    { path: '/', component: LoginPage },
    { path: '/register', component: RegisterPage },
    {
      path: '/app',
      component: WorkspaceLayout,
      meta: { requiresAuth: true },
      children: [
        { path: '', redirect: '/app/jobs' },
        { path: 'jobs', component: JobPage },
        // 旧分析链接也进入统一聊天页；岗位报告在对话里生成并保存。
        { path: 'analysis/:jobId', redirect: to => ({ path: '/app/chat', query: { job_id: String(to.params.jobId) } }) },
        { path: 'profile', component: ProfilePage },
        { path: 'educations', component: EducationPage },
        { path: 'projects', component: ProjectsPage },
        { path: 'skills', component: SkillsPage },
        { path: 'resumes', component: ResumePage },
        { path: 'chat', component: ChatPage },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  // 只有个人页需要登录；注册页和登录页可以直接打开。
  if (!to.meta.requiresAuth) return
  try {
    // 等后端确认登录，再展示个人页；前端判断不能代替后端鉴权。
    const user = await loadCurrentUser()
    if (user) return
    // 保存原本要访问的地址，登录后可以回去。
    return { path: '/', query: { redirect: to.fullPath } }
  } catch {
    // 网络或数据库异常与“未登录”不同，登录页要给出故障提示。
    return { path: '/', query: { reason: 'unavailable' } }
  }
})

export default router

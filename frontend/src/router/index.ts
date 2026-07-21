import { createRouter, createWebHashHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Dashboard',
    meta: { title: '概览' },
    component: () => import('@/pages/Dashboard.vue'),
  },
  {
    path: '/chat',
    name: 'Chat',
    meta: { title: '对话', icon: 'comments' },
    component: () => import('@/pages/PlaceholderPage.vue'),
  },
  {
    path: '/memories',
    name: 'Memories',
    meta: { title: '记忆', icon: 'brain' },
    component: () => import('@/pages/PlaceholderPage.vue'),
  },
  {
    path: '/goals',
    name: 'Goals',
    meta: { title: '目标', icon: 'bullseye' },
    component: () => import('@/pages/PlaceholderPage.vue'),
  },
  {
    path: '/activities',
    name: 'Activities',
    meta: { title: '活动', icon: 'clock' },
    component: () => import('@/pages/PlaceholderPage.vue'),
  },
  {
    path: '/settings',
    name: 'Settings',
    meta: { title: '模型设置', icon: 'gear' },
    component: () => import('@/pages/SettingsModel.vue'),
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router

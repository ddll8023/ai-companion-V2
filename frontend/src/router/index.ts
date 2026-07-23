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
    component: () => import('@/pages/Chat.vue'),
  },
  {
    path: '/memories',
    name: 'Memories',
    meta: { title: '记忆', icon: 'brain' },
    component: () => import('@/pages/Memories.vue'),
  },
  {
    path: '/goals',
    name: 'Goals',
    meta: { title: '目标', icon: 'bullseye' },
    component: () => import('@/pages/Goals.vue'),
  },
  {
    path: '/understanding',
    name: 'UserUnderstanding',
    meta: { title: '用户理解', icon: 'user' },
    component: () => import('@/pages/UserUnderstanding.vue'),
  },
  {
    path: '/activities',
    name: 'Activities',
    meta: { title: '活动', icon: 'clock' },
    component: () => import('@/pages/Activities.vue'),
  },
  {
    path: '/settings',
    name: 'Settings',
    meta: { title: '模型设置', icon: 'gear' },
    component: () => import('@/pages/SettingsModel.vue'),
  },
  {
    path: '/settings/privacy',
    name: 'SettingsPrivacy',
    meta: { title: '隐私设置', icon: 'shield' },
    component: () => import('@/pages/SettingsPrivacy.vue'),
  },
  {
    path: '/settings/data',
    name: 'DataManagement',
    meta: { title: '数据管理', icon: 'database' },
    component: () => import('@/pages/DataManagement.vue'),
  },
  {
    path: '/settings/status',
    name: 'SystemStatus',
    meta: { title: '系统状态', icon: 'heart-pulse' },
    component: () => import('@/pages/SystemStatus.vue'),
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router

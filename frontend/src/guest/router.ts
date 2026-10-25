import { createRouter, createWebHistory, type RouteRecordRaw, type RouterHistory } from 'vue-router'

export const GUEST_BASE = '/s'

export const routes: RouteRecordRaw[] = [
  { path: '/:token', name: 'Sign', component: () => import('./pages/SignPage.vue'), props: true },
  { path: '/:pathMatch(.*)*', name: 'NotFound', component: () => import('./pages/NotFound.vue') },
]

export function createGuestRouter(history: RouterHistory = createWebHistory(GUEST_BASE)) {
  return createRouter({ history, routes })
}

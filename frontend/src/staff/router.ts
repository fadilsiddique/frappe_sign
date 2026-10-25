import { createRouter, createWebHistory, type RouteRecordRaw, type RouterHistory } from 'vue-router'

export const STAFF_BASE = '/sign'

export const routes: RouteRecordRaw[] = [
  { path: '/', name: 'Home', component: () => import('./pages/Home.vue') },
  { path: '/templates', name: 'Templates', component: () => import('./pages/Templates.vue') },
  {
    path: '/templates/:id/design',
    name: 'Designer',
    component: () => import('./pages/Designer.vue'),
    props: true,
  },
  { path: '/:pathMatch(.*)*', name: 'NotFound', component: () => import('./pages/Home.vue') },
]

export function createStaffRouter(history: RouterHistory = createWebHistory(STAFF_BASE)) {
  return createRouter({ history, routes })
}

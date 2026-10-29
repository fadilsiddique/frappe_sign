import { createRouter, createWebHistory, type RouteRecordRaw, type RouterHistory } from 'vue-router'

export const STAFF_BASE = '/sign'

export const routes: RouteRecordRaw[] = [
  { path: '/', name: 'Home', component: () => import('./pages/Home.vue') },
  { path: '/requests', name: 'Requests', component: () => import('./pages/Requests.vue') },
  {
    path: '/requests/:id',
    name: 'Request',
    component: () => import('./pages/RequestDetail.vue'),
    props: true,
  },
  // The old paths (D18): bookmarks and the links in Desk keep working.
  { path: '/envelopes', redirect: (to) => ({ path: '/requests', query: to.query }) },
  {
    path: '/envelopes/:id',
    redirect: (to) => ({ path: `/requests/${String(to.params.id)}`, query: to.query }),
  },
  { path: '/new', name: 'SendWizard', component: () => import('./pages/SendWizard.vue') },
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

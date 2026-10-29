import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import App from '@/staff/App.vue'
import AppSidebar from '@/staff/shell/AppSidebar.vue'
import { NAV_ITEMS } from '@/staff/shell/nav'

// The sidebar's calls: two documents wait for the user's signature, and 3 setup steps are left.
vi.mock('frappe-ui', async (original) => ({
  ...(await original<typeof import('frappe-ui')>()),
  createResource: ({ url }: { url: string }) => ({
    data: url.endsWith('get_dashboard')
      ? { to_sign: [{}, {}], waiting: [], month: { completed: 0, waiting: 0, declined: 0 } }
      : {
          complete: false,
          steps: ['email', 'seal', 'profile', 'documents'].map((key, index) => ({
            key,
            done: index === 0,
            required: true,
            can_fix: true,
            facts: {},
          })),
        },
  }),
}))

const Page = defineComponent({ render: () => h('p', 'page') })
function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: ['Home', 'Requests', 'Request', 'SendWizard', 'Templates', 'Designer'].map((name) => ({
      name,
      path: name === 'Home' ? '/' : `/${name.toLowerCase()}`,
      component: Page,
    })),
  })
}

function setViewport(mobile: boolean) {
  window.matchMedia = vi.fn().mockReturnValue({
    matches: mobile,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }) as unknown as typeof window.matchMedia
}

beforeEach(() => {
  window.frappe_sign = {
    user: 'mariam@gulftrading.example',
    full_name: 'Mariam Haddad',
    branding: { company: 'Gulf Trading LLC', logo: null, brand_color: null },
  }
})
afterEach(() => {
  delete window.frappe_sign
})

describe('AppSidebar', () => {
  async function mountAt(path: string) {
    const router = makeRouter()
    await router.push(path)
    const sidebar = mount(AppSidebar, { global: { plugins: [router] } })
    await flushPromises()
    return sidebar
  }

  it('lists every section, Back to Desk, the user and the company', async () => {
    const sidebar = await mountAt('/')
    for (const item of NAV_ITEMS) expect(sidebar.find(`[data-testid="nav-${item.key}"]`).exists()).toBe(true)
    expect(sidebar.text()).toContain('Back to Desk')
    expect(sidebar.text()).toContain('Mariam Haddad')
    expect(sidebar.text()).toContain('Gulf Trading LLC')
  })

  it('counts what waits for the user under To sign', async () => {
    const sidebar = await mountAt('/')
    // The suffix sits beside the link, in the same row.
    const row = sidebar.find('[data-testid="nav-to-sign"]').element.closest('[data-slot="sidebar-item"]')
    expect(row?.textContent).toContain('2')
  })

  it('counts the setup steps left beside Settings', async () => {
    const sidebar = await mountAt('/')
    const row = sidebar.find('[data-testid="nav-settings"]').element.closest('[data-slot="sidebar-item"]')
    expect(row?.textContent).toContain('3 left')
  })

  it('lights up the section of the current page', async () => {
    const sidebar = await mountAt('/designer')
    const active = sidebar.findAll('[data-slot="sidebar-item"][data-state="active"]')
    expect(active).toHaveLength(1)
    expect(active[0]!.text()).toContain('Templates')
  })
})

describe('App shell', () => {
  async function mountApp(path: string, mobile: boolean) {
    setViewport(mobile)
    const router = makeRouter()
    await router.push(path)
    const app = mount(App, { global: { plugins: [router] }, attachTo: document.body })
    await flushPromises()
    return app
  }

  it('uses the sidebar on desktop and the tab bar on phones', async () => {
    const desktop = await mountApp('/', false)
    expect(document.querySelector('[data-testid="sidebar"]')).not.toBeNull()
    expect(document.querySelector('[data-testid="mobile-nav"]')).toBeNull()
    desktop.unmount()

    const phone = await mountApp('/', true)
    expect(document.querySelector('[data-testid="mobile-nav"]')).not.toBeNull()
    expect(document.querySelector('[data-testid="sidebar"]')).toBeNull()
    phone.unmount()
  })

  it('gives the designer the full width', async () => {
    const app = await mountApp('/designer', false)
    expect(document.querySelector('[data-testid="sidebar"]')).toBeNull()
    app.unmount()
  })
})

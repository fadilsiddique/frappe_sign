import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { HEALTH_ICON, SETTINGS_TABS, type HealthReport } from '@/staff/settings/types'

const report: HealthReport = {
  status: 'warn',
  checked_on: '2026-10-29 10:00:00',
  checks: [
    { key: 'seal', title: 'Company seal', status: 'ok', detail: 'Gulf: valid until 2028-01-01', hint: '' },
    {
      key: 'tsa',
      title: 'Timestamp servers',
      status: 'warn',
      detail: 'http://a.test: down',
      hint: 'Add another server.',
    },
  ],
}

vi.mock('frappe-ui', async (importOriginal) => {
  const actual = await importOriginal<typeof import('frappe-ui')>()
  return {
    ...actual,
    createResource: () => ({ data: report, loading: false, error: null, update: vi.fn(), reload: vi.fn() }),
  }
})

describe('settings health', () => {
  it('is the last settings tab', () => {
    expect(SETTINGS_TABS.at(-1)).toEqual({ key: 'health', label: 'Health' })
  })

  it('gives every status an icon, a colour and a word', () => {
    for (const status of ['ok', 'info', 'warn', 'fail'] as const) {
      const entry = HEALTH_ICON[status]
      expect(entry.icon).toMatch(/^lucide-/)
      expect(entry.color).toMatch(/^text-/)
      expect(entry.label.length).toBeGreaterThan(2)
    }
  })

  it('lists each check with its detail and hint, and says what the worst one means', async () => {
    const { default: HealthTab } = await import('@/staff/settings/HealthTab.vue')
    const tab = mount(HealthTab, {
      global: { stubs: { ResourceState: { template: '<div><slot /></div>' } } },
    })
    await flushPromises()
    expect(tab.get('[data-testid="health-summary"]').text()).toBe('Something needs a look.')
    expect(tab.get('[data-testid="health-seal"]').attributes('data-status')).toBe('ok')
    const warn = tab.get('[data-testid="health-tsa"]')
    expect(warn.text()).toContain('http://a.test: down')
    expect(warn.text()).toContain('Add another server.')
    expect(warn.get('[role="img"]').attributes('aria-label')).toBe('Needs a look')
  })
})

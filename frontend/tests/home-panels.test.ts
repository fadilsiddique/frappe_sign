import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import OrderDots from '@/staff/components/OrderDots.vue'
import SetupPanel from '@/staff/home/SetupPanel.vue'
import ToSignPanel from '@/staff/home/ToSignPanel.vue'
import type { SetupStatus, SetupStep, WaitingRow } from '@/staff/home/types'
import WaitingPanel from '@/staff/home/WaitingPanel.vue'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/:any(.*)*', component: { render: () => null } }],
})
const global = { plugins: [router] }

const step = (key: SetupStep['key'], done: boolean, canFix = true): SetupStep => ({
  key,
  done,
  can_fix: canFix,
  required: true,
  facts: key === 'email' && done ? { email_id: 'sign@gulftrading.ae' } : {},
})

describe('SetupPanel', () => {
  const status = (canFix = true): SetupStatus => ({
    complete: false,
    steps: [
      step('email', true, canFix),
      step('seal', false, canFix),
      step('profile', false, canFix),
      step('documents', false, canFix),
      step('template', false, canFix),
      step('test', false, canFix),
    ],
  })

  it('opens the first step to do with its action as the primary button', () => {
    const panel = mount(SetupPanel, { props: { status: status() }, global })
    expect(panel.text()).toContain('1 of 6')
    const details = panel.findAll('[data-testid="step-detail"]')
    expect(details).toHaveLength(1)
    expect(details[0]!.element.closest('li')!.dataset.step).toBe('seal')
    const action = details[0]!.find('a')
    expect(action.text()).toContain('Create a seal')
    expect(action.attributes('href')).toBe('/settings')
  })

  it('shows what a done step set up, and opens any step on click', async () => {
    const panel = mount(SetupPanel, { props: { status: status() }, global })
    expect(panel.find('[data-step="email"]').text()).toContain('sign@gulftrading.ae')
    await panel.find('[data-step="template"] button').trigger('click')
    const detail = panel.find('[data-step="template"] [data-testid="step-detail"]')
    expect(detail.text()).toContain('A template says who signs and where.')
    expect(panel.findAll('[data-testid="step-detail"]')).toHaveLength(1)
  })

  it('tells someone without the rights who can do it', () => {
    const panel = mount(SetupPanel, { props: { status: status(false) }, global })
    expect(panel.find('[data-testid="step-detail"]').text()).toContain('Ask a Sign Manager or System Manager')
    expect(panel.find('[data-testid="step-detail"] a').exists()).toBe(false)
  })
})

describe('ToSignPanel', () => {
  it('lists what waits for the user, with the role and the button', () => {
    const panel = mount(ToSignPanel, {
      props: {
        rows: [
          {
            name: 'SIGN-1',
            title: 'Quotation for Saffron Hospitality',
            sender_name: 'Ahmed Khan',
            kind: 'Approver' as const,
            age_seconds: 7200,
            expires_on: null,
          },
        ],
      },
      global,
    })
    const row = panel.find('[data-testid="to-sign-row"]')
    expect(row.text()).toContain('Ahmed Khan asked you to approve, 2 hours ago')
    expect(row.text()).toContain('You approve')
    expect(row.find('button').text()).toBe('Approve')
  })

  it('says the user is all caught up', () => {
    expect(mount(ToSignPanel, { props: { rows: [] }, global }).text()).toContain('You are all caught up')
  })
})

describe('WaitingPanel', () => {
  const row = (name: string, group: WaitingRow['group'], soon = false): WaitingRow => ({
    name,
    title: `Request ${name}`,
    group,
    next: [{ full_name: 'Omar Farouk', status: 'Sent', viewed_seconds: null }],
    people: [
      { name: 'r1', full_name: 'Fatima Ali', kind: 'Signer', status: 'Signed', next: false },
      { name: 'r2', full_name: 'Omar Farouk', kind: 'Signer', status: 'Sent', next: true },
    ],
    signed: 1,
    total: 2,
    sent_seconds: 0,
    expires_on: '2026-11-05',
    expiring_soon: soon,
  })

  it('groups by who to chase and links each request', () => {
    const panel = mount(WaitingPanel, {
      props: { rows: [row('A', 'outside'), row('B', 'team'), row('C', 'outside', true)], setupDone: true },
      global,
    })
    const groups = panel.findAll('[data-group]')
    expect(groups.map((g) => g.attributes('data-group'))).toEqual(['outside', 'team'])
    expect(groups[0]!.findAll('[data-testid="waiting-row"]')).toHaveLength(2)
    const first = groups[0]!.find('[data-testid="waiting-row"]')
    expect(first.attributes('href')).toBe('/requests/A')
    expect(first.text()).toContain('Next: Omar Farouk, not opened yet')
    expect(first.text()).toContain('1 of 2')
    expect(groups[0]!.findAll('[data-testid="waiting-row"]')[1]!.text()).toMatch(/Ends /)
  })

  it('says what to do when nothing waits', () => {
    expect(mount(WaitingPanel, { props: { rows: [], setupDone: false }, global }).text()).toContain(
      'Finish setting up, then send your first request.',
    )
  })
})

describe('OrderDots', () => {
  it('numbers people and marks who signed and who is next', () => {
    const dots = mount(OrderDots, {
      props: {
        people: [
          { status: 'Signed', next: false },
          { status: 'Sent', next: true },
          { status: 'Pending', next: false },
        ],
      },
    })
    const items = dots.findAll('[data-state]')
    expect(items.map((d) => d.attributes('data-state'))).toEqual(['signed', 'next', 'later'])
    expect(items[1]!.text()).toBe('2')
  })
})

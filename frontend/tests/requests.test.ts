import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { activityLines, type ActivityEvent } from '@/staff/requests/activity'
import { nextPeople, type Person } from '@/staff/requests/people'
import { checkWarnings } from '@/staff/send/warnings'
import { requestLine } from '@/staff/requests/lines'
import RequestList from '@/staff/requests/RequestList.vue'
import RequestsToolbar from '@/staff/requests/RequestsToolbar.vue'
import type { RequestFilters, RequestRow, Tab } from '@/staff/requests/types'
import { emptyFilters, hasFilters } from '@/staff/requests/useRequests'
import { createStaffRouter } from '@/staff/router'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/:any(.*)*', component: { render: () => null } }],
})
const global = { plugins: [router] }

function row(name: string, group: RequestRow['group'], overrides: Partial<RequestRow> = {}): RequestRow {
  return {
    name,
    title: `Request ${name}`,
    group,
    status:
      group === 'done' ? 'Completed' : group === 'draft' ? 'Draft' : group === 'closed' ? 'Declined' : 'Sent',
    send_state: null,
    sealing_state: null,
    reference_doctype: null,
    reference_name: null,
    sender: 'a@example.com',
    sender_name: 'Mariam Haddad',
    next: [{ full_name: 'Omar Farouk', status: 'Sent', viewed_seconds: null }],
    people: [],
    signed: 1,
    total: 2,
    sent_seconds: 60,
    expires_on: '2026-11-05',
    expiring_soon: false,
    ...overrides,
  }
}

describe('activityLines', () => {
  const people = [
    { name: 'r1', full_name: 'Fatima Ali' },
    { name: 'r2', full_name: 'Omar Farouk' },
  ]
  const event = (seq: number, name: string, recipient_row: string | null = null): ActivityEvent => ({
    seq,
    event: name,
    at: '2026-10-25 10:00:00 Asia/Dubai',
    actor: null,
    ip: null,
    recipient_row,
    ago_seconds: 7200,
  })

  it('writes the key events as sentences, newest first', () => {
    const lines = activityLines(
      [event(1, 'Created'), event(2, 'Sent'), event(3, 'Viewed', 'r2'), event(4, 'Signed', 'r1')],
      people,
    )
    expect(lines.map((line) => line.text)).toEqual([
      'Fatima Ali signed',
      'Omar Farouk opened the document',
      'The request was sent',
      'The request was created',
    ])
    expect(lines[0]!.ago).toBe('2 hours ago')
  })

  it('leaves routine steps to the audit details', () => {
    const lines = activityLines(
      [
        event(1, 'OTP Sent', 'r1'),
        event(2, 'Consented', 'r1'),
        event(3, 'Field Filled', 'r1'),
        event(4, 'Downloaded'),
      ],
      people,
    )
    expect(lines).toEqual([])
  })

  it('says "Someone" when the person is unknown', () => {
    expect(activityLines([event(1, 'Declined')], people)[0]!.text).toBe('Someone declined')
    expect(activityLines([event(1, 'Reminded', 'r2')], people)[0]!.text).toBe(
      'A reminder was sent to Omar Farouk',
    )
  })
})

describe('requestLine', () => {
  it('says how each kind of request stands', () => {
    expect(requestLine(row('A', 'outside'))).toBe('Next: Omar Farouk, not opened yet')
    expect(requestLine(row('B', 'draft', { total: 0 }))).toBe('Draft, people not chosen yet')
    expect(requestLine(row('C', 'draft'))).toBe('Draft, not sent yet')
    expect(requestLine(row('D', 'done'))).toBe('Everyone signed')
    expect(requestLine(row('E', 'closed', { status: 'Voided' }))).toBe('Voided by the sender')
    expect(requestLine(row('F', 'closed', { status: 'Expired' }))).toBe('Nobody finished before it expired')
  })
})

describe('RequestList', () => {
  const rows = [
    row('A', 'outside'),
    row('B', 'team'),
    row('C', 'outside', { expiring_soon: true }),
    row('D', 'done'),
  ]

  it('groups the rows and keeps the group order', () => {
    const list = mount(RequestList, { props: { rows, selected: null }, global })
    expect(list.findAll('[data-group]').map((g) => g.attributes('data-group'))).toEqual([
      'outside',
      'team',
      'done',
    ])
    expect(list.find('[data-group="outside"]').findAll('[data-testid="request-row"]')).toHaveLength(2)
  })

  it('marks the selected row and tells the page which row was picked', async () => {
    const list = mount(RequestList, { props: { rows, selected: 'B' }, global })
    expect(list.find('[data-row="B"]').attributes('aria-selected')).toBe('true')
    expect(list.find('[data-row="A"]').attributes('aria-selected')).toBe('false')
    await list.find('[data-row="C"]').trigger('click')
    expect(list.emitted('select')![0]![0]).toMatchObject({ name: 'C' })
  })

  it('moves the selection with the arrow keys, in the order on screen', async () => {
    const list = mount(RequestList, { props: { rows, selected: 'A' }, global, attachTo: document.body })
    // On screen: A, C (outside), B (team), D (done).
    await list.find('[data-testid="request-list"]').trigger('keydown', { key: 'ArrowDown' })
    expect(list.emitted('select')![0]![0]).toMatchObject({ name: 'C' })
    list.unmount()
  })

  it('shows progress and the expiry in fixed lanes, amber when close', () => {
    const list = mount(RequestList, { props: { rows, selected: null }, global })
    const first = list.find('[data-row="A"]')
    expect(first.text()).toContain('1 of 2')
    expect(list.find('[data-row="C"]').text()).toMatch(/Ends /)
    expect(list.find('[data-row="D"]').text()).not.toMatch(/Nov/)
  })
})

describe('RequestsToolbar', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  const mountToolbar = (filters: RequestFilters = emptyFilters()) =>
    mount(RequestsToolbar, {
      props: {
        tab: 'open' as Tab,
        filters,
        counts: { open: 4, completed: 2, closed: 1, all: 7 },
        options: { doctypes: ['Quotation'], senders: [] },
        'onUpdate:tab': (value: Tab) => toolbar.setProps({ tab: value }),
        'onUpdate:filters': (value: RequestFilters) => toolbar.setProps({ filters: value }),
      },
    })
  let toolbar: ReturnType<typeof mountToolbar>

  it('shows the counts on the pills and switches the tab', async () => {
    toolbar = mountToolbar()
    expect(toolbar.find('[data-testid="count-open"]').text()).toBe('4')
    expect(toolbar.find('[data-testid="count-all"]').text()).toBe('7')
    expect(toolbar.find('[data-testid="pill-open"]').attributes('aria-pressed')).toBe('true')
    await toolbar.find('[data-testid="pill-completed"]').trigger('click')
    expect(toolbar.emitted('update:tab')![0]).toEqual(['completed'])
  })

  it('searches after a pause in typing, not on every key', async () => {
    toolbar = mountToolbar()
    const input = toolbar.find('input[type="search"]')
    await input.setValue('lea')
    await input.setValue('lease')
    vi.advanceTimersByTime(299)
    expect(toolbar.emitted('update:filters')).toBeUndefined()
    vi.advanceTimersByTime(2)
    await flushPromises()
    expect(toolbar.emitted('update:filters')).toHaveLength(1)
    expect((toolbar.emitted('update:filters')![0]![0] as RequestFilters).search).toBe('lease')
  })

  it('opens the filter row on demand, and offers only document types that exist', async () => {
    toolbar = mountToolbar()
    expect(toolbar.find('[data-testid="filters"]').exists()).toBe(false)
    await toolbar.find('[data-testid="filter-toggle"]').trigger('click')
    const filters = toolbar.find('[data-testid="filters"]')
    expect(filters.text()).toContain('Document type')
    expect(filters.text()).not.toContain('Sent by')
  })

  it('opens the filter row when a filter is already set, and can clear it', async () => {
    toolbar = mountToolbar({ ...emptyFilters(), reference_doctype: 'Quotation' })
    expect(toolbar.find('[data-testid="filters"]').exists()).toBe(true)
    await toolbar
      .findAll('button')
      .find((b) => b.text() === 'Clear filters')!
      .trigger('click')
    expect(toolbar.emitted('update:filters')![0]![0]).toEqual(emptyFilters())
  })
})

describe('filters and routes', () => {
  it('knows when a search or filter is set', () => {
    expect(hasFilters(emptyFilters())).toBe(false)
    expect(hasFilters({ ...emptyFilters(), search: 'lease' })).toBe(true)
    expect(hasFilters({ ...emptyFilters(), date_to: '2026-11-01' })).toBe(true)
  })

  it('moves the old envelope paths to requests, keeping the query', () => {
    const staff = createStaffRouter(createMemoryHistory())
    expect(staff.resolve('/requests').name).toBe('Requests')
    expect(staff.resolve('/requests/SIGN-1').name).toBe('Request')
    const redirect = (path: string) => {
      const record = staff.getRoutes().find((r) => r.path === path)!
      const target = record.redirect as (to: unknown) => { path: string; query?: unknown }
      return target({ params: { id: 'SIGN-1' }, query: { status: 'open' } })
    }
    expect(redirect('/envelopes')).toEqual({ path: '/requests', query: { status: 'open' } })
    expect(redirect('/envelopes/:id')).toEqual({ path: '/requests/SIGN-1', query: { status: 'open' } })
  })
})

describe('nextPeople', () => {
  const person = (name: string, status: string, order: number, kind = 'Signer'): Person => ({
    name,
    role_label: name,
    kind,
    routing_order: order,
    full_name: name,
    email: `${name}@example.com`,
    status,
    signed_on: null,
    viewed_on: null,
    decline_reason: null,
  })

  it('is the lowest unfinished order in a signing order, and ignores copies', () => {
    const people = [
      person('a', 'Signed', 1),
      person('b', 'Viewed', 2),
      person('c', 'Pending', 3),
      person('d', 'Sent', 3, 'CC'),
    ]
    expect([...nextPeople(people, 'Sequential')]).toEqual(['b'])
  })

  it('is everyone still waiting when signing all at once', () => {
    const people = [person('a', 'Signed', 1), person('b', 'Sent', 2), person('c', 'Viewed', 3)]
    expect([...nextPeople(people, 'Parallel')]).toEqual(['b', 'c'])
  })

  it('is empty when everyone finished', () => {
    expect(nextPeople([person('a', 'Signed', 1)], 'Sequential').size).toBe(0)
  })
})

describe('checkWarnings', () => {
  const anchor = (role: string) => ({
    tag: role,
    role,
    field_type: 'Signature',
    n: 1,
    page: 1,
    x: 0,
    y: 0,
    w: 1,
    h: 1,
  })
  const recipient = (role_label: string, kind = 'Signer') => ({
    role_label,
    kind,
    routing_order: 1,
    full_name: 'A',
    email: 'a@example.com',
  })

  it('warns about a role nobody has and a signer without a field', () => {
    const warnings = checkWarnings(
      [anchor('Customer'), anchor('Witness')],
      [recipient('Customer'), recipient('Company')],
    )
    expect(warnings).toHaveLength(2)
    expect(warnings[0]).toContain('Witness')
    expect(warnings[1]).toContain('Company')
  })

  it('matches roles with spaces by their underscore token, and ignores copies', () => {
    expect(
      checkWarnings([anchor('Sales_Manager')], [recipient('Sales Manager'), recipient('Archive', 'CC')]),
    ).toEqual([])
  })

  it('says so when the document has no sign_field()', () => {
    expect(checkWarnings([], [recipient('Customer')])).toHaveLength(1)
  })
})

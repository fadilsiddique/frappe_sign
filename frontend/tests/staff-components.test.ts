import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import AppPageHeader from '@/staff/components/AppPageHeader.vue'
import AvatarStack, { type StackPerson } from '@/staff/components/AvatarStack.vue'
import EmptyState from '@/staff/components/EmptyState.vue'
import ErrorState from '@/staff/components/ErrorState.vue'
import HeaderAction from '@/staff/components/HeaderAction.vue'
import ResourceState from '@/staff/components/ResourceState.vue'
import StatusBadge from '@/staff/components/StatusBadge.vue'

describe('StatusBadge', () => {
  it('shows the plain word and colour', () => {
    const badge = mount(StatusBadge, { props: { status: 'In Progress', sealing: 'Not Started' } })
    expect(badge.text()).toBe('Waiting')
    expect(badge.html()).toContain('blue')
  })

  it('shows a failed seal in red', () => {
    const badge = mount(StatusBadge, { props: { status: 'In Progress', sealing: 'Failed' } })
    expect(badge.text()).toBe('Seal failed')
    expect(badge.html()).toContain('red')
  })
})

describe('AvatarStack', () => {
  const people: StackPerson[] = [
    { name: 'Fatima Ali', state: 'signed' },
    { name: 'Omar Farouk', state: 'opened' },
    { name: 'Khalid Nasser', state: 'waiting' },
    { name: 'Noor Aziz', state: 'declined' },
    { name: 'Sara Idris', state: 'waiting' },
  ]

  it('rings each person by state and ticks who signed', () => {
    const stack = mount(AvatarStack, { props: { people: people.slice(0, 4) } })
    const items = stack.findAll('li')
    expect(items).toHaveLength(4)
    expect(items[0]!.classes()).toContain('ring-green-500')
    expect(items[1]!.classes()).toContain('ring-blue-500')
    expect(items[2]!.classes()).toContain('ring-gray-300')
    expect(items[3]!.classes()).toContain('ring-red-500')
    expect(items[0]!.find('.lucide-check').exists()).toBe(true)
    expect(items[1]!.find('.lucide-check').exists()).toBe(false)
  })

  it('names each person and state for screen readers', () => {
    const stack = mount(AvatarStack, { props: { people: people.slice(0, 2) } })
    expect(stack.findAll('li').map((li) => li.attributes('aria-label'))).toEqual([
      'Fatima Ali: signed',
      'Omar Farouk: opened, not signed',
    ])
  })

  it('folds the people that do not fit into "+n"', () => {
    const stack = mount(AvatarStack, { props: { people, max: 4 } })
    const items = stack.findAll('li')
    expect(items).toHaveLength(4)
    expect(items[3]!.text()).toBe('+2')
    expect(items[3]!.attributes('aria-label')).toBe('Noor Aziz: declined, Sara Idris: not opened yet')
  })
})

describe('EmptyState and ErrorState', () => {
  it('shows the title, the next step and its action', () => {
    const empty = mount(EmptyState, {
      props: { title: 'No requests yet', text: 'Send one from a Quotation.', icon: 'lucide-send' },
      slots: { action: () => h('button', 'New request') },
    })
    expect(empty.text()).toContain('No requests yet')
    expect(empty.text()).toContain('Send one from a Quotation.')
    expect(empty.find('button').text()).toBe('New request')
  })

  it('asks to try again', async () => {
    const error = mount(ErrorState, { props: { message: 'Not permitted' } })
    expect(error.attributes('role')).toBe('alert')
    await error.find('button').trigger('click')
    expect(error.emitted('retry')).toHaveLength(1)
  })
})

describe('ResourceState', () => {
  const slots = {
    default: () => h('p', { id: 'content' }, 'rows'),
    empty: () => h('p', { id: 'empty' }, 'none'),
  }
  const resource = (data: unknown, error: unknown = null) => ({ data, error, reload: vi.fn() })

  it('shows a skeleton until the first data arrives', () => {
    const view = mount(ResourceState, { props: { resource: resource(null) }, slots })
    expect(view.find('[data-testid="list-skeleton"]').exists()).toBe(true)
    expect(view.attributes('aria-busy')).toBe('true')
  })

  it('shows the empty slot for an empty list, and the content otherwise', () => {
    expect(
      mount(ResourceState, { props: { resource: resource([]) }, slots })
        .find('#empty')
        .exists(),
    ).toBe(true)
    expect(
      mount(ResourceState, { props: { resource: resource([1]) }, slots })
        .find('#content')
        .exists(),
    ).toBe(true)
  })

  it('takes a custom empty check', () => {
    const view = mount(ResourceState, {
      props: {
        resource: resource({ rows: [] }),
        isEmpty: (data: unknown) => !(data as { rows: [] }).rows.length,
      },
      slots,
    })
    expect(view.find('#empty').exists()).toBe(true)
  })

  it('shows the error and reloads on retry, also for list resources', async () => {
    const plain = resource(null, { messages: ['Not permitted'] })
    const view = mount(ResourceState, { props: { resource: plain }, slots })
    expect(view.text()).toContain('Not permitted')
    await view.find('button').trigger('click')
    await flushPromises()
    expect(plain.reload).toHaveBeenCalledOnce()

    const list = { data: null, list: { error: new Error('Timed out') }, reload: vi.fn() }
    expect(mount(ResourceState, { props: { resource: list }, slots }).text()).toContain('Timed out')
  })
})

describe('HeaderAction', () => {
  function mountAt(mobile: boolean) {
    window.matchMedia = vi.fn().mockReturnValue({
      matches: mobile,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }) as unknown as typeof window.matchMedia
    return mount(HeaderAction, { props: { label: 'New request', icon: 'lucide-plus' } })
  }

  it('shows the label on desktop', () => {
    expect(mountAt(false).text()).toContain('New request')
  })

  it('shows only the icon on phones, named for screen readers', () => {
    const button = mountAt(true).find('button')
    expect(button.text()).toBe('')
    expect(button.attributes('aria-label')).toBe('New request')
  })
})

describe('AppPageHeader', () => {
  function mountAt(mobile: boolean) {
    window.matchMedia = vi.fn().mockReturnValue({
      matches: mobile,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }) as unknown as typeof window.matchMedia
    return mount(AppPageHeader, {
      props: { title: 'Sent' },
      slots: { primary: () => h('button', 'New request'), actions: () => h('button', 'Void') },
      attachTo: document.body,
    })
  }

  it('keeps every action in the header on desktop', () => {
    const header = mountAt(false)
    expect(header.text()).toContain('Sent')
    expect(header.text()).toContain('Void')
    expect(header.find('[data-testid="page-actions"]').exists()).toBe(false)
    header.unmount()
  })

  it('moves the other actions under the header on phones', () => {
    const header = mountAt(true)
    const row = header.find('[data-testid="page-actions"]')
    expect(row.text()).toBe('Void')
    expect(row.text()).not.toContain('New request')
    header.unmount()
  })
})

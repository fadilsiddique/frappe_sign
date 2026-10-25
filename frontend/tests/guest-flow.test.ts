import { describe, expect, it } from 'vitest'
import { SignApiError } from '@/shared/api'
import { canFinish, nextRequired, remaining, terminalFor } from '@/guest/flow'
import type { GuestField } from '@/guest/types'

function field(key: string, page: number, y: number, extra: Partial<GuestField> = {}): GuestField {
  return {
    key,
    type: 'Text',
    page,
    rect: { x: 0.1, y, w: 0.2, h: 0.05 },
    required: true,
    read_only: false,
    value: null,
    filled: false,
    options: [],
    font_size: 11,
    ...extra,
  }
}

describe('terminal screens', () => {
  it.each([
    ['link_expired', {}, 'expired'],
    ['envelope_not_open', { status: 'Voided' }, 'voided'],
    ['envelope_not_open', { status: 'Declined' }, 'declined'],
    ['envelope_not_open', { status: 'Completed' }, 'completed'],
    ['envelope_not_open', { status: 'Expired' }, 'expired'],
    ['recipient_done', { status: 'Signed' }, 'already'],
    ['recipient_done', { status: 'Delegated' }, 'delegated'],
    ['server_error', {}, 'error'],
  ])('%s %o -> %s', (code, data, screen) => {
    expect(terminalFor(new SignApiError(code, '', 409, data)).screen).toBe(screen)
  })

  it('names who to wait for', () => {
    const state = terminalFor(new SignApiError('not_your_turn', '', 409, { waiting_for: ['Ahmed Khan'] }))
    expect(state).toEqual({ screen: 'waiting', waitingFor: ['Ahmed Khan'] })
  })

  it('treats unknown errors as errors', () => {
    expect(terminalFor(new Error('boom')).screen).toBe('error')
  })
})

describe('next field', () => {
  const fields = [
    field('b', 1, 0.5),
    field('a', 1, 0.1),
    field('date', 1, 0.2, { type: 'Date Signed' }),
    field('optional', 1, 0.3, { required: false }),
    field('c', 2, 0.1, { type: 'Signature' }),
    field('agree', 2, 0.4, { type: 'Checkbox', value: '0' }),
  ]

  it('walks required fields in reading order and wraps', () => {
    expect(nextRequired(fields)?.key).toBe('a')
    expect(nextRequired(fields, 'a')?.key).toBe('b')
    expect(nextRequired(fields, 'b')?.key).toBe('c')
    expect(nextRequired(fields, 'agree')?.key).toBe('a')
    expect(remaining(fields)).toBe(4)
  })

  it('counts empty name and email fields as done; the server fills them', () => {
    const autofill = [field('name', 1, 0.1, { type: 'Full Name' }), field('email', 1, 0.2, { type: 'Email' })]
    expect(canFinish(autofill)).toBe(true)
  })

  it('finishes when every required field is done', () => {
    const done = fields.map((f) =>
      f.type === 'Checkbox' ? { ...f, value: '1' } : { ...f, filled: true, value: 'x' },
    )
    expect(nextRequired(done)).toBeUndefined()
    expect(canFinish(done)).toBe(true)
    expect(canFinish(fields)).toBe(false)
  })
})

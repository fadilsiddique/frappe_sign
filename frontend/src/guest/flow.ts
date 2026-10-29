// Pure logic of the guest flow: which screen an API error leads to, and the "Next field" order.
import { SignApiError } from '@/shared/api'
import type { GuestField } from './types'

export type Terminal =
  'expired' | 'voided' | 'declined' | 'completed' | 'waiting' | 'already' | 'delegated' | 'signed' | 'error'

export type Screen = 'loading' | 'verify' | 'consent' | 'sign' | Terminal

export const CAPTURE_TYPES = ['Signature', 'Initials', 'Company Stamp', 'Attachment'] as const
export const AUTOMATIC_TYPES = ['Date Signed'] as const
// Left empty, these take the signer's own name or email at finish (services/signing.py).
export const AUTOFILL_TYPES = ['Full Name', 'Email'] as const

export interface TerminalState {
  screen: Terminal
  waitingFor?: string[]
}

export function terminalFor(error: unknown): TerminalState {
  if (!(error instanceof SignApiError)) return { screen: 'error' }
  switch (error.code) {
    case 'link_expired':
      return { screen: 'expired' }
    case 'not_your_turn':
      return { screen: 'waiting', waitingFor: (error.data.waiting_for as string[]) ?? [] }
    case 'recipient_done':
      return { screen: error.data.status === 'Delegated' ? 'delegated' : 'already' }
    case 'envelope_not_open': {
      const status = error.data.status
      if (status === 'Voided') return { screen: 'voided' }
      if (status === 'Declined') return { screen: 'declined' }
      if (status === 'Completed') return { screen: 'completed' }
      return { screen: 'expired' }
    }
    default:
      return { screen: 'error' }
  }
}

// Fields the signer fills in by hand (Date Signed and read-only fields fill themselves).
export function editable(field: GuestField): boolean {
  return !field.read_only && !(AUTOMATIC_TYPES as readonly string[]).includes(field.type)
}

export function isCapture(field: GuestField): boolean {
  return (CAPTURE_TYPES as readonly string[]).includes(field.type)
}

export function isDone(field: GuestField): boolean {
  if (field.type === 'Checkbox') return field.value === '1'
  return field.filled || (AUTOFILL_TYPES as readonly string[]).includes(field.type)
}

// Reading order: page, then top to bottom, then left to right (the server sends them sorted).
export function ordered(fields: GuestField[]): GuestField[] {
  return [...fields].sort((a, b) => a.page - b.page || a.rect.y - b.rect.y || a.rect.x - b.rect.x)
}

// The next required field still empty, after `current` if given, wrapping around.
export function nextRequired(fields: GuestField[], current?: string): GuestField | undefined {
  const todo = ordered(fields).filter((f) => editable(f) && f.required && !isDone(f))
  if (!todo.length) return undefined
  const all = ordered(fields)
  const start = current ? all.findIndex((f) => f.key === current) : -1
  return todo.find((f) => all.indexOf(f) > start) ?? todo[0]
}

export function remaining(fields: GuestField[]): number {
  return fields.filter((f) => editable(f) && f.required && !isDone(f)).length
}

export function canFinish(fields: GuestField[]): boolean {
  return remaining(fields) === 0
}

// Required fields the signer fills by hand: how many are done, out of how many.
export function progress(fields: GuestField[]): { done: number; total: number } {
  // Name and email fill themselves, so they are not steps the signer takes.
  const required = fields.filter(
    (f) => editable(f) && f.required && !(AUTOFILL_TYPES as readonly string[]).includes(f.type),
  )
  return { done: required.filter(isDone).length, total: required.length }
}

export interface ReviewItem {
  key: string
  type: GuestField['type']
  page: number
  // Text to show; empty for signatures and other images, which show a "Signed" tick.
  text: string
  done: boolean
}

// What the signer is about to commit to, in reading order, for the review before finishing.
export function reviewItems(fields: GuestField[]): ReviewItem[] {
  return ordered(fields)
    .filter(
      (f) =>
        editable(f) && !(AUTOFILL_TYPES as readonly string[]).includes(f.type) && (f.required || isDone(f)),
    )
    .map((f) => ({
      key: f.key,
      type: f.type,
      page: f.page,
      text: isCapture(f) ? '' : f.type === 'Checkbox' ? '' : (f.value ?? ''),
      done: isDone(f),
    }))
}

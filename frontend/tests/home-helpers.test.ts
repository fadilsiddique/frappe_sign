import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { shortDate, timeAgo } from '@/staff/format'
import { askedLine, nextLine, notSignedYet } from '@/staff/home/lines'
import { firstOpenStep, stepsLeft, stepViews } from '@/staff/home/setupSteps'
import type { SetupStatus, SetupStep, WaitingRow } from '@/staff/home/types'

describe('timeAgo', () => {
  it.each([
    [5, 'just now'],
    [60, '1 minute ago'],
    [125, '2 minutes ago'],
    [3600, '1 hour ago'],
    [3 * 3600 + 10, '3 hours ago'],
    [86_400, 'yesterday'],
    [5 * 86_400, '5 days ago'],
  ])('%i seconds is "%s"', (seconds, text) => {
    expect(timeAgo(seconds)).toBe(text)
  })
})

describe('shortDate', () => {
  const now = new Date('2026-10-26T12:00:00Z')
  it('leaves out this year and keeps others', () => {
    expect(shortDate('2026-11-05', 'en-GB', now)).toBe('5 Nov')
    expect(shortDate('2029-10-24', 'en-GB', now)).toBe('24 Oct 2029')
  })
})

const step = (
  key: SetupStep['key'],
  done: boolean,
  facts: Record<string, unknown> = {},
  required = true,
) => ({
  key,
  done,
  can_fix: true,
  required,
  facts,
})

describe('setup steps', () => {
  // Dates follow the page language; these expectations are in British English.
  beforeAll(() => (document.documentElement.lang = 'en-GB'))
  afterAll(() => (document.documentElement.lang = ''))

  const status: SetupStatus = {
    complete: false,
    steps: [
      step('email', true, { email_id: 'sign@gulftrading.ae' }),
      step('seal', true, { kind: 'Self-signed', valid_to: '2029-10-24', expired: false }),
      step('profile', false, { profile: 'Gulf Trading LLC' }),
      step('documents', false, { doctypes: [] }, false),
      step('template', false, { count: 0 }),
      step('test', false),
    ],
  }

  it('numbers the steps and summarises the done ones', () => {
    const views = stepViews(status)
    expect(views.map((v) => v.number)).toEqual([1, 2, 3, 4, 5, 6])
    expect(views[0]!.summary).toBe('sign@gulftrading.ae')
    expect(views[1]!.summary).toMatch(/^Self-signed, valid until 24 Oct 2029$/)
    expect(views[2]!.summary).toBeNull()
  })

  it('links each step to where it is fixed', () => {
    const links = Object.fromEntries(stepViews(status).map((v) => [v.key, v.route ?? v.href]))
    expect(links).toEqual({
      email: '/app/email-account',
      seal: '/app/sign-certificate',
      profile: '/app/sign-profile/Gulf%20Trading%20LLC',
      documents: '/app/sign-settings',
      template: '/templates',
      test: '/new',
    })
  })

  it('shows an expired seal as a problem to fix', () => {
    const expired = {
      ...status,
      steps: [step('seal', false, { kind: 'Self-signed', valid_to: '2025-01-02', expired: true })],
    }
    const [seal] = stepViews(expired)
    expect(seal!.summary).toMatch(/^Expired on 2 Jan/)
    expect(seal!.action).toBe('Create a new seal')
  })

  it('opens the first required step to do, and counts what is left', () => {
    expect(firstOpenStep(status)).toBe('profile')
    expect(stepsLeft(status)).toBe(3)
    const onlyOptional = { ...status, steps: [step('email', true), step('documents', false, {}, false)] }
    expect(firstOpenStep(onlyOptional)).toBe('documents')
    expect(stepsLeft(onlyOptional)).toBe(0)
  })
})

const waiting = (next: WaitingRow['next'], people: WaitingRow['people'] = []): WaitingRow => ({
  name: 'SIGN-1',
  title: 'Quotation for Desert Peak Contracting',
  group: 'outside',
  next,
  people,
  signed: 0,
  total: people.length,
  sent_seconds: 0,
  expires_on: '2026-11-05',
  expiring_soon: false,
})

describe('Home lines', () => {
  it('says who asked and how long ago', () => {
    const row = { name: 'S', title: 'T', sender_name: 'Ahmed Khan', expires_on: null, age_seconds: 7200 }
    expect(askedLine({ ...row, kind: 'Signer' })).toBe('Ahmed Khan asked you to sign, 2 hours ago')
    expect(askedLine({ ...row, kind: 'Approver' })).toBe('Ahmed Khan asked you to approve, 2 hours ago')
  })

  it('names who is next', () => {
    const omar = { full_name: 'Omar Farouk', status: 'Viewed', viewed_seconds: 10_800 }
    const khalid = { full_name: 'Khalid Nasser', status: 'Sent', viewed_seconds: null }
    const sara = { full_name: 'Sara Idris', status: 'Sent', viewed_seconds: null }
    expect(nextLine(waiting([omar]))).toBe('Next: Omar Farouk, opened it 3 hours ago')
    expect(nextLine(waiting([khalid]))).toBe('Next: Khalid Nasser, not opened yet')
    expect(nextLine(waiting([sara, khalid]))).toBe('Next: Sara Idris and Khalid Nasser, at the same time')
    expect(nextLine(waiting([sara, khalid, omar]))).toBe(
      'Next: Sara Idris, Khalid Nasser and 1 more, at the same time',
    )
    expect(nextLine(waiting([]))).toBe('Everyone has signed. Sealing the PDF.')
  })

  it('names who has not signed', () => {
    const person = (full_name: string, status: string) => ({ full_name, status, kind: 'Signer', next: false })
    expect(notSignedYet(waiting([], [person('Rania Saleh', 'Signed'), person('Fatima Ali', 'Sent')]))).toBe(
      'Fatima Ali has not signed.',
    )
    expect(notSignedYet(waiting([], [person('A', 'Sent'), person('B', 'Pending')]))).toBe(
      'A, B have not signed.',
    )
  })
})

// Words and links for the "Set up signing" steps (UX_PLAN "Home"). The server says what is done;
// this file says it to the user. The seal, profile and documents steps open Settings; email is an
// Email Account, which only Desk edits.
import type { RouteDestination } from 'frappe-ui'
import { __ } from '@/shared/translate'
import { shortDate } from '../format'
import type { SetupKey, SetupStatus, SetupStep } from './types'

export interface StepView {
  key: SetupKey
  number: number
  title: string
  done: boolean
  optional: boolean
  canFix: boolean
  // One line under a done step, or the problem with a step that was set up and broke.
  summary: string | null
  text: string
  action: string
  route?: RouteDestination
  href?: string
}

const str = (value: unknown): string => (typeof value === 'string' ? value : '')

function sealSummary(facts: Record<string, unknown>): string | null {
  const validTo = str(facts.valid_to)
  if (facts.expired) return __('Expired on {0}', [shortDate(validTo)])
  if (!facts.kind) return null
  return validTo ? __('{0}, valid until {1}', [__(str(facts.kind)), shortDate(validTo)]) : __(str(facts.kind))
}

function view(step: SetupStep): Omit<StepView, 'number' | 'done' | 'optional' | 'canFix'> {
  const facts = step.facts
  switch (step.key) {
    case 'email':
      return {
        key: 'email',
        title: __('Email account'),
        summary: str(facts.email_id) || null,
        text: __('Invitations and signed copies go out from an outgoing email account.'),
        action: __('Set up email'),
        href: '/app/email-account',
      }
    case 'seal':
      return {
        key: 'seal',
        title: __('Company seal'),
        summary: sealSummary(facts),
        text: __(
          'The seal proves the signed PDF was not changed after signing. A test seal is fine to start.',
        ),
        action: facts.expired ? __('Create a new seal') : __('Create a seal'),
        route: '/settings',
      }
    case 'profile': {
      const profile = str(facts.profile)
      return {
        key: 'profile',
        title: __('Company profile'),
        summary: profile || null,
        text: __('Your logo and color appear on the signing page and in emails.'),
        action: __('Edit profile'),
        route: '/settings',
      }
    }
    case 'documents':
      return {
        key: 'documents',
        title: __('Documents you sign'),
        summary: Array.isArray(facts.doctypes) ? facts.doctypes.map((d) => __(String(d))).join(', ') : null,
        text: __(
          'Choose which ERPNext documents can be sent for signature. Most teams start with Quotation.',
        ),
        action: __('Choose documents'),
        route: { path: '/settings', query: { tab: 'documents' } },
      }
    case 'template':
      return {
        key: 'template',
        title: __('First template'),
        summary: Number(facts.count) === 1 ? __('1 published') : __('{0} published', [Number(facts.count)]),
        text: __('A template says who signs and where. Start from a Print Format, or upload your own PDF.'),
        action: __('New template'),
        route: '/templates',
      }
    case 'test':
      return {
        key: 'test',
        title: __('Send a test'),
        summary: __('Sent'),
        text: __('Send a request to yourself and sign it on your phone. It takes two minutes.'),
        action: __('Send a test'),
        route: '/new',
      }
  }
}

export function stepViews(status: SetupStatus): StepView[] {
  return status.steps.map((step, index) => {
    const base = view(step)
    return {
      ...base,
      number: index + 1,
      done: step.done,
      optional: !step.required,
      canFix: step.can_fix,
      // An expired seal shows its problem even though the step is to do.
      summary: step.done || (step.key === 'seal' && step.facts.expired) ? base.summary : null,
    }
  })
}

// The step to open first: the first required one still to do, else the first optional one.
export function firstOpenStep(status: SetupStatus): SetupKey | null {
  const open = status.steps.filter((step) => !step.done)
  return (open.find((step) => step.required) ?? open[0])?.key ?? null
}

export function stepsLeft(status: SetupStatus): number {
  return status.steps.filter((step) => step.required && !step.done).length
}

// UI words for stored values (UX_PLAN "Words"). The DocType values stay as they are (D13); only
// what the user reads changes. An unknown value shows as it is, translated.
import { __ } from '@/shared/translate'

export type BadgeTheme = 'gray' | 'blue' | 'green' | 'amber' | 'red'

export interface StatusView {
  label: string
  theme: BadgeTheme
}

const STATUS: Record<string, StatusView> = {
  Draft: { label: 'Draft', theme: 'gray' },
  Sent: { label: 'Waiting', theme: 'blue' },
  'In Progress': { label: 'Waiting', theme: 'blue' },
  Completed: { label: 'Completed', theme: 'green' },
  Declined: { label: 'Declined', theme: 'red' },
  Voided: { label: 'Voided', theme: 'gray' },
  Expired: { label: 'Expired', theme: 'amber' },
}

// Sealing states that mean the seal job has not finished yet.
const SEALING_BUSY = new Set(['Queued', 'Sealing'])

export function requestStatus(status: string, sealing?: string, sending?: string): StatusView {
  let view = STATUS[status] ?? { label: status, theme: 'gray' }
  if (sending === 'Failed') view = { label: 'Send failed', theme: 'red' }
  else if (status === 'Draft' && sending === 'Queued') view = { label: 'Sending', theme: 'blue' }
  else if (sealing === 'Failed') view = { label: 'Seal failed', theme: 'red' }
  else if (status === 'In Progress' && sealing && SEALING_BUSY.has(sealing))
    view = { label: 'Sealing', theme: 'blue' }
  return { label: __(view.label), theme: view.theme }
}

const ROLE_KIND: Record<string, string> = {
  Signer: 'Signs',
  Approver: 'Approves',
  CC: 'Gets a copy',
}

const SIGNER_SOURCE: Record<string, string> = {
  'Ask at Send': 'Chosen when sending',
  'Fixed User': 'A specific person',
  'Doc Field': 'A person named in a field of the document',
  'Party Contact': 'The customer or supplier on the document',
  Employee: 'The employee on the document',
}

const SIGNING_ORDER: Record<string, string> = {
  Sequential: 'Sign in this order',
  Parallel: 'All at once',
}

const OTP_MODE: Record<string, string> = { Email: 'Emailed code', WhatsApp: 'WhatsApp code', Off: 'Off' }

export const roleKindLabel = (kind: string): string => __(ROLE_KIND[kind] ?? kind)
export const signerSourceLabel = (source: string): string => __(SIGNER_SOURCE[source] ?? source)
export const signingOrderLabel = (order: string): string => __(SIGNING_ORDER[order] ?? order)
export const otpModeLabel = (mode: string): string => __(OTP_MODE[mode] ?? mode)

// Verification choices; WhatsApp only appears when the site can send it (P3.1).
export const otpModeOptions = (whatsapp: boolean): Array<{ label: string; value: string }> =>
  (whatsapp ? ['Off', 'Email', 'WhatsApp'] : ['Off', 'Email']).map((value) => ({
    label: otpModeLabel(value),
    value,
  }))

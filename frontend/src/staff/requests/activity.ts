// The audit events of a request as plain sentences (UX_PLAN "Request detail"). Routine steps (code
// sent, consent, fields filled, downloads) stay behind "Show audit details".
import { __ } from '@/shared/translate'
import { timeAgo } from '../format'

export interface ActivityEvent {
  seq: number
  event: string
  at: string
  actor: string | null
  ip: string | null
  recipient_row?: string | null
  ago_seconds: number
}

export interface ActivityLine {
  seq: number
  text: string
  ago: string
}

const KEY_EVENTS = new Set([
  'Created',
  'Sent',
  'Viewed',
  'Signed',
  'Declined',
  'Delegated',
  'Reminded',
  'Voided',
  'Expired',
  'Sealed',
  'Completed',
  'Post-Sign Action',
  'Source Changed',
])

function sentence(event: string, who: string | null): string {
  const name = who ?? __('Someone')
  switch (event) {
    case 'Created':
      return __('The request was created')
    case 'Sent':
      return __('The request was sent')
    case 'Viewed':
      return __('{0} opened the document', [name])
    case 'Signed':
      return __('{0} signed', [name])
    case 'Declined':
      return __('{0} declined', [name])
    case 'Delegated':
      return __('{0} passed it to someone else', [name])
    case 'Reminded':
      return who ? __('A reminder was sent to {0}', [who]) : __('A reminder was sent')
    case 'Voided':
      return __('The request was voided')
    case 'Expired':
      return __('The request expired')
    case 'Sealed':
      return __('The signed PDF was sealed')
    case 'Completed':
      return __('Everyone signed')
    case 'Post-Sign Action':
      return __('The follow-up action ran')
    default:
      return __('The source document changed')
  }
}

// Newest first. `people` maps recipient rows to names.
export function activityLines(
  events: ActivityEvent[],
  people: Array<{ name: string; full_name: string }>,
): ActivityLine[] {
  const names = new Map(people.map((person) => [person.name, person.full_name]))
  return events
    .filter((event) => KEY_EVENTS.has(event.event))
    .map((event) => ({
      seq: event.seq,
      text: sentence(event.event, event.recipient_row ? (names.get(event.recipient_row) ?? null) : null),
      ago: timeAgo(event.ago_seconds),
    }))
    .sort((a, b) => b.seq - a.seq)
}

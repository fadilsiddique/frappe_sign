// One-line descriptions of Sent rows. Open requests say who is next; the others say how they ended.
import { __ } from '@/shared/translate'
import { nextLine } from '../home/lines'
import type { RequestRow } from './types'

export function requestLine(row: RequestRow): string {
  switch (row.group) {
    case 'draft':
      return row.total ? __('Draft, not sent yet') : __('Draft, people not chosen yet')
    case 'done':
      return __('Everyone signed')
    case 'closed':
      if (row.status === 'Declined') return __('Someone declined')
      if (row.status === 'Voided') return __('Voided by the sender')
      return __('Nobody finished before it expired')
    default:
      return nextLine(row)
  }
}

export const GROUPS: Array<{ key: RequestRow['group']; label: string }> = [
  { key: 'outside', label: 'Waiting on customers and suppliers' },
  { key: 'team', label: 'Waiting on your team' },
  { key: 'draft', label: 'Drafts' },
  { key: 'done', label: 'Completed' },
  { key: 'closed', label: 'Closed' },
]

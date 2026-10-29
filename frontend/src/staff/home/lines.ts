// One-line descriptions of Home rows.
import { __ } from '@/shared/translate'
import { timeAgo } from '../format'
import type { ToSignRow, WaitingRow } from './types'

export function askedLine(row: ToSignRow): string {
  const when = timeAgo(row.age_seconds)
  return row.kind === 'Approver'
    ? __('{0} asked you to approve, {1}', [row.sender_name, when])
    : __('{0} asked you to sign, {1}', [row.sender_name, when])
}

export function nextLine(row: Pick<WaitingRow, 'next'>): string {
  const [first, second, ...rest] = row.next
  if (!first) return __('Everyone has signed. Sealing the PDF.')
  if (!second) {
    if (first.status === 'Viewed' && first.viewed_seconds !== null)
      return __('Next: {0}, opened it {1}', [first.full_name, timeAgo(first.viewed_seconds)])
    return __('Next: {0}, not opened yet', [first.full_name])
  }
  if (!rest.length) return __('Next: {0} and {1}, at the same time', [first.full_name, second.full_name])
  return __('Next: {0}, {1} and {2} more, at the same time', [first.full_name, second.full_name, rest.length])
}

export function notSignedYet(row: WaitingRow): string {
  const names = row.people.filter((person) => person.status !== 'Signed').map((person) => person.full_name)
  if (names.length === 1) return __('{0} has not signed.', [names[0]!])
  return __('{0} have not signed.', [names.join(', ')])
}

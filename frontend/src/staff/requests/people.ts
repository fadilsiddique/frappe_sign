// The people of one request as the step list shows them: who is next, and what each one is doing.
import { __ } from '@/shared/translate'
import { shortDate } from '../format'

export interface Person {
  name: string
  role_label: string
  kind: string
  routing_order?: number | null
  full_name: string
  email: string
  status: string
  signed_on: string | null
  viewed_on: string | null
  decline_reason: string | null
}

const FINISHED = new Set(['Signed', 'Declined', 'Delegated'])
const WAITING = new Set(['Sent', 'Viewed'])

// The names of the people whose turn it is. Same rule as the server (is_turn): in a signing order
// it is the lowest routing order that has not finished; all at once, everyone who has not finished.
export function nextPeople(people: Person[], order: string | null): Set<string> {
  const signing = people.filter((person) => person.kind !== 'CC' && !FINISHED.has(person.status))
  const turn = Math.min(...signing.map((person) => Number(person.routing_order ?? 0)))
  return new Set(
    signing
      .filter((person) => WAITING.has(person.status))
      .filter((person) => order === 'Parallel' || Number(person.routing_order ?? 0) === turn)
      .map((person) => person.name),
  )
}

export function personState(person: Person, requestStatus: string): string {
  if (person.status === 'Signed')
    return person.signed_on ? __('Signed {0}', [shortDate(person.signed_on.slice(0, 10))]) : __('Signed')
  if (person.status === 'Declined')
    return person.decline_reason ? __('Declined: {0}', [person.decline_reason]) : __('Declined')
  if (person.status === 'Delegated') return __('Passed to someone else')
  if (person.status === 'Viewed') return __('Opened, not signed yet')
  if (person.status === 'Sent') return __('Not opened yet')
  return requestStatus === 'Draft' ? __('Not sent yet') : __('Waits for the people before')
}

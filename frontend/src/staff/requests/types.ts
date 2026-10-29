// Shapes of frappe_sign.api.staff.list_requests, request_counts and request_filter_options
// (services/requests.py).
import type { WaitingRow } from '../home/types'

export type Tab = 'open' | 'completed' | 'closed' | 'all'

export interface RequestRow extends Omit<WaitingRow, 'group' | 'sent_seconds'> {
  group: 'outside' | 'team' | 'draft' | 'done' | 'closed'
  sent_seconds: number | null
  status: string
  send_state: string | null
  sealing_state: string | null
  reference_doctype: string | null
  reference_name: string | null
  sender: string | null
  sender_name: string
}

export interface RequestFilters {
  search: string
  reference_doctype: string
  sender: string
  date_from: string
  date_to: string
}

export type RequestCounts = Record<Tab, number>

export interface FilterOptions {
  doctypes: string[]
  senders: Array<{ name: string; full_name: string }>
}

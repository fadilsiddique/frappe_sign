// Shapes of frappe_sign.api.staff.get_dashboard and get_setup_status (services/home.py, setup.py).

export interface ToSignRow {
  name: string
  title: string
  sender_name: string
  kind: 'Signer' | 'Approver'
  age_seconds: number
  expires_on: string | null
}

export interface WaitingPerson {
  name: string
  full_name: string
  kind: string
  status: string
  next: boolean
}

export interface WaitingRow {
  name: string
  title: string
  group: 'outside' | 'team'
  next: Array<{ full_name: string; status: string; viewed_seconds: number | null }>
  people: WaitingPerson[]
  signed: number
  total: number
  sent_seconds: number
  expires_on: string | null
  expiring_soon: boolean
}

export interface Dashboard {
  to_sign: ToSignRow[]
  waiting: WaitingRow[]
  month: { completed: number; waiting: number; declined: number }
}

export type SetupKey = 'email' | 'seal' | 'profile' | 'documents' | 'template' | 'test'

export interface SetupStep {
  key: SetupKey
  done: boolean
  can_fix: boolean
  required: boolean
  facts: Record<string, unknown>
}

export interface SetupStatus {
  steps: SetupStep[]
  complete: boolean
}

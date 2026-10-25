import type { PageMetric, Rect } from '@/shared/coords'

export type FieldType =
  | 'Signature'
  | 'Initials'
  | 'Full Name'
  | 'Email'
  | 'Date Signed'
  | 'Text'
  | 'Number'
  | 'Checkbox'
  | 'Dropdown'
  | 'Company Stamp'
  | 'Attachment'

export interface GuestField {
  key: string
  type: FieldType
  page: number
  rect: Rect
  required: boolean
  read_only: boolean
  value: string | null
  filled: boolean
  options: string[]
  font_size: number
}

export interface Summary {
  envelope: {
    title: string
    message: string | null
    sender_name: string
    company: string | null
    status: string
    expires_on: string | null
  }
  recipient: {
    full_name: string
    email: string
    role_label: string
    kind: 'Signer' | 'Approver' | 'CC'
    status: string
    can_delegate: boolean
  }
  otp_mode: 'Off' | 'Email' | 'WhatsApp'
  otp_required?: boolean
  session?: string
  consent: { text: string; version: number; given: boolean }
  pages: PageMetric[]
  fields: GuestField[]
}

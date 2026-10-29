// The shapes frappe_sign.api.staff.get_settings returns (services/settings_page.py).
export interface SealDetails {
  kind: string | null
  valid_to: string | null
  expired: boolean
}

export interface SenderStatus {
  status: 'connected' | 'default' | 'missing'
  email_id: string | null
}

export interface ProfileCard {
  company: string
  logo: string | null
  brand_color: string | null
  legal_footer: string | null
  sender_email_account: string | null
  authorised_signatory: string | null
  seal: SealDetails
  sender: SenderStatus
}

export interface DocumentRow {
  doctype: string
  default_template: string | null
  templates: Array<{ name: string; title: string }>
  sends: number
}

export interface SigningSettings {
  default_expiry_days: number
  default_reminder_days: number
  otp_validity_minutes: number
  consent_text: string | null
}

export interface AdvancedSettings {
  tsa_urls: string | null
  max_upload_mb: number
  max_pages: number
}

export interface SettingsData {
  can_edit: boolean
  has_erpnext: boolean
  profiles: ProfileCard[]
  companies: string[]
  email_accounts: Array<{ name: string; email_id: string }>
  signatories: Array<{ name: string; full_name: string }>
  documents: DocumentRow[]
  signing: SigningSettings
  advanced: AdvancedSettings
}

export type SettingsTab = 'company' | 'documents' | 'signing' | 'advanced'
export const SETTINGS_TABS: Array<{ key: SettingsTab; label: string }> = [
  { key: 'company', label: 'Company' },
  { key: 'documents', label: 'Documents' },
  { key: 'signing', label: 'Signing' },
  { key: 'advanced', label: 'Advanced' },
]

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

export type SettingsTab = 'company' | 'documents' | 'signing' | 'advanced' | 'health'
export const SETTINGS_TABS: Array<{ key: SettingsTab; label: string }> = [
  { key: 'company', label: 'Company' },
  { key: 'documents', label: 'Documents' },
  { key: 'signing', label: 'Signing' },
  { key: 'advanced', label: 'Advanced' },
  { key: 'health', label: 'Health' },
]

// The report frappe_sign.api.staff.get_health returns (services/health.py).
export type HealthStatus = 'ok' | 'info' | 'warn' | 'fail'

export interface HealthCheck {
  key: string
  title: string
  status: HealthStatus
  detail: string
  hint: string
}

export interface HealthReport {
  status: HealthStatus
  checked_on: string
  checks: HealthCheck[]
}

// Status as an icon and a word, never colour alone (the word is the accessible name).
export const HEALTH_ICON: Record<HealthStatus, { icon: string; color: string; label: string }> = {
  ok: { icon: 'lucide-circle-check', color: 'text-ink-green-3', label: 'Fine' },
  info: { icon: 'lucide-info', color: 'text-ink-gray-6', label: 'For your information' },
  warn: { icon: 'lucide-triangle-alert', color: 'text-ink-amber-3', label: 'Needs a look' },
  fail: { icon: 'lucide-circle-x', color: 'text-ink-red-4', label: 'Needs fixing' },
}

// Shapes the send wizard shares: the roles to fill, the templates, the preview of a rendered document.
import type { PageMetric } from '@/shared/coords'
import type { PreviewAnchor } from '../components/AnchorPreview.vue'

export type Step = 'source' | 'recipients' | 'fields' | 'preview' | 'review'
export type Mode = 'template' | 'upload' | 'document'
export type Choice = 'document' | 'template' | 'upload'

export interface Recipient {
  role_label: string
  kind: string
  routing_order: number
  full_name: string
  email: string
  mobile?: string | null
  party_type?: string | null
  party?: string | null
  contact?: string | null
  resolved?: boolean
}

export interface DocumentTemplate {
  name: string
  title: string
  print_format: string | null
  letter_head: string | null
}

export interface TemplateRow {
  name: string
  title: string
  published_version: string
  source_type: string
  reference_doctype: string | null
  pdf_file: string | null
}

export interface Preview {
  key: string
  generator: string
  generator_tested: boolean
  metrics: PageMetric[]
  anchors: PreviewAnchor[]
}

export interface Prefill {
  field_key: string
  role_label: string
  field_type: string
  read_only: number
  value: string
}

export interface DocumentChoice {
  name: string
  party: string
  date: string
  total: number | null
  currency: string
}

export interface Person {
  full_name: string
  email: string
  source: string
}

// What the first step has picked so far.
export interface SourcePick {
  choice: Choice
  doctype: string
  name: string
  template: string
}

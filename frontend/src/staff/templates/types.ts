export interface TemplateCardRow {
  name: string
  title: string
  source_type: string
  reference_doctype: string | null
  print_format: string | null
  pdf_file: string | null
  published_version: string | null
  is_active: number
  modified: string
  last_used: string | null
  last_used_seconds: number | null
}

export interface PersonRow {
  role_label: string
  kind: string
  signer_source: string
  source_field: string
  fixed_user: string
}

export interface PrintFormatChoice {
  name: string
  has_sign_fields: boolean
}

export interface SettableField {
  fieldname: string
  label: string
}

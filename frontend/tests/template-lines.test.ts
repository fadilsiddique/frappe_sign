import { describe, expect, it } from 'vitest'
import { editRoute, lastUsedLine, typeLine } from '@/staff/templates/lines'
import type { TemplateCardRow } from '@/staff/templates/types'

const row = (patch: Partial<TemplateCardRow>): TemplateCardRow => ({
  name: 'STPL-00001',
  title: 'Quotation',
  source_type: 'Print Format',
  reference_doctype: 'Quotation',
  print_format: 'Quotation Sign',
  pdf_file: null,
  published_version: null,
  is_active: 1,
  modified: '2026-10-29 10:00:00',
  last_used: null,
  last_used_seconds: null,
  ...patch,
})

describe('template cards', () => {
  it('opens the form for a Print Format template and the designer for an own PDF', () => {
    expect(editRoute(row({}))).toBe('/templates/STPL-00001/edit')
    expect(editRoute(row({ source_type: 'Uploaded PDF' }))).toBe('/templates/STPL-00001/design')
  })

  it('names the type', () => {
    expect(typeLine(row({}))).toBe('Quotation · Print Format')
    expect(typeLine(row({ source_type: 'Uploaded PDF', reference_doctype: null }))).toBe('Own PDF')
  })

  it('says when it was last used', () => {
    expect(lastUsedLine(row({}))).toBe('Not used yet')
    expect(lastUsedLine(row({ last_used_seconds: 7200 }))).toBe('Used 2 hours ago')
  })
})

// Words and links for a template card.
import { __ } from '@/shared/translate'
import { timeAgo } from '../format'
import type { TemplateCardRow } from './types'

export const isPrintFormat = (row: TemplateCardRow): boolean => row.source_type === 'Print Format'

// A Print Format template opens its form; an own-PDF template opens the designer.
export const editRoute = (row: TemplateCardRow): string =>
  isPrintFormat(row) ? `/templates/${row.name}/edit` : `/templates/${row.name}/design`

export function typeLine(row: TemplateCardRow): string {
  const kind = isPrintFormat(row) ? __('Print Format') : __('Own PDF')
  return row.reference_doctype ? `${__(row.reference_doctype)} · ${kind}` : kind
}

export function lastUsedLine(row: TemplateCardRow): string {
  if (row.last_used_seconds === null) return __('Not used yet')
  return __('Used {0}', [timeAgo(Math.max(0, row.last_used_seconds))])
}

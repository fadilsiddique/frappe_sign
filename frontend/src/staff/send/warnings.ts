// What to check before sending a document: roles and field boxes that do not match.
import { __ } from '@/shared/translate'
import type { PreviewAnchor } from '../components/AnchorPreview.vue'
import type { Recipient } from './types'

// Anchor roles are role labels with spaces as underscores (pdf/anchors.py role_token).
export function roleToken(label: string): string {
  return label.trim().split(/\s+/).join('_')
}

export function checkWarnings(anchors: PreviewAnchor[], recipients: Recipient[]): string[] {
  const signers = recipients.filter((person) => person.kind === 'Signer')
  const tokens = new Set(signers.map((person) => roleToken(person.role_label)))
  const warnings: string[] = []
  if (!anchors.length) return [__("No signature field found. The template's own fields are used.")]
  for (const role of new Set(anchors.map((anchor) => anchor.role)))
    if (!tokens.has(role)) warnings.push(__('No signer has the role {0}, so its fields stay empty.', [role]))
  for (const person of signers)
    if (!anchors.some((anchor) => anchor.role === roleToken(person.role_label)))
      warnings.push(__('{0} has no field to fill on this document.', [person.role_label]))
  return warnings
}

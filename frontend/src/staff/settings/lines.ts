// Words for the Settings page.
import { __ } from '@/shared/translate'
import { shortDate } from '../format'
import type { SealDetails, SenderStatus } from './types'

export type Tone = 'ok' | 'warn' | 'bad'

export function sealLine(seal: SealDetails): { text: string; tone: Tone } {
  if (!seal.kind) return { text: __('Missing: documents cannot be sealed'), tone: 'bad' }
  const until = seal.valid_to ? shortDate(seal.valid_to) : ''
  if (seal.expired) return { text: __('Expired on {0}', [until]), tone: 'bad' }
  const kind = __(seal.kind)
  return { text: until ? __('{0}, valid until {1}', [kind, until]) : kind, tone: 'ok' }
}

export function senderLine(sender: SenderStatus): { text: string; tone: Tone } {
  if (sender.status === 'connected')
    return { text: __('Connected: {0}', [sender.email_id ?? '']), tone: 'ok' }
  if (sender.status === 'default') {
    return { text: __('Using the site email account: {0}', [sender.email_id ?? '']), tone: 'ok' }
  }
  return { text: __('Missing: add an outgoing email account'), tone: 'bad' }
}

// The icon carries the color; the words stay dark gray so they pass contrast.
export const toneClass: Record<Tone, string> = {
  ok: 'text-ink-green-3',
  warn: 'text-ink-amber-3',
  bad: 'text-ink-red-4',
}

export const toneIcon: Record<Tone, string> = {
  ok: 'lucide-circle-check',
  warn: 'lucide-triangle-alert',
  bad: 'lucide-circle-alert',
}

export function sendsLine(count: number): string {
  if (!count) return __('Not sent yet')
  return count === 1 ? __('1 request') : __('{0} requests', [count])
}

// The consent is stored as HTML (the signing page shows it as such). The editor is plain text:
// blank lines are paragraphs.
export function consentToText(html: string | null): string {
  if (!html) return ''
  const doc = new DOMParser().parseFromString(
    html.replace(/<\/p>\s*<p[^>]*>/gi, '\n\n').replace(/<br\s*\/?>/gi, '\n'),
    'text/html',
  )
  return (doc.body.textContent ?? '').trim()
}

const ESCAPES: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;' }

export function consentToHtml(text: string): string {
  return text
    .split(/\n{2,}/)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => `<p>${part.replace(/[&<>]/g, (ch) => ESCAPES[ch]!).replace(/\n/g, '<br>')}</p>`)
    .join('')
}

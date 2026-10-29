// Staff server calls. frappe-ui's call() sends the CSRF token from the boot data.
import { call } from 'frappe-ui'

export const STAFF_API = 'frappe_sign.api.staff.'

export function staff<T>(method: string, args: Record<string, unknown> = {}): Promise<T> {
  return call<T>(STAFF_API + method, args)
}

// Private files (template PDFs) for the logged-in user, as bytes for pdf.js.
export async function fetchPdf(url: string): Promise<ArrayBuffer> {
  const response = await fetch(url, { credentials: 'same-origin' })
  if (!response.ok) throw new Error(`Could not load ${url}`)
  return response.arrayBuffer()
}

export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

export function errorMessage(error: unknown): string {
  const messages = (error as { messages?: string[] })?.messages
  if (messages?.length) return messages.join(' ').replace(/<[^>]+>/g, '')
  return error instanceof Error ? error.message : String(error)
}

// A public image (company logo): the signing page and emails show it to people who are not logged in.
export async function uploadPublicImage(file: File): Promise<string> {
  const body = new FormData()
  body.append('file', file, file.name)
  body.append('is_private', '0')
  const csrf = window.csrf_token
  const response = await fetch('/api/method/upload_file', {
    method: 'POST',
    body,
    credentials: 'same-origin',
    headers: csrf && csrf !== 'None' ? { 'X-Frappe-CSRF-Token': csrf } : {},
  })
  const result = (await response.json()) as { message?: { file_url?: string }; _server_messages?: string }
  if (!response.ok || !result.message?.file_url) throw new Error(`Could not upload ${file.name}`)
  return result.message.file_url
}

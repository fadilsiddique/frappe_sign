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

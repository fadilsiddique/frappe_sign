// Client for the guest API (frappe_sign/api/guest.py). Adds the X-Sign-Session header and turns
// failures into SignApiError with the backend's stable `code`. Switch UI states on `code`, never
// on message text (CLAUDE.md).

export const GUEST_API = '/api/method/frappe_sign.api.guest.'
export const SESSION_HEADER = 'X-Sign-Session'

export class SignApiError extends Error {
  readonly code: string
  readonly status: number
  readonly data: Record<string, unknown>

  constructor(code: string, message: string, status: number, data: Record<string, unknown> = {}) {
    super(message)
    this.name = 'SignApiError'
    this.code = code
    this.status = status
    this.data = data
  }
}

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>

interface ErrorBody {
  code?: string
  data?: Record<string, unknown>
  exc_type?: string
  _server_messages?: string
}

function serverMessage(body: ErrorBody): string {
  try {
    const messages = JSON.parse(body._server_messages ?? '[]') as string[]
    const first = messages.length ? (JSON.parse(messages[0]) as { message?: string }) : null
    return first?.message?.replace(/<[^>]+>/g, '') ?? ''
  } catch {
    return ''
  }
}

function codeFor(status: number, body: ErrorBody): string {
  if (body.code) return body.code
  if (status === 429 || body.exc_type === 'RateLimitExceededError') return 'rate_limited'
  if (status === 0) return 'network_error'
  return 'server_error'
}

export class GuestClient {
  session: string | null = null
  private readonly fetchImpl: FetchLike

  constructor(fetchImpl: FetchLike = (input, init) => fetch(input, init)) {
    this.fetchImpl = fetchImpl
  }

  private headers(): Record<string, string> {
    const headers: Record<string, string> = {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    }
    if (this.session) headers[SESSION_HEADER] = this.session
    // A logged-in user opening their own signing link still needs Frappe's CSRF token.
    const csrf = typeof window !== 'undefined' ? window.csrf_token : undefined
    if (csrf && csrf !== 'None') headers['X-Frappe-CSRF-Token'] = csrf
    return headers
  }

  private async post(method: string, args: Record<string, unknown>): Promise<Response> {
    let response: Response
    try {
      response = await this.fetchImpl(GUEST_API + method, {
        method: 'POST',
        headers: this.headers(),
        body: JSON.stringify(args),
        credentials: 'same-origin',
      })
    } catch {
      throw new SignApiError('network_error', 'Network error', 0)
    }
    if (!response.ok) {
      const body = ((await response.json().catch(() => ({}))) ?? {}) as ErrorBody
      throw new SignApiError(codeFor(response.status, body), serverMessage(body), response.status, body.data)
    }
    return response
  }

  async call<T>(method: string, args: Record<string, unknown> = {}): Promise<T> {
    const response = await this.post(method, args)
    const body = (await response.json()) as { message: T }
    return body.message
  }

  async pdf(): Promise<ArrayBuffer> {
    const response = await this.post('get_pdf', {})
    return response.arrayBuffer()
  }
}

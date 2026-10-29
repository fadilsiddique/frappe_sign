import { describe, expect, it, vi } from 'vitest'
import { GUEST_API, GuestClient, SESSION_HEADER, SignApiError } from '@/shared/api'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('GuestClient', () => {
  it('sends the page language so server texts match it', async () => {
    window.frappe_sign = { lang: 'ar' }
    const fetchImpl = vi.fn().mockImplementation(async () => jsonResponse(200, { message: {} }))
    await new GuestClient(fetchImpl).call('open', { token: 't' })
    expect(JSON.parse(fetchImpl.mock.calls[0][1].body)).toEqual({ token: 't', _lang: 'ar' })
    delete window.frappe_sign
  })

  it('posts JSON and sends the session header once there is one', async () => {
    const fetchImpl = vi.fn().mockImplementation(async () => jsonResponse(200, { message: { ok: true } }))
    const client = new GuestClient(fetchImpl)
    await client.call('open', { token: 't' })
    expect(fetchImpl.mock.calls[0][0]).toBe(GUEST_API + 'open')
    expect(fetchImpl.mock.calls[0][1].headers[SESSION_HEADER]).toBeUndefined()
    client.session = 'secret'
    expect(await client.call('state')).toEqual({ ok: true })
    const init = fetchImpl.mock.calls[1][1]
    expect(init.method).toBe('POST')
    expect(init.headers[SESSION_HEADER]).toBe('secret')
    expect(init.credentials).toBe('same-origin')
  })

  it('turns failures into coded errors', async () => {
    const body = {
      code: 'not_your_turn',
      data: { waiting_for: ['Ahmed'] },
      _server_messages: JSON.stringify([JSON.stringify({ message: 'Waiting for <b>Ahmed</b>' })]),
    }
    const client = new GuestClient(vi.fn().mockResolvedValue(jsonResponse(409, body)))
    const error = await client.call('open').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(SignApiError)
    expect((error as SignApiError).code).toBe('not_your_turn')
    expect((error as SignApiError).data).toEqual({ waiting_for: ['Ahmed'] })
    expect((error as SignApiError).message).toBe('Waiting for Ahmed')
  })

  it('maps rate limits and network failures', async () => {
    const limited = new GuestClient(vi.fn().mockResolvedValue(jsonResponse(429, {})))
    expect(((await limited.call('open').catch((e) => e)) as SignApiError).code).toBe('rate_limited')
    const offline = new GuestClient(vi.fn().mockRejectedValue(new TypeError('offline')))
    expect(((await offline.call('open').catch((e) => e)) as SignApiError).code).toBe('network_error')
  })

  it('fetches the PDF as bytes', async () => {
    const bytes = new Uint8Array([37, 80, 68, 70])
    const client = new GuestClient(vi.fn().mockResolvedValue(new Response(bytes, { status: 200 })))
    expect(new Uint8Array(await client.pdf())).toEqual(bytes)
  })
})

// State of one signing visit: open the link, verify, consent, fill, finish (DESIGN 5.1, 7.3).
import { reactive } from 'vue'
import { GuestClient, SignApiError } from '@/shared/api'
import { __ } from '@/shared/translate'
import { terminalFor, type Screen } from './flow'
import type { GuestField, Summary } from './types'

const TERMINAL_CODES = new Set(['link_expired', 'not_your_turn', 'recipient_done', 'envelope_not_open'])

export interface FlowState {
  screen: Screen
  summary: Summary | null
  pdf: ArrayBuffer | null
  waitingFor: string[]
  busy: boolean
  error: string
  otpSentTo: string
  completed: boolean
}

export function useGuestFlow(token: string, client: GuestClient = new GuestClient()) {
  const state = reactive<FlowState>({
    screen: 'loading',
    summary: null,
    pdf: null,
    waitingFor: [],
    busy: false,
    error: '',
    otpSentTo: '',
    completed: false,
  })

  function showTerminal(error: unknown) {
    const terminal = terminalFor(error)
    state.screen = terminal.screen
    state.waitingFor = terminal.waitingFor ?? []
  }

  // Errors that end the visit switch screens; others show a message and keep the screen.
  async function handle(error: unknown): Promise<void> {
    if (error instanceof SignApiError && error.code === 'session_invalid') {
      client.session = null
      await start()
      return
    }
    if (error instanceof SignApiError && TERMINAL_CODES.has(error.code)) {
      showTerminal(error)
      return
    }
    if (error instanceof SignApiError && error.code === 'rate_limited') {
      state.error = __('Too many attempts. Wait a minute and try again.')
      return
    }
    state.error =
      error instanceof SignApiError && error.message ? error.message : __('Something went wrong. Try again.')
  }

  async function run<T>(work: () => Promise<T>): Promise<T | undefined> {
    state.busy = true
    state.error = ''
    try {
      return await work()
    } catch (error) {
      await handle(error)
      return undefined
    } finally {
      state.busy = false
    }
  }

  function apply(summary: Summary) {
    state.summary = summary
    if (summary.session) client.session = summary.session
  }

  async function start(): Promise<void> {
    state.screen = 'loading'
    try {
      const summary = await client.call<Summary>('open', { token })
      apply(summary)
      if (summary.otp_required) state.screen = 'verify'
      else await afterVerified()
    } catch (error) {
      if (error instanceof SignApiError && TERMINAL_CODES.has(error.code)) showTerminal(error)
      else {
        state.screen = 'error'
        state.error = error instanceof SignApiError ? error.message : ''
      }
    }
  }

  async function afterVerified() {
    if (state.summary?.consent.given) await enterSign()
    else state.screen = 'consent'
  }

  async function enterSign() {
    state.screen = 'sign'
    state.pdf = await client.pdf()
  }

  async function requestOtp() {
    const result = await run(() =>
      client.call<{ sent_to: string }>('request_otp', { token, channel: 'Email' }),
    )
    if (result) state.otpSentTo = result.sent_to
  }

  async function verifyOtp(code: string) {
    const summary = await run(() => client.call<Summary>('verify_otp', { token, code }))
    if (!summary) return
    apply(summary)
    await afterVerified()
  }

  async function acceptConsent() {
    const version = state.summary?.consent.version ?? 0
    const ok = await run(() => client.call('consent', { version }))
    if (ok === undefined || !state.summary) return
    state.summary.consent.given = true
    await enterSign()
  }

  function updateFields(fields: GuestField[]) {
    if (state.summary) state.summary.fields = fields
  }

  async function saveValue(key: string, value: string): Promise<boolean> {
    const result = await run(() =>
      client.call<{ fields: GuestField[] }>('save_fields', { values: { [key]: value } }),
    )
    if (result) updateFields(result.fields)
    return Boolean(result)
  }

  async function saveCapture(key: string, method: string, image: string, fileName = ''): Promise<boolean> {
    const result = await run(() =>
      client.call<{ fields: GuestField[] }>('save_capture', {
        field_key: key,
        method,
        image,
        file_name: fileName,
      }),
    )
    if (result) updateFields(result.fields)
    return Boolean(result)
  }

  async function finish() {
    const result = await run(() => client.call<{ status: string; completed: boolean }>('finish'))
    if (!result) return
    state.completed = result.completed
    state.screen = 'signed'
  }

  async function decline(reason: string) {
    const result = await run(() => client.call('decline', { reason }))
    if (result !== undefined) state.screen = 'declined'
  }

  async function delegate(fullName: string, email: string) {
    const result = await run(() => client.call('delegate', { full_name: fullName, email }))
    if (result !== undefined) state.screen = 'delegated'
  }

  return {
    state,
    start,
    requestOtp,
    verifyOtp,
    acceptConsent,
    saveValue,
    saveCapture,
    finish,
    decline,
    delegate,
  }
}

export type GuestFlow = ReturnType<typeof useGuestFlow>

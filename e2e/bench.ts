// Run frappe_sign.tests.e2e fixtures through `bench execute` (they commit and need allow_tests).
import { execFileSync } from 'node:child_process'
import { resolve } from 'node:path'

const BENCH = process.env.E2E_BENCH ?? resolve(__dirname, '../../..')
const SITE = process.env.E2E_SITE ?? 'sign.localhost'

export function benchExecute<T>(method: string, kwargs?: Record<string, unknown>): T {
  const args = ['--site', SITE, 'execute', `frappe_sign.tests.e2e.${method}`]
  if (kwargs) args.push('--kwargs', JSON.stringify(kwargs))
  const output = execFileSync('bench', args, { cwd: BENCH, encoding: 'utf8' })
  const last = output.trim().split('\n').filter(Boolean).pop() ?? 'null'
  return JSON.parse(last) as T
}

export interface GuestEnvelope {
  envelope: string
  token: string
  started: string
}

export interface EnvelopeState {
  status: string
  recipients: Record<string, string>
  fields: Record<string, boolean>
}

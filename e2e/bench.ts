// Run frappe_sign.tests.e2e fixtures through `bench execute` (they commit and need allow_tests).
import { execFileSync } from 'node:child_process'
import { resolve } from 'node:path'

const BENCH = process.env.E2E_BENCH ?? resolve(__dirname, '../../..')
const SITE = process.env.E2E_SITE ?? 'sign.localhost'

export function benchExecute<T>(method: string, kwargs?: Record<string, unknown>, attempts = 1): T {
  const args = ['--site', SITE, 'execute', `frappe_sign.tests.e2e.${method}`]
  if (kwargs) args.push('--kwargs', JSON.stringify(kwargs))
  for (let attempt = 1; ; attempt++) {
    try {
      const output = execFileSync('bench', args, { cwd: BENCH, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
      const last = output.trim().split('\n').filter(Boolean).pop() ?? 'null'
      return JSON.parse(last) as T
    } catch (error) {
      // A bench worker may still be running the render job for an envelope the test sent.
      if (attempt >= attempts) {
        const stderr = String((error as { stderr?: string }).stderr ?? '').slice(-2000)
        throw new Error(`${method} failed: ${stderr}`, { cause: error })
      }
      execFileSync('sleep', ['3'])
    }
  }
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

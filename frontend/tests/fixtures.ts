import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// Shared fixtures live with the Python tests. Vitest runs from frontend/ (yarn test).
export const FIXTURES_DIR = resolve(process.cwd(), '../frappe_sign/tests/fixtures')

export function readFixtureJson<T>(name: string): T {
  return JSON.parse(readFileSync(resolve(FIXTURES_DIR, name), 'utf8')) as T
}

// Copies the built HTML shells into frappe_sign/www/ so Frappe serves them at /sign and /s (DESIGN 7.1).
// The shells carry the Jinja boot block that www/sign.py and www/s.py fill.
import { copyFileSync, existsSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const outDir = resolve(frontend, '../frappe_sign/public/frontend')
const wwwDir = resolve(frontend, '../frappe_sign/www')

const SHELLS = { 'staff.html': 'sign.html', 'guest.html': 's.html' }

mkdirSync(wwwDir, { recursive: true })
for (const [built, page] of Object.entries(SHELLS)) {
  const source = resolve(outDir, built)
  if (!existsSync(source)) throw new Error(`Build output ${source} is missing; run vite build first.`)
  copyFileSync(source, resolve(wwwDir, page))
  console.log(`copied ${built} -> frappe_sign/www/${page}`)
}

// Fails when the guest app is over budget: 250 KB gzipped, JS and CSS, without the pdf.js worker (DESIGN 7.3).
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { gzipSync } from 'node:zlib'

const BUDGET_BYTES = 250 * 1024
const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const outDir = resolve(frontend, '../frappe_sign/public/frontend')
const manifest = JSON.parse(readFileSync(resolve(outDir, '.vite/manifest.json'), 'utf8'))

// Every file the guest entry loads: its chunk, static imports and their CSS. Dynamic imports load
// later, so they do not count towards first load, and the pdf.js worker is excluded by name.
function collect(key, files = new Set(), seen = new Set()) {
  if (seen.has(key)) return files
  seen.add(key)
  const chunk = manifest[key]
  files.add(chunk.file)
  for (const css of chunk.css ?? []) files.add(css)
  for (const imported of chunk.imports ?? []) collect(imported, files, seen)
  return files
}

const files = [...collect('guest.html')].filter((file) => !/pdf\.worker/.test(file))
const total = files.reduce((sum, file) => sum + gzipSync(readFileSync(resolve(outDir, file))).length, 0)
const kb = (bytes) => `${(bytes / 1024).toFixed(1)} KB`

console.log(`guest bundle: ${kb(total)} gzipped (budget ${kb(BUDGET_BYTES)}), ${files.length} files`)
if (total > BUDGET_BYTES) {
  console.error('guest bundle is over budget')
  process.exit(1)
}

// P3.5: every staff screen and every email in Arabic, right to left, for the user's review.
// Screenshots go to docs/ux/ar/. Administrator's language is set to Arabic for the run and
// restored afterwards.
import { expect, test, type Page } from '@playwright/test'
import { axeFindings } from './axe'
import { benchExecute } from './bench'

const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'admin'
const OUT = '../docs/ux/ar'

let started: string | undefined
let previous = ''
let requests: Record<string, string> = {}
let template = ''

test.beforeAll(() => {
  previous = benchExecute<{ previous: string }>('set_user_language', { user: 'Administrator', language: 'ar' }).previous
  requests = benchExecute<Record<string, string>>('create_sent_requests')
  started = requests.started
  template = benchExecute<{ template: string }>('create_arabic_template').template
})

test.afterAll(() => {
  benchExecute('set_user_language', { user: 'Administrator', language: previous })
  if (started) benchExecute('purge_created', { started }, 5)
})

async function login(page: Page) {
  const response = await page.request.post('/api/method/login', { data: { usr: 'Administrator', pwd: ADMIN_PASSWORD } })
  expect(response.ok()).toBeTruthy()
}

async function expectArabic(page: Page) {
  await page.waitForLoadState('networkidle')
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl')
  await expect(page.locator('html')).toHaveAttribute('lang', /^ar/)
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow).toBeLessThanOrEqual(0)
}

// Words that stay Latin on purpose: product and file names, the e2e data and identifiers.
const LATIN_OK = /E2E|Ahmed|Fatima|Layla|Administrator|Frappe|ERPNext|SIGN-|SHA|PDF|PKCS|AATL|CSC|SPF|DKIM|RFC|DocType|@|\.p12|https?:|wkhtml|Quotation|Service Agreement|Test Template|Lease|Supply|Draft Terms|Signed Order|Declined Offer|sign_field|Desk/

// Visible text lines with Latin words and no Arabic: a string that was never translated.
async function untranslated(page: Page): Promise<string[]> {
  const lines = await page.evaluate(() =>
    document.body.innerText.split('\n').map((line) => line.trim()).filter(Boolean),
  )
  return [...new Set(lines)].filter((line) => /[A-Za-z]{3,}/.test(line) && !/[\u0600-\u06FF]/.test(line) && !LATIN_OK.test(line) && !/^(Customer|Company)$/.test(line))
}

const SCREENS: [string, string, () => string][] = [
  ['01-home', '/sign', () => '/sign'],
  ['02-requests', '/sign/requests', () => '/sign/requests'],
  ['03-request-waiting', '', () => `/sign/requests/${requests.customer}`],
  ['04-request-done', '', () => `/sign/requests/${requests.done}`],
  ['05-request-declined', '', () => `/sign/requests/${requests.declined}`],
  ['06-send-wizard', '/sign/new', () => '/sign/new'],
  ['07-templates', '/sign/templates', () => '/sign/templates'],
  ['08-designer', '', () => `/sign/templates/${template}/design`],
  ['09-settings-company', '/sign/settings', () => '/sign/settings'],
]

for (const [name, , path] of SCREENS) {
  test(`${name} in Arabic`, async ({ page }) => {
    await login(page)
    await page.goto(path())
    await expectArabic(page)
    await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true })
    expect(await axeFindings(page)).toEqual([])
    expect(await untranslated(page)).toEqual([])
  })
}

test('the settings tabs in Arabic', async ({ page }) => {
  await login(page)
  await page.goto('/sign/settings')
  await expectArabic(page)
  const tabs = page.getByRole('tab')
  const count = await tabs.count()
  expect(count).toBeGreaterThan(1)
  for (let index = 1; index < count; index++) {
    await tabs.nth(index).click()
    await page.waitForLoadState('networkidle')
    await page.screenshot({ path: `${OUT}/10-settings-tab-${index + 1}.png`, fullPage: true })
    expect(await untranslated(page)).toEqual([])
  }
})

test('the public verify page and the portal page in Arabic', async ({ page }) => {
  await login(page)
  await page.goto('/sign-verify')
  await page.screenshot({ path: `${OUT}/11-verify.png`, fullPage: true })
  await page.goto('/my-signatures')
  await page.screenshot({ path: `${OUT}/12-portal-my-documents.png`, fullPage: true })
})

test('every email in Arabic', async ({ page }) => {
  const emails = benchExecute<Record<string, string>>('render_emails', { language: 'ar' })
  let index = 20
  for (const [name, html] of Object.entries(emails)) {
    await page.setContent(`<body style="margin:0">${html}</body>`)
    await page.screenshot({ path: `${OUT}/${index++}-email-${name}.png`, fullPage: true })
  }
})

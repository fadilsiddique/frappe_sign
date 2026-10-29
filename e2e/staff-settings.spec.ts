// U.9: Settings. A System Manager sets up the company, its seal, the documents and the defaults; a
// Sign Manager only looks.
import { resolve } from 'node:path'
import { expect, test, type Page } from '@playwright/test'
import { benchExecute } from './bench'

const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'admin'
const P12 = resolve(__dirname, '../frappe_sign/tests/fixtures/certs/sealing.p12')
const SHOTS = '../docs/ux/after'

interface Prepared {
  company: string
  started: string
  expiry: number
  user: string
  password: string
}
let prepared: Prepared | undefined

test.beforeAll(() => {
  prepared = benchExecute<Prepared>('prepare_settings')
})

test.afterAll(() => {
  if (prepared) benchExecute('purge_settings', { started: prepared.started, expiry: prepared.expiry }, 3)
})

async function login(page: Page, user: string, password: string) {
  const response = await page.request.post('/api/method/login', { data: { usr: user, pwd: password } })
  expect(response.ok()).toBeTruthy()
}

test('a System Manager sets up the company, the documents and the defaults', async ({ page }) => {
  const { company, expiry } = prepared!
  await login(page, 'Administrator', ADMIN_PASSWORD)

  // Company tab: add the company, make a test seal, then upload a real certificate over it.
  await page.goto('/sign/settings')
  await expect(page.getByTestId('empty-state')).toContainText('No company yet')
  await page.getByTestId('add-company').click()
  await page.getByTestId('new-company').click()
  await page.getByRole('option', { name: company }).click()
  await page.getByTestId('confirm-add-company').click()
  const card = page.getByTestId(`profile-${company}`)
  await expect(card).toBeVisible()
  await expect(card.getByTestId('seal-status')).toContainText('Missing')
  await expect(page.getByRole('navigation', { name: 'Main' }).getByTestId('nav-settings')).toBeVisible()

  await card.getByTestId('create-test-seal').click()
  await expect(card.getByTestId('seal-status')).toContainText('Self-signed, valid until')
  await expect(card.getByTestId('create-test-seal')).toHaveCount(0)

  await card.getByTestId('brand-color').fill('#112233')
  await card.getByTestId('save-profile').click()
  await expect(card.getByTestId('save-profile')).toBeDisabled()
  await page.reload()
  await expect(page.getByTestId(`profile-${company}`).getByTestId('brand-color')).toHaveValue('#112233')

  await page.getByTestId('open-seal-dialog').click()
  await page.getByTestId('seal-file').setInputFiles(P12)
  await page.getByTestId('seal-password').fill('wrong-password')
  await page.getByTestId('seal-upload').click()
  await expect(page.getByText('The password is wrong')).toBeVisible()
  await page.getByTestId('seal-password').fill('fixture-seal')
  await page.getByTestId('seal-upload').click()
  await expect(page.getByTestId('seal-status')).toContainText('CA-issued, valid until')
  await page.screenshot({ path: `${SHOTS}/u9-settings-company-1440.png` })

  // Documents tab.
  await page.getByTestId('settings-tab-documents').click()
  await expect(page).toHaveURL(/tab=documents/)
  await page.getByTestId('add-document').click()
  await page.getByTestId('doctype-search').fill('Note')
  await page.getByTestId('pick-Note').click()
  const row = page.getByTestId('document-Note')
  await expect(row).toContainText('Not sent yet')
  await page.screenshot({ path: `${SHOTS}/u9-settings-documents-1440.png` })
  page.once('dialog', (dialog) => dialog.accept())
  await row.getByTestId('remove-document').click()
  await expect(row).toHaveCount(0)

  // Signing tab: the value survives a reload.
  await page.getByTestId('settings-tab-signing').click()
  await page.getByTestId('expiry-days').fill(String(expiry + 7))
  await page.getByTestId('save-signing').click()
  await expect(page.getByTestId('save-signing')).toBeDisabled()
  await page.reload()
  await expect(page.getByTestId('expiry-days')).toHaveValue(String(expiry + 7))
  await page.screenshot({ path: `${SHOTS}/u9-settings-signing-1440.png` })

  await page.getByTestId('settings-tab-advanced').click()
  await expect(page.getByTestId('tsa-urls')).toBeVisible()

  // Phone width.
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByTestId('settings-tab-company').click()
  await expect(page.getByTestId(`profile-${company}`)).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: `${SHOTS}/u9-settings-company-390.png`, fullPage: true })
})

test('a Sign Manager sees the settings but cannot change them', async ({ page }) => {
  const { user, password } = prepared!
  await login(page, user, password)
  await page.goto('/sign/settings')
  await expect(page.getByTestId('read-only')).toBeVisible()
  await expect(page.getByTestId('add-company')).toHaveCount(0)
  await page.getByTestId('settings-tab-documents').click()
  await expect(page.getByTestId('add-document')).toHaveCount(0)
  await page.getByTestId('settings-tab-signing').click()
  await expect(page.getByTestId('expiry-days')).toBeDisabled()
  await expect(page.getByTestId('save-signing')).toHaveCount(0)

  // The API refuses too.
  const response = await page.request.post('/api/method/frappe_sign.api.staff.save_settings', {
    data: { section: 'signing', values: { default_expiry_days: 99 } },
    headers: { 'X-Frappe-CSRF-Token': await page.evaluate(() => window.csrf_token ?? '') },
  })
  expect(response.status()).toBe(403)
})

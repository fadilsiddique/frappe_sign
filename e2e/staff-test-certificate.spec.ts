// Sign Certificate: "Create test certificate" makes a self-signed certificate and the Sign Profile
// that uses it, so a trial site can seal without buying a certificate first.
import { expect, test } from '@playwright/test'
import { benchExecute } from './bench'

const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'admin'

interface Prepared {
  company: string
  started: string
}

let prepared: Prepared | undefined

test.beforeAll(() => {
  prepared = benchExecute<Prepared>('prepare_certificate')
})

test.afterAll(() => {
  if (prepared) benchExecute('purge_certificates', { started: prepared.started })
})

test('create a test certificate from the Sign Certificate list', async ({ page }) => {
  const { company } = prepared!
  const login = await page.request.post('/api/method/login', { data: { usr: 'Administrator', pwd: ADMIN_PASSWORD } })
  expect(login.ok()).toBeTruthy()

  await page.goto('/app/sign-certificate')
  await page.getByRole('button', { name: 'Create test certificate' }).click()
  const dialog = page.locator('.modal.show').filter({ hasText: 'Name on the certificate' })
  await expect(dialog).toBeVisible()

  await dialog.locator('input[data-fieldname="company"]').fill(company)
  await dialog.locator('input[data-fieldname="common_name"]').fill(company)
  await page.screenshot({ path: '../e2e/test-results/desk-test-certificate-dialog.png' })
  await dialog.getByRole('button', { name: 'Create' }).click()

  const message = page.locator('.modal.show').filter({ hasText: 'Certificate created' })
  await expect(message).toContainText(`Sign Profile ${company} was created with this certificate.`)
  // /app/... on v16.0.0, /desk/<module>/... on later v16 releases.
  await expect(page).toHaveURL(/\/sign-certificate\/SCERT-/)
  await page.screenshot({ path: '../e2e/test-results/desk-test-certificate-created.png' })
  await expect(message.getByRole('link', { name: company })).toBeVisible()
  await message.locator('.btn-modal-close').click()

  await expect(page.locator('select[data-fieldname="kind"]')).toHaveValue('Self-signed')
  await expect(page.locator('[data-fieldname="subject"]')).toContainText(`CN=${company}`)
})

// U.6: send a Quotation from the wizard without typing a DocType or a document number: the
// pickers, the people found on the document, the check step, the sticky footer and phones.
import { expect, test, type Page } from '@playwright/test'
import { benchExecute } from './bench'

const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'admin'

interface Prepared {
  quotation: string
  template: string
  started: string
}
let prepared: Prepared

test.beforeAll(() => {
  prepared = benchExecute<Prepared>('prepare_quotation')
})
test.afterAll(() => {
  if (prepared) benchExecute('purge_quotation', { started: prepared.started }, 5)
})

async function login(page: Page) {
  const response = await page.request.post('/api/method/login', { data: { usr: 'Administrator', pwd: ADMIN_PASSWORD } })
  expect(response.ok()).toBeTruthy()
}

test('send a Quotation by picking it, without typing a number', async ({ page }) => {
  await login(page)
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/sign/new')

  // Step 1: an ERPNext document is the first choice; Quotation is enabled.
  await expect(page.getByTestId('choice-document')).toHaveAttribute('aria-checked', 'true')
  await expect(page.getByTestId('doctype-select')).toBeVisible()
  await page.getByTestId('document-combobox').click()
  const option = page.getByRole('option').filter({ hasText: prepared.quotation })
  await expect(option).toContainText('Gulf Trading')
  await page.screenshot({ path: '../e2e/test-results/wizard-1-document.png' })
  await option.click()
  await expect(page.getByTestId('next')).toBeEnabled()
  await page.getByTestId('next').click()

  // Step 2: the customer is found on the document.
  await expect(page.getByTestId('found').first()).toBeVisible({ timeout: 30_000 })
  await expect(page.getByPlaceholder('Email').first()).toHaveValue('ahmed@gulftrading.example')
  await page.screenshot({ path: '../e2e/test-results/wizard-2-people.png' })
  await page.getByTestId('next').click()

  // Step 3: the check step labels the boxes and warns about roles nobody has.
  await expect(page.getByTestId('anchor-preview')).toBeVisible()
  await expect(page.getByTestId('anchor').first()).toBeVisible()
  await expect(page.getByTestId('warnings')).toContainText('No signer has the role')
  await page.screenshot({ path: '../e2e/test-results/wizard-3-check.png' })
  await page.getByTestId('next').click()

  // Step 4: the message sits behind a button; then Send.
  await expect(page.getByRole('textbox', { name: 'Message' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Add a message' }).click()
  await expect(page.getByRole('textbox', { name: 'Message' })).toBeVisible()
  await page.getByTestId('send').click()
  await expect(page.getByTestId('envelope-detail')).toBeVisible()
})

test('people suggestions fill the email, and Back returns to the document', async ({ page }) => {
  await login(page)
  await page.goto(`/sign/new?doctype=Quotation&name=${prepared.quotation}`)
  await expect(page.getByTestId('person-row').first()).toBeVisible({ timeout: 30_000 })
  const name = page.getByPlaceholder('Full name').first()
  await name.fill('Administrator')
  await page.getByRole('option').filter({ hasText: 'admin' }).first().click()
  await expect(page.getByPlaceholder('Email').first()).not.toHaveValue('ahmed@gulftrading.example')
  await page.getByRole('button', { name: 'Back' }).click()
  await expect(page.getByTestId('document-source')).toBeVisible()
})

test('on a phone the footer stays in view and nothing scrolls sideways', async ({ page }) => {
  await login(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/sign/new')
  await expect(page.getByTestId('wizard-footer')).toBeVisible()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow).toBeLessThanOrEqual(0)
  await page.screenshot({ path: '../e2e/test-results/wizard-390.png' })
})

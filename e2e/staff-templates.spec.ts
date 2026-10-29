// U.7: the Templates grid, and making and publishing a Quotation template in the staff app without Desk.
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

test('the grid shows cards and New template asks the kind first', async ({ page }) => {
  await login(page)
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/sign/templates')
  const card = page.getByTestId(`template-${prepared.template}`)
  await expect(card).toContainText('Quotation acceptance')
  await expect(card).toContainText('Quotation · Print Format')
  await expect(card).toContainText('Published')
  await page.screenshot({ path: '../e2e/test-results/templates-grid.png' })

  await page.getByTestId('new-template').click()
  await expect(page.getByTestId('kind-print-format')).toBeVisible()
  await expect(page.getByTestId('kind-pdf')).toBeVisible()
  await page.screenshot({ path: '../e2e/test-results/templates-kind.png' })
})

test('make and publish a Quotation template without Desk', async ({ page }) => {
  await login(page)
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/sign/templates/new/print-format')

  await expect(page.getByTestId('template-doctype')).toContainText('Quotation')
  await page.getByTestId('template-print-format').click()
  await page.getByRole('option').first().click()
  await expect(page.getByTestId('format-ok')).toBeVisible()

  await page.getByTestId('template-title').fill('E2E Quotation by hand')
  await page.getByTestId('after-choice').click()
  await page.getByRole('option', { name: 'Create a draft Sales Order' }).click()

  await page.getByTestId('document-combobox').click()
  await page.getByRole('option').filter({ hasText: prepared.quotation }).click()
  await page.getByTestId('draw-preview').click()
  await expect(page.getByTestId('anchor').first()).toBeVisible({ timeout: 30_000 })
  await page.screenshot({ path: '../e2e/test-results/templates-editor.png', fullPage: true })

  await page.getByTestId('publish-template').click()
  await expect(page.getByText(/Published version 1/)).toBeVisible()
  await expect(page).toHaveURL(/\/sign\/templates\/STPL-\d+\/edit/)

  // It is in the grid, published, and reopens with its choices.
  await page.goto('/sign/templates')
  const card = page.getByRole('link', { name: /E2E Quotation by hand/ })
  await expect(card).toContainText('Published')
  await card.click()
  await expect(page.getByTestId('after-choice')).toContainText('Create a draft Sales Order')
  await expect(page.getByTestId('person-row')).toHaveCount(2)
})

test('the editor fits a phone', async ({ page }) => {
  await login(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/sign/templates/new/print-format')
  await expect(page.getByTestId('template-title')).toBeVisible()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
  expect(overflow).toBe(false)
  await page.screenshot({ path: '../e2e/test-results/templates-editor-mobile.png', fullPage: true })
})

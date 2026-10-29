// Send wizard with a Print Format source (P2.9): from the Quotation form's dialog, "Preview and edit"
// opens /sign/new with the Quotation; recipients are resolved, the anchors are previewed, and the
// envelope is sent.
import { expect, test } from '@playwright/test'
import { benchExecute } from './bench'

const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'admin'

interface Prepared {
  quotation: string
  template: string
  started: string
}

let prepared: Prepared | undefined

test.beforeAll(() => {
  prepared = benchExecute<Prepared>('prepare_quotation')
})

test.afterAll(() => {
  if (prepared) benchExecute('purge_quotation', { started: prepared.started }, 5)
})

test('customize a Quotation send in the wizard', async ({ page, context }) => {
  const { quotation } = prepared!
  const login = await page.request.post('/api/method/login', { data: { usr: 'Administrator', pwd: ADMIN_PASSWORD } })
  expect(login.ok()).toBeTruthy()

  await page.goto(`/app/quotation/${quotation}`)
  await page.getByRole('button', { name: 'Send for Signature' }).click()
  const dialog = page.locator('.modal.show').filter({ hasText: 'Recipients' })
  await expect(dialog.getByText('ahmed@gulftrading.example')).toBeVisible()
  const [wizard] = await Promise.all([
    context.waitForEvent('page'),
    dialog.getByRole('button', { name: 'Preview and edit' }).click(),
  ])

  // Recipients come from the Quotation.
  await expect(wizard.getByTestId('send-wizard')).toBeVisible()
  await expect(wizard.getByText(`Quotation ${quotation}`)).toBeVisible({ timeout: 30_000 })
  await expect(wizard.getByPlaceholder('Email').first()).toHaveValue('ahmed@gulftrading.example')
  await wizard.getByRole('button', { name: 'Next' }).click()

  // Preview: the sign_field() anchors of the Print Format, drawn on the rendered pages.
  await expect(wizard.getByTestId('anchor-preview')).toBeVisible()
  await expect(wizard.getByTestId('anchor')).toHaveCount(3)
  await expect(wizard.getByTestId('warnings')).toBeVisible()
  await expect(wizard.getByTestId('anchor-preview').locator('canvas').first()).toBeVisible()
  await wizard.waitForTimeout(1000)
  await wizard.screenshot({ path: '../e2e/test-results/wizard-anchor-preview.png', fullPage: true })
  await wizard.getByTestId('next').click()

  await wizard.getByTestId('send').click()
  await expect(wizard.getByTestId('envelope-detail')).toBeVisible()
  await expect(wizard.getByTestId('person').first()).toContainText('Ahmed')
})

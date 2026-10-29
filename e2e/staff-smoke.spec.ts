// Staff app smoke test (P1.16, P1.17): design and publish a template, send it, open the envelope.
import { resolve } from 'node:path'
import { expect, test } from '@playwright/test'
import { benchExecute } from './bench'

const PDF = resolve(__dirname, '../frappe_sign/tests/fixtures/pdfs/a4_simple.pdf')
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'admin'
let started = ''

test.beforeAll(() => {
  started = benchExecute<{ now: string }>('prepare_staff').now
})

test.afterAll(() => {
  if (started) benchExecute('purge_created', { started }, 5)
})

test('design, publish and send a template', async ({ page }) => {
  const login = await page.request.post('/api/method/login', { data: { usr: 'Administrator', pwd: ADMIN_PASSWORD } })
  expect(login.ok()).toBeTruthy()

  // New template, then the designer.
  page.once('dialog', (dialog) => dialog.accept('E2E Designer Template'))
  await page.goto('/sign/templates')
  await page.getByRole('button', { name: 'New template' }).click()
  await page.getByTestId('kind-pdf').click()
  await expect(page.getByTestId('designer')).toBeVisible()
  await page.getByTestId('upload-pdf').setInputFiles(PDF)
  const pageBox = page.getByTestId('page-1')
  await expect(pageBox).toBeVisible()

  // Place a signature with the palette, then drag it.
  await page.getByTestId('palette-Signature').click()
  const box = (await pageBox.boundingBox())!
  await pageBox.click({ position: { x: box.width * 0.1, y: box.height * 0.7 } })
  const field = page.locator('[data-field="signer_1_signature_1"]')
  await expect(field).toBeVisible()
  const before = (await field.boundingBox())!
  await page.mouse.move(before.x + 10, before.y + 10)
  await page.mouse.down()
  await page.mouse.move(before.x + 60, before.y + 40, { steps: 5 })
  await page.mouse.up()
  const after = (await field.boundingBox())!
  expect(after.x - before.x).toBeGreaterThan(40)
  await page.keyboard.press('Control+z')
  await expect.poll(async () => Math.round((await field.boundingBox())!.x)).toBe(Math.round(before.x))
  await page.screenshot({ path: '../e2e/test-results/staff-designer.png' })
  await page.getByRole('button', { name: 'Publish' }).click()
  await expect(page.getByText(/Published: STPL-/)).toBeVisible()

  // Send it with the wizard.
  await page.goto('/sign/new')
  await page.getByTestId('choice-template').click()
  await page.getByRole('button', { name: 'E2E Designer Template' }).click()
  await page.getByTestId('next').click()
  await page.getByPlaceholder('Full name').fill('Ahmed Khan')
  await page.getByPlaceholder('Email').fill('ahmed.e2e@example.com')
  await page.getByRole('button', { name: 'Next' }).click()
  await page.getByTestId('send').click()

  // The envelope detail with its audit trail.
  await expect(page.getByTestId('envelope-detail')).toBeVisible()
  await expect(page.getByTestId('person').first()).toContainText('Ahmed Khan')
  await page.getByRole('button', { name: 'Show audit details' }).click()
  await expect(page.getByTestId('event').first()).toContainText('Created')
  await expect(page.getByTestId('chain')).toHaveAttribute('aria-label', 'Verified')
  await page.screenshot({ path: '../e2e/test-results/staff-envelope.png' })
})

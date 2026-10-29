// U.8: the designer's drop zone, grouped palette with icons, compact people, save state and
// icon undo and redo.
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

test('drop zone, palette groups, compact people, save state, undo and redo', async ({ page }) => {
  const login = await page.request.post('/api/method/login', { data: { usr: 'Administrator', pwd: ADMIN_PASSWORD } })
  expect(login.ok()).toBeTruthy()
  await page.setViewportSize({ width: 1440, height: 900 })
  page.once('dialog', (dialog) => dialog.accept('E2E Polished Designer'))
  await page.goto('/sign/templates')
  await page.getByRole('button', { name: 'New template' }).click()
  await page.getByTestId('kind-pdf').click()

  // Empty canvas: a drop zone, not a sentence. Palette in two groups.
  await expect(page.getByTestId('pdf-drop')).toBeVisible()
  await expect(page.getByTestId('palette').getByRole('heading', { name: 'Signature' })).toBeVisible()
  await expect(page.getByTestId('palette').getByRole('heading', { name: 'Details' })).toBeVisible()
  await expect(page.getByTestId('save-state')).toContainText('Saved')
  await page.screenshot({ path: '../e2e/test-results/designer-empty.png' })

  await page.getByTestId('upload-pdf').setInputFiles(PDF)
  const pageBox = page.getByTestId('page-1')
  await expect(pageBox).toBeVisible()
  await expect(page.getByTestId('pdf-drop')).toHaveCount(0)

  // People are one compact row; details open on click.
  await expect(page.getByTestId('roles').getByRole('button', { expanded: false })).toHaveCount(1)
  await page.getByTestId('roles').getByRole('button', { expanded: false }).click()
  await expect(page.getByTestId('roles').getByLabel('Name')).toBeVisible()

  // Place a field: the state says Unsaved, undo and redo are icon buttons.
  await expect(page.getByTestId('undo')).toBeDisabled()
  await page.getByTestId('palette-Signature').click()
  const box = (await pageBox.boundingBox())!
  await pageBox.click({ position: { x: box.width * 0.1, y: box.height * 0.7 } })
  await expect(page.getByTestId('save-state')).toContainText('Unsaved')
  await page.getByTestId('undo').click()
  await expect(page.locator('[data-field]')).toHaveCount(0)
  await page.getByTestId('redo').click()
  await expect(page.locator('[data-field]')).toHaveCount(1)
  await page.screenshot({ path: '../e2e/test-results/designer-placed.png' })

  await page.getByRole('button', { name: 'Save' }).click()
  await expect(page.getByTestId('save-state')).toContainText('Saved')
})

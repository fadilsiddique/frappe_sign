// Gate 2: a user submits a Quotation and sends it for signature; the customer signs on a phone;
// the signed PDF is attached, sign_status is Signed and a draft Sales Order exists.
import { expect, test, type Page } from '@playwright/test'
import { benchExecute } from './bench'

const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'admin'

interface Prepared {
  quotation: string
  template: string
  started: string
}

interface DocumentState {
  envelope: { name: string; status: string; send_state: string; sealing_state: string } | null
  document: { sign_status: string | null; sign_envelope: string | null; docstatus: number }
  attachments: string[]
  sales_orders: { name: string; docstatus: number }[]
}

let prepared: Prepared | undefined

test.beforeAll(() => {
  prepared = benchExecute<Prepared>('prepare_quotation', {
    submit: 0,
    post_sign_action: 'Create Mapped Document',
  })
})

test.afterAll(() => {
  if (prepared) benchExecute('purge_quotation', { started: prepared.started }, 5)
})

const state = () => benchExecute<DocumentState>('document_state', { doctype: 'Quotation', name: prepared!.quotation })

async function drawSignature(page: Page) {
  const pad = page.getByTestId('pad')
  await expect(pad).toBeVisible()
  const box = (await pad.boundingBox())!
  await page.mouse.move(box.x + box.width * 0.15, box.y + box.height * 0.7)
  await page.mouse.down()
  for (const [x, y] of [[0.3, 0.35], [0.45, 0.7], [0.6, 0.35], [0.75, 0.7], [0.9, 0.35]])
    await page.mouse.move(box.x + box.width * x, box.y + box.height * y, { steps: 6 })
  await page.mouse.up()
}

test('Gate 2: Quotation signed on a phone becomes a draft Sales Order', async ({ page, browser }) => {
  test.setTimeout(240_000)
  const { quotation } = prepared!
  const login = await page.request.post('/api/method/login', { data: { usr: 'Administrator', pwd: ADMIN_PASSWORD } })
  expect(login.ok()).toBeTruthy()

  // 1. The user submits the Quotation.
  await page.goto(`/app/quotation/${quotation}`)
  await page.getByRole('button', { name: 'Submit' }).click()
  await page.getByRole('button', { name: 'Yes' }).click()
  await expect.poll(() => state().document.docstatus).toBe(1)

  // 2. and sends it for signature from the form.
  await page.reload()
  await page.getByRole('button', { name: 'Send for Signature' }).click()
  const dialog = page.locator('.modal.show').filter({ hasText: 'Recipients' })
  await expect(dialog.getByText('ahmed@gulftrading.example')).toBeVisible()
  await dialog.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByText(/Sending SIGN-.* for signature/)).toBeVisible()
  const envelope = state().envelope!.name
  await expect
    .poll(() => state().envelope!.send_state, { timeout: 20_000 })
    .not.toBe('Queued')
    .catch(() => benchExecute('render_if_queued', { envelope }, 3))
  expect(state().envelope!.status).toBe('Sent')
  await page.reload()
  await expect(page.getByText('Signature: Sent')).toBeVisible({ timeout: 30_000 })

  // 3. The customer signs on a 390 px phone.
  const { token } = benchExecute<{ token: string }>('signing_token', { envelope, email: 'ahmed@gulftrading.example' })
  expect(token).toBeTruthy()
  const phone = await browser.newContext({
    viewport: { width: 390, height: 844 },
    hasTouch: true,
    isMobile: true,
    deviceScaleFactor: 3,
  })
  const guest = await phone.newPage()
  await guest.goto(`/s/${token}`)
  await guest.getByTestId('agree').check()
  await guest.getByTestId('start').click()
  await expect(guest.locator('[data-field="customer_signature_1"]')).toBeVisible()
  await guest.getByTestId('next').click()
  await expect(guest.getByTestId('signature-sheet')).toBeVisible()
  await guest.waitForTimeout(500) // let the sheet finish sliding in before drawing
  await drawSignature(guest)
  await guest.getByTestId('save-signature').click()
  await expect(guest.locator('[data-field="customer_signature_1"]')).toHaveAttribute('data-done', '1')
  await guest.screenshot({ path: '../e2e/test-results/gate2-phone-signed.png' })
  await guest.getByTestId('finish').click()
  await guest.getByTestId('confirm-finish').click()
  await expect(guest.getByTestId('terminal')).toHaveAttribute('data-screen', 'signed')
  await phone.close()

  // 4. Sealing, write-back and the post-sign action: a worker, or inline when none runs them.
  await expect
    .poll(() => state().envelope!.sealing_state, { timeout: 45_000 })
    .toBe('Sealed')
    .catch(() => benchExecute('complete_pending', { envelope }, 3))
  await expect
    .poll(() => state().document.sign_status, { timeout: 60_000 })
    .toBe('Signed')
  await expect.poll(() => state().sales_orders.length, { timeout: 60_000 }).toBe(1)

  const final = state()
  expect(final.envelope!.status).toBe('Completed')
  expect(final.attachments).toContain(`${envelope}-signed.pdf`)
  expect(final.sales_orders[0].docstatus).toBe(0)

  await page.reload()
  await expect(page.getByText('Signature: Signed')).toBeVisible()
  await page.screenshot({ path: '../e2e/test-results/gate2-quotation-signed.png' })
})

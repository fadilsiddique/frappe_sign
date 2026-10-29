// Desk integration (P2.5): send a submitted Quotation from its form, see the print view button
// and the list view bulk action.
import { expect, test } from '@playwright/test'
import { benchExecute } from './bench'

const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'admin'

interface Prepared {
  quotation: string
  template: string
  started: string
}

interface DocumentState {
  envelope: { name: string; status: string; send_state: string; send_error: string | null } | null
  document: { sign_status: string | null; sign_envelope: string | null }
}

let prepared: Prepared | undefined

test.beforeAll(() => {
  prepared = benchExecute<Prepared>('prepare_quotation')
})

test.afterAll(() => {
  if (prepared) benchExecute('purge_quotation', { started: prepared.started }, 5)
})

test('send a Quotation for signature from Desk', async ({ page }) => {
  const { quotation } = prepared!
  const login = await page.request.post('/api/method/login', { data: { usr: 'Administrator', pwd: ADMIN_PASSWORD } })
  expect(login.ok()).toBeTruthy()

  // Form: the button opens the dialog with the Customer found on the Quotation.
  await page.goto(`/app/quotation/${quotation}`)
  await page.getByRole('button', { name: 'Send for Signature' }).click()
  const dialog = page.locator('.modal.show').filter({ hasText: 'Who signs' })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByText('ahmed@gulftrading.example')).toBeVisible()
  // U.12: plain rows without the selection column, the message folded away, "Preview and edit".
  await expect(dialog.locator('.grid-row-check:visible')).toHaveCount(0)
  await expect(dialog.getByRole('button', { name: 'Preview and edit' })).toBeVisible()
  await expect(dialog.getByText('Message to signers')).toBeHidden()
  await dialog.getByText('Add a message').click()
  await expect(dialog.getByText('Message to signers')).toBeVisible()
  await page.screenshot({ path: '../e2e/test-results/desk-send-dialog.png' })
  await dialog.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByText(/Sending SIGN-.* for signature/)).toBeVisible()

  // The render job: a bench worker, or inline when none is running.
  let state = benchExecute<DocumentState>('document_state', { doctype: 'Quotation', name: quotation })
  expect(state.envelope).not.toBeNull()
  await expect
    .poll(
      () => {
        state = benchExecute<DocumentState>('document_state', { doctype: 'Quotation', name: quotation })
        return state.envelope!.send_state
      },
      { timeout: 20_000 },
    )
    .not.toBe('Queued')
    .catch(() => benchExecute('render_if_queued', { envelope: state.envelope!.name }, 3))
  state = benchExecute<DocumentState>('document_state', { doctype: 'Quotation', name: quotation })
  expect(state.envelope!.send_error).toBeNull()
  expect(state.envelope!.status).toBe('Sent')

  // Form headline: the status and who the request waits for.
  await page.goto(`/app/quotation/${quotation}`)
  await expect(page.locator('.form-message')).toContainText('waiting for')

  // Print view: the same button, for the Print Format on screen.
  await page.goto(`/app/print/Quotation/${quotation}`)
  await expect(page.getByRole('button', { name: 'Send for Signature' })).toBeVisible()

  // List view: bulk action in the Actions menu once a row is selected.
  await page.goto('/app/quotation')
  await page.locator('.list-row-checkbox').first().check()
  await page.getByRole('button', { name: 'Actions' }).click()
  await expect(page.getByRole('menuitem', { name: 'Send for Signature' })).toBeVisible()

  // Dashboards (P2.10): the Customer's connections list its envelopes; the workspace has the cards.
  await page.goto('/app/customer/Gulf Trading LLC')
  await page.getByRole('tab', { name: 'Connections' }).click()
  await expect(page.locator('.form-dashboard').getByText('Signatures', { exact: true })).toBeVisible()
  await expect(page.locator('.form-dashboard').getByText('Sign Envelope')).toBeVisible()
  await page.goto('/app/signatures')
  await expect(page.getByText('Awaiting Others')).toBeVisible()
  for (const label of ['Open Frappe Sign', 'New request', 'Settings', 'Get started'])
    await expect(page.locator('.widget.shortcut-widget-box').getByText(label, { exact: true })).toBeVisible()
  // The sidebar lists only the four working entries, not the internal DocTypes.
  const sidebar = page.locator('.desk-sidebar, .body-sidebar')
  await expect(sidebar.getByText('Trigger Log')).toHaveCount(0)
  await expect(sidebar.getByText('Requests', { exact: true }).first()).toBeVisible()
  await page.screenshot({ path: '../e2e/test-results/desk-signatures-workspace.png' })
})

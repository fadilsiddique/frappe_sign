// P3.5: the signing page in Arabic at 390 px, from the first screen to the done screen, for the
// user's review. The envelope's language is Arabic, so no browser setting is needed.
import { expect, test } from '@playwright/test'
import { axeFindings } from './axe'
import { benchExecute, type GuestEnvelope } from './bench'
import { drawSignature } from './signature-pad'

const OUT = '../docs/ux/ar'
let fixture: GuestEnvelope
let verify: GuestEnvelope

test.beforeAll(() => {
  fixture = benchExecute<GuestEnvelope>('create_guest_envelope', { language: 'ar' })
})

test.afterAll(() => {
  if (fixture) benchExecute('purge', { envelope: fixture.envelope, started: fixture.started }, 5)
  if (verify) benchExecute('purge', { envelope: verify.envelope, started: verify.started }, 5)
})

test('the guest page signs in Arabic', async ({ page }) => {
  await page.goto(`/s/${fixture.token}`)
  await expect(page.getByTestId('consent')).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl')
  await expect(page.locator('html')).toHaveAttribute('lang', /^ar/)
  await expect(page.getByTestId('language-switch')).toHaveText('English')
  await page.screenshot({ path: `${OUT}/30-guest-consent.png`, fullPage: true })
  expect(await axeFindings(page)).toEqual([])

  await page.getByTestId('agree').check()
  await page.getByTestId('start').click()
  await expect(page.getByTestId('sign')).toBeVisible()
  await page.waitForLoadState('networkidle')
  await page.screenshot({ path: `${OUT}/31-guest-sign.png` })
  expect(await axeFindings(page)).toEqual([])

  await page.getByTestId('more').click()
  await expect(page.getByTestId('open-decline')).toBeVisible()
  await page.screenshot({ path: `${OUT}/32-guest-more.png` })
  await page.keyboard.press('Escape')
  await page.mouse.click(10, 300)

  await page.getByTestId('next').click()
  await expect(page.getByTestId('signature-sheet')).toBeVisible()
  await drawSignature(page)
  await page.screenshot({ path: `${OUT}/33-guest-signature-sheet.png` })
  await page.getByTestId('save-signature').click()
  await expect(page.getByTestId('signature-sheet')).toBeHidden()

  await page.getByTestId('finish').click()
  await expect(page.getByTestId('confirm')).toBeVisible()
  await page.waitForTimeout(600)
  await page.screenshot({ path: `${OUT}/34-guest-review.png` })
  await page.getByTestId('confirm-finish').click()
  await expect(page.getByTestId('terminal')).toBeVisible()
  await page.screenshot({ path: `${OUT}/35-guest-done.png` })
})

test('the code step, the expired link and the language switch in Arabic', async ({ page }) => {
  verify = benchExecute<GuestEnvelope>('create_guest_envelope', { otp_mode: 'Email', language: 'ar' })
  await page.goto(`/s/${verify.token}`)
  await expect(page.getByTestId('verify')).toBeVisible()
  await page.screenshot({ path: `${OUT}/36-guest-code.png` })

  await page.goto('/s/not-a-real-link')
  await expect(page.getByRole('heading').first()).toBeVisible()
  await page.screenshot({ path: `${OUT}/37-guest-expired.png` })

  // The signer's own choice wins over the sender's: switch to English and back.
  await page.goto(`/s/${verify.token}`)
  await page.getByTestId('language-switch').click()
  await expect(page.locator('html')).toHaveAttribute('lang', /^en/)
  await page.getByTestId('language-switch').click()
  await expect(page.locator('html')).toHaveAttribute('lang', /^ar/)
})

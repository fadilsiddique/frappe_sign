// U.13: the guest page and the verify page at 390 px, in left to right and right to left: no
// sideways scroll, no serious axe findings (contrast included), and a visible focus ring.
import { expect, test, type Page } from '@playwright/test'
import { axeFindings } from './axe'
import { benchExecute, type GuestEnvelope } from './bench'

let fixture: GuestEnvelope

// Consent is recorded on the first visit, so every test gets its own envelope.
test.beforeEach(() => {
  fixture = benchExecute<GuestEnvelope>('create_guest_envelope')
})

test.afterEach(() => {
  if (fixture) benchExecute('purge', { envelope: fixture.envelope, started: fixture.started }, 5)
})

async function rtl(page: Page) {
  await page.evaluate(() => document.documentElement.setAttribute('dir', 'rtl'))
}

async function expectSound(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow).toBeLessThanOrEqual(0)
  expect(await axeFindings(page)).toEqual([])
}

for (const right of [false, true]) {
  const mode = right ? 'right to left' : 'left to right'

  test(`consent and signing screens, ${mode}`, async ({ page }) => {
    await page.goto(`/s/${fixture.token}`)
    await expect(page.getByTestId('consent')).toBeVisible()
    if (right) await rtl(page)
    await expectSound(page)
    await page.screenshot({ path: `../e2e/test-results/u13-guest-consent-${right ? 'rtl' : 'ltr'}.png` })
    await page.getByTestId('consent').getByRole('checkbox').check()
    await page.getByTestId('start').click()
    await expect(page.getByTestId('guest-header')).toBeVisible()
    await page.waitForLoadState('networkidle')
    await expectSound(page)
    await page.screenshot({ path: `../e2e/test-results/u13-guest-sign-${right ? 'rtl' : 'ltr'}.png` })
  })

  test(`expired screen, ${mode}`, async ({ page }) => {
    await page.goto('/s/not-a-real-link')
    await expect(page.getByRole('heading').first()).toBeVisible()
    if (right) await rtl(page)
    await expectSound(page)
    if (!right) await page.screenshot({ path: '../docs/ux/after/u13-guest-expired-390.png' })
  })

  test(`verify page, ${mode}`, async ({ page }) => {
    await page.goto('/sign-verify')
    if (right) await rtl(page)
    await page.getByLabel('Request ID').fill('SIGN-1999-99999')
    await page.getByRole('button', { name: 'Verify' }).click()
    await expect(page.getByTestId('verify-bad')).toBeVisible()
    await expectSound(page)
  })
}

test('the first Tab on the guest and verify pages shows a focus ring', async ({ page }) => {
  for (const path of [`/s/${fixture.token}`, '/sign-verify']) {
    await page.goto(path)
    await page.waitForLoadState('networkidle')
    await page.keyboard.press('Tab')
    const visible = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null
      if (!el || el === document.body) return false
      const style = getComputedStyle(el)
      return style.outlineStyle !== 'none' || style.boxShadow !== 'none'
    })
    expect(visible, path).toBeTruthy()
  }
})

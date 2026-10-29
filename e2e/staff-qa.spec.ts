// U.13: the quality bar for every staff screen: no sideways scroll at 1440 and 390 px, in left to
// right and right to left, axe findings (contrast included), a visible focus ring on the first Tab,
// and the after screenshots in docs/ux/after.
import { expect, test, type Page } from '@playwright/test'
import { axeFindings } from './axe'
import { benchExecute } from './bench'

const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'admin'
const SCREENS: [string, string][] = [
  ['home', '/sign'],
  ['sent', '/sign/requests'],
  ['new', '/sign/new'],
  ['templates', '/sign/templates'],
  ['settings', '/sign/settings'],
]
const SIZES = { '1440': { width: 1440, height: 900 }, '390': { width: 390, height: 844 } }

let started: string | undefined
let request: string | undefined

test.beforeAll(() => {
  const made = benchExecute<Record<string, string>>('create_sent_requests')
  started = made.started
  request = made.customer
})

test.afterAll(() => {
  if (started) benchExecute('purge_created', { started }, 5)
})

async function login(page: Page) {
  const response = await page.request.post('/api/method/login', { data: { usr: 'Administrator', pwd: ADMIN_PASSWORD } })
  expect(response.ok()).toBeTruthy()
}

async function open(page: Page, path: string, rtl: boolean) {
  await page.goto(path)
  await page.waitForLoadState('networkidle')
  if (rtl) await page.evaluate(() => document.documentElement.setAttribute('dir', 'rtl'))
}

async function expectNoSidewaysScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow).toBeLessThanOrEqual(0)
}

for (const [name, path] of SCREENS) {
  for (const [size, viewport] of Object.entries(SIZES)) {
    for (const rtl of [false, true]) {
      test(`${name} at ${size} px ${rtl ? 'right to left' : 'left to right'}`, async ({ page }) => {
        await login(page)
        await page.setViewportSize(viewport)
        await open(page, path, rtl)
        await expectNoSidewaysScroll(page)
        if (!rtl) await page.screenshot({ path: `../docs/ux/after/u13-${name}-${size}.png` })
        else await page.screenshot({ path: `../e2e/test-results/u13-${name}-${size}-rtl.png` })
        expect(await axeFindings(page)).toEqual([])
      })
    }
  }
}

test('the Sent preview and the request detail hold in right to left', async ({ page }) => {
  await login(page)
  await open(page, `/sign/requests/${request}`, true)
  await expectNoSidewaysScroll(page)
  await page.screenshot({ path: '../e2e/test-results/u13-detail-1440-rtl.png' })
  expect(await axeFindings(page)).toEqual([])
})

test('the first Tab shows a focus ring on every screen', async ({ page }) => {
  await login(page)
  await page.setViewportSize(SIZES['1440'])
  for (const [, path] of SCREENS) {
    await open(page, path, false)
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

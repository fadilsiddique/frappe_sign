// U.3: Home leads a new site through setup, then shows what waits for the user and on whom.
import { expect, test, type Page } from '@playwright/test'
import { benchExecute } from './bench'

const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'admin'
const STEPS = ['email', 'seal', 'profile', 'documents', 'template', 'test']

interface HomeRequests {
  for_me: string
  for_customer: string
  started: string
}
let requests: HomeRequests | undefined

test.afterAll(() => {
  if (requests) benchExecute('purge_created', { started: requests.started }, 5)
})

async function login(page: Page) {
  const response = await page.request.post('/api/method/login', { data: { usr: 'Administrator', pwd: ADMIN_PASSWORD } })
  expect(response.ok()).toBeTruthy()
}

// The setup status of a site where the first `done` steps are finished. The dev site is already set
// up, so the walk-through answers get_setup_status itself instead of undoing real setup.
function setupStatus(done: number) {
  const steps = STEPS.map((key, index) => ({
    key,
    done: index < done,
    can_fix: true,
    required: true,
    facts: key === 'email' && index < done ? { email_id: 'sign@gulftrading.example' } : {},
  }))
  return { message: { steps, complete: done === STEPS.length } }
}

async function answerSetup(page: Page, done: number) {
  await page.unroute('**/frappe_sign.api.staff.get_setup_status*')
  await page.route('**/frappe_sign.api.staff.get_setup_status*', (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify(setupStatus(done)) }),
  )
}

test('the setup panel leads an empty site through setup', async ({ page }) => {
  await login(page)
  const panel = page.getByTestId('setup-panel')
  const openStep = panel.getByTestId('step-detail')

  // Nothing done: the email account comes first, in Desk.
  await answerSetup(page, 0)
  await page.goto('/sign')
  await expect(panel).toBeVisible()
  await expect(panel).toContainText('0 of 6')
  await expect(openStep).toHaveCount(1)
  await expect(openStep.getByRole('link', { name: 'Set up email' })).toHaveAttribute('href', '/app/email-account')
  await expect(page.getByRole('navigation', { name: 'Main' }).getByText('6 left')).toBeVisible()
  await page.screenshot({ path: '../e2e/test-results/home-setup-empty.png' })

  // Each finished step moves the panel on to the next one.
  await answerSetup(page, 1)
  await page.reload()
  await expect(panel.locator('[data-step="email"]')).toContainText('sign@gulftrading.example')
  await expect(openStep.getByRole('link', { name: 'Create a seal' })).toHaveAttribute('href', '/sign/settings')

  await answerSetup(page, 3)
  await page.reload()
  await expect(openStep.getByRole('link', { name: 'Choose documents' })).toHaveAttribute('href', '/sign/settings?tab=documents')

  // The last steps stay in the staff app.
  await answerSetup(page, 5)
  await page.reload()
  await openStep.getByRole('link', { name: 'Send a test' }).click()
  await expect(page).toHaveURL(/\/sign\/new$/)

  // Everything done: the panel gives way to the month's figures.
  await answerSetup(page, 6)
  await page.goto('/sign')
  await expect(page.getByTestId('month')).toBeVisible()
  await expect(panel).toHaveCount(0)
})

test('Home shows what waits for me and whom I wait on', async ({ page }) => {
  requests = benchExecute<HomeRequests>('create_home_requests')
  await login(page)
  await page.goto('/sign')

  const toSign = page.getByTestId('to-sign-row').filter({ hasText: 'E2E Lease for Unit 4B' })
  await expect(toSign).toContainText('Administrator asked you to sign')

  const waiting = page.getByTestId('waiting')
  const outside = waiting.locator('[data-group="outside"]').getByTestId('waiting-row').filter({ hasText: 'E2E Supply Quotation' })
  await expect(outside).toContainText('Next: Ahmed Khan, not opened yet')
  await expect(outside).toContainText('0 of 2')
  const team = waiting.locator('[data-group="team"]').getByTestId('waiting-row').filter({ hasText: 'E2E Lease for Unit 4B' })
  await expect(team).toContainText('Next: Administrator')
  await page.screenshot({ path: '../e2e/test-results/home-queue.png', fullPage: true })

  // A waiting row opens the request.
  await outside.click()
  await expect(page).toHaveURL(new RegExp(`/sign/requests/${requests.for_customer}$`))

  // Sign opens the signing page for my own link.
  await page.goBack()
  await toSign.getByRole('button', { name: 'Sign' }).click()
  await expect(page).toHaveURL(/\/s\/[\w-]+$/)
})

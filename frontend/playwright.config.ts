import { defineConfig } from '@playwright/test'

// End-to-end tests in ../e2e run against a bench site that has allow_tests set.
//   bench --site sign.localhost serve --port 8012      (from the bench directory)
//   yarn e2e                                           (from frontend/)
// E2E_BASE_URL, E2E_SITE and E2E_BENCH override the defaults; E2E_CHANNEL picks the browser
// (default: the installed Google Chrome, so no browser download is needed).
export default defineConfig({
  testDir: '../e2e',
  outputDir: '../e2e/test-results',
  timeout: 90_000,
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://127.0.0.1:8012',
    channel: process.env.E2E_CHANNEL ?? 'chrome',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'phone-390',
      use: { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 3 },
    },
  ],
})

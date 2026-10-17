import { defineConfig, devices } from '@playwright/test'

const externalURL = process.env.SNACKPRESS_BASE_URL

export default defineConfig({
  testDir: './tests/e2e',
  testIgnore: 'accounts.spec.ts',
  fullyParallel: false,
  use: {
    baseURL: externalURL || 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    channel: process.env.SNACKPRESS_BROWSER_CHANNEL || undefined,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: externalURL
    ? []
    : [
        {
          command: '.venv/bin/python scripts/serve.py',
          url: 'http://127.0.0.1:8000/api/health',
          reuseExistingServer: !process.env.CI,
        },
        { command: 'pnpm dev', url: 'http://127.0.0.1:5173', reuseExistingServer: !process.env.CI },
      ],
})

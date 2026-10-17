import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { defineConfig } from '@playwright/test'
import base from './playwright.config'

process.env.SNACKPRESS_ACCOUNT_TEST_DATA ||= mkdtempSync(join(tmpdir(), 'snackpress-accounts-'))
export default defineConfig({
  ...base,
  testIgnore: [],
  testMatch: 'accounts.spec.ts',
  outputDir: 'test-results/accounts',
  workers: 1,
  timeout: 60000,
  globalTeardown: './tests/e2e/accounts-cleanup.ts',
  use: { ...base.use, baseURL: 'http://127.0.0.1:5175' },
  webServer: [
    {
      command: '.venv/bin/python -m uvicorn snackpress_api.main:app --host 127.0.0.1 --port 8015',
      url: 'http://127.0.0.1:8015/api/health',
      env: {
        PYTHONPATH: 'apps/api:packages/imposition:packages/prepress',
        SNACKPRESS_DATA: process.env.SNACKPRESS_ACCOUNT_TEST_DATA,
        SNACKPRESS_MAIL_MODE: 'file',
        SNACKPRESS_PUBLIC_URL: 'http://127.0.0.1:5175',
      },
    },
    {
      command: 'pnpm --filter @snackpress/web dev --port 5175 --strictPort',
      url: 'http://127.0.0.1:5175',
      env: { SNACKPRESS_API_PROXY: 'http://127.0.0.1:8015' },
    },
  ],
})

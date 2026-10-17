import { defineConfig } from '@playwright/test'
import accounts from './playwright.accounts.config'

export default defineConfig({
  ...accounts,
  testMatch: ['products.spec.ts', 'product-accounts.spec.ts', 'burger.spec.ts'],
  outputDir: 'test-results/products',
})

import type { Page } from '@playwright/test'

export async function openSettings(page: Page, title: string) {
  const summary = page
    .locator('details.settings-section > summary')
    .filter({ has: page.getByText(title, { exact: true }) })
  if ((await summary.locator('..').getAttribute('open')) === null) await summary.click()
}

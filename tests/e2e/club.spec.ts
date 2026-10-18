import { test, expect } from '@playwright/test'
import { openSettings } from './settings'

for (const mobile of [false, true]) {
  test(`Club Sandwich : estimation immédiate (${mobile ? 'mobile' : 'bureau'})`, async ({
    page,
  }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/?tool=club-sandwich')
    const estimate = page.getByLabel('Dos estimé', { exact: true })
    await expect(estimate).toHaveText('6,900 mm')
    const pages = page.getByLabel('Pages intérieures (nombre pair)', { exact: true })
    await pages.fill('256')
    await expect(estimate).toHaveText('13,300 mm', { timeout: 1000 })
    await page.getByLabel('Marge de colle estimée', { exact: true }).fill('1')
    await expect(estimate).toHaveText('13,800 mm', { timeout: 1000 })
    await openSettings(page, 'Papier')
    await page.getByLabel('Grammage', { exact: true }).fill('120')
    await page.getByLabel('Main du papier', { exact: true }).fill('1.5')
    await expect(estimate).toHaveText('24,040 mm', { timeout: 1000 })
    await page.getByLabel('Méthode de calcul', { exact: true }).selectOption('caliper')
    await expect(estimate).toHaveText('13,800 mm', { timeout: 1000 })
    await page.getByLabel('Calibre d’une feuille', { exact: true }).fill('150')
    await expect(estimate).toHaveText('20,200 mm', { timeout: 1000 })
    await expect(page.locator('.club-estimate')).toContainText(
      '19,200 mm de bloc papier + 1,000 mm de colle',
    )
    await expect(page.getByLabel('Calibre d’une feuille', { exact: true })).toBeFocused()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page
      .locator('.tool-controls')
      .screenshot({ path: `test-results/club-${mobile ? 'mobile' : 'desktop'}.png` })
    await pages.fill('255')
    await expect(estimate).toHaveText('—', { timeout: 1000 })
    await pages.fill('')
    await expect(estimate).toHaveText('—')
    await pages.fill('128')
    await expect(estimate).toHaveText('10,600 mm', { timeout: 1000 })
  })
}

import { openSettings } from './settings'
import { test, expect } from '@playwright/test'

test('Pizza : aperçu automatique, ovale, saisie rapide et export final', async ({ page }) => {
  test.setTimeout(60000)
  let imports = 0
  let renders = 0
  let exports = 0
  page.on('request', (request) => {
    if (request.url().includes('/api/tools/pizza/previews') && request.method() === 'POST')
      imports++
    if (request.url().includes('/render') && request.method() === 'POST') renders++
    if (request.url().includes('/api/tools/pizza/run')) exports++
  })
  await page.goto('/?tool=pizza')
  const live = page.getByLabel('Aperçu automatique', { exact: true })
  await expect(live.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
  const importsAfterMount = imports
  await page.getByLabel('Forme', { exact: true }).selectOption('ellipse')
  await page.getByLabel('Largeur finie', { exact: true }).fill('100')
  await page.getByLabel('Hauteur finie', { exact: true }).fill('60')
  await expect(page.getByLabel('Rayon des coins', { exact: true })).toHaveCount(0)
  await expect(live.getByRole('status').filter({ hasText: 'Aperçu à jour' })).toBeVisible({
    timeout: 15000,
  })
  await expect(live.locator('.pdf-viewer-footer')).toContainText('106 × 66 mm')
  expect(imports).toBe(importsAfterMount)
  expect(exports).toBe(0)
  const count = renders
  // Keystrokes within the debounce window produce one fresh render.
  await page.getByLabel('Largeur finie', { exact: true }).fill('110')
  await page.getByLabel('Largeur finie', { exact: true }).fill('120')
  await page.getByLabel('Largeur finie', { exact: true }).fill('130')
  await expect(live.getByRole('status').filter({ hasText: 'Aperçu à jour' })).toBeVisible({
    timeout: 15000,
  })
  await expect(live.locator('.pdf-viewer-footer')).toContainText('136 × 66 mm')
  expect(renders - count).toBe(1)
  // Invalid values keep the previous PDF available, without a final export.
  await page.getByLabel('Largeur finie', { exact: true }).fill('0')
  await expect(live.getByRole('alert')).toContainText('Corrigez les réglages')
  await expect(live.locator('canvas[data-ready=true]')).toBeVisible()
  await page.getByLabel('Largeur finie', { exact: true }).fill('100')
  await expect(live.getByRole('status').filter({ hasText: 'Aperçu à jour' })).toBeVisible({
    timeout: 15000,
  })
  await expect(live.locator('.pdf-viewer-footer')).toContainText('106 × 66 mm', { timeout: 15000 })
  await expect(live.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
  await page.screenshot({ path: 'test-results/live-pizza-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: 'test-results/live-pizza-mobile.png', fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  const final = page.waitForResponse((r) => r.url().includes('/api/tools/pizza/run'))
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  expect((await final).status()).toBe(201)
  await expect(page.locator('.artifact-downloads a').first()).toBeVisible()
})

test('dernière modification affichée malgré une ancienne réponse retardée', async ({ page }) => {
  await page.goto('/?tool=pizza')
  const live = page.getByLabel('Aperçu automatique', { exact: true })
  await expect(live.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
  let delayed = false
  await page.route('**/api/tool-previews/*/render', async (route) => {
    if (!delayed) {
      delayed = true
      const response = await route.fetch()
      await new Promise((resolve) => setTimeout(resolve, 1000))
      await route.fulfill({ response }).catch(() => {})
    } else await route.continue()
  })
  await page.getByLabel('Largeur finie', { exact: true }).fill('110')
  await expect.poll(() => delayed).toBe(true)
  await page.getByLabel('Largeur finie', { exact: true }).fill('140')
  await expect(live.locator('.pdf-viewer-footer')).toContainText('146 × 61 mm', { timeout: 15000 })
  await expect(live.getByRole('status').filter({ hasText: 'Aperçu à jour' })).toBeVisible()
  await expect(live.locator('.pdf-viewer-footer')).not.toContainText('116 ×')
})

test('Fortune Cookie : PDF automatique limité, placement interactif et série complète', async ({
  page,
}) => {
  await page.goto('/?tool=fortune-cookie')
  await openSettings(page, 'Numérotation')
  await page.getByLabel('Nombre d’exemplaires').fill('12')
  const live = page.getByLabel('Aperçu automatique', { exact: true })
  await expect(live.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
  await expect(live).toContainText('deux premiers exemplaires')
  await expect(page.getByLabel('Déplacer la numérotation 1')).toBeVisible()
  await openSettings(page, 'Positions des numéros')
  await page
    .getByRole('group', { name: 'Numérotation 1', exact: true })
    .getByLabel('Position X')
    .fill('20')
  await expect(live.getByRole('status').filter({ hasText: 'Aperçu à jour' })).toBeVisible({
    timeout: 15000,
  })
  const final = page.waitForResponse((r) => r.url().includes('/api/tools/fortune-cookie/run'))
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  expect((await final).status()).toBe(201)
  await expect(page.locator('.artifact-downloads')).toContainText('12 pages')
})

test('imposition : aperçu PDF automatique avant export et mise à jour des réglages', async ({
  page,
}) => {
  await page.goto('/?tool=imposition')
  await page.getByRole('button', { name: 'Essayer avec une carte exemple' }).click()
  const live = page.getByLabel('Aperçu automatique', { exact: true })
  await expect(live.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
  await expect(page.getByRole('link', { name: 'Télécharger le PDF', exact: true })).toHaveCount(0)
  await page.getByRole('spinbutton', { name: 'Marges machine, sur les 4 côtés mm' }).fill('12')
  await expect(live.getByRole('status').filter({ hasText: 'Aperçu à jour' })).toBeVisible({
    timeout: 15000,
  })
  await page.getByRole('tab', { name: 'Verso', exact: true }).click()
  await expect(live.getByRole('img', { name: 'Aperçu PDF, page 2', exact: true })).toBeVisible({
    timeout: 15000,
  })
  await page.getByRole('tab', { name: 'Recto', exact: true }).click()
  await page.getByRole('button', { name: 'Plan', exact: true }).click()
  await expect(page.getByRole('img', { name: /Recto :/ })).toBeVisible()
  await page.getByRole('button', { name: 'Aperçu PDF', exact: true }).click()
  await expect(live.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
})

import { test, expect } from '@playwright/test'
import path from 'node:path'

const source = path.resolve('apps/web/public/exemple-carte.pdf')
test.setTimeout(60000)

test('Granola : fichiers mixtes, quantités exactes, aperçu, export et conservation après retrait', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/?tool=granola')
  await expect(page.getByRole('heading', { name: 'Granola.', exact: true })).toBeVisible()
  await page.getByLabel('Format de la planche', { exact: true }).selectOption('A4')
  await expect(page.getByLabel('Largeur de la planche', { exact: true })).toHaveValue('210')
  await expect(page.getByLabel('Hauteur de la planche', { exact: true })).toHaveValue('297')
  await page.getByLabel('Format de la planche', { exact: true }).selectOption('custom')
  await expect(page.getByLabel('Format de la planche', { exact: true })).toHaveValue('custom')
  await page.getByLabel('Choisir les fichiers').setInputFiles(source)
  const png = await page.evaluate(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 600
    canvas.height = 300
    const ctx = canvas.getContext('2d')!
    ctx.fillStyle = '#263c58'
    ctx.fillRect(0, 0, 600, 300)
    ctx.fillStyle = '#ffffff'
    ctx.font = 'bold 60px sans-serif'
    ctx.fillText('ÉTIQUETTE', 90, 165)
    return canvas.toDataURL('image/png').split(',')[1]
  })
  await page.getByLabel('Choisir les fichiers').setInputFiles({
    name: 'etiquette.png',
    mimeType: 'image/png',
    buffer: Buffer.from(png, 'base64'),
  })
  await page.getByLabel('Exemplaires du fichier 1').fill('3')
  await page.getByLabel('Exemplaires du fichier 2').fill('5')
  await page.getByLabel('Largeur de l’image 2').fill('60')
  await page.getByLabel('Espacement entre les poses', { exact: true }).fill('4')
  await expect(page.locator('.granola-summary')).toContainText('8 exemplaire(s)')
  await expect(page.locator('.live-preview-status')).toContainText('Aperçu à jour', {
    timeout: 20000,
  })
  await expect(page.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
  await page.screenshot({ path: 'test-results/granola-desktop.png', fullPage: true })
  const response = page.waitForResponse((r) => r.url().includes('/api/tools/granola/run'))
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  const result = await response
  expect(result.status(), await result.text()).toBe(201)
  const data = await result.json()
  expect(data.metrics.Exemplaires).toBe(8)
  const manifest = await (
    await page.request.get(`/api/tool-jobs/${data.id}/files/plan-imposition.json`)
  ).json()
  expect(manifest.sources.map((s: { quantity: number }) => s.quantity)).toEqual([3, 5])
  expect(manifest.sources[1].width).toBeCloseTo(60)
  expect(manifest.sources[1].height).toBeCloseTo(30)
  expect(manifest.settings.gap).toBe(4)
  await expect(page.locator('.tool-success')).toContainText('8 exemplaires')
  const download = page.getByRole('link', { name: /Planches imposées/ })
  await expect(download).toBeVisible()
  await page.getByLabel('Retirer le fichier 1').click()
  await expect(page.getByLabel('Exemplaires du fichier 1')).toHaveValue('5')
  await expect(page.getByLabel('Largeur de l’image 1')).toHaveValue('60')
  await expect(page.locator('.granola-summary')).toContainText('5 exemplaire(s)')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('tab', { name: 'Réglages', exact: true }).click()
  await expect(page.getByLabel('Exemplaires du fichier 1')).toBeVisible()
  await expect(page.getByLabel('Exemplaires du fichier 1')).toHaveValue('5')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/granola-mobile-settings.png', fullPage: true })
  await page.getByRole('tab', { name: 'Aperçu', exact: true }).click()
  await expect(page.locator('.live-preview-status')).toContainText('Aperçu à jour', {
    timeout: 20000,
  })
  await expect(page.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/granola-mobile-preview.png', fullPage: true })
  await page.request.delete(`/api/tool-jobs/${data.id}`)
})

test('Granola : exemple multiformat et refus d’un fichier trop grand', async ({ page }) => {
  await page.goto('/?tool=granola')
  await page.getByRole('button', { name: /Charger un exemple/ }).click()
  await expect(page.locator('.granola-summary')).toContainText('2 fichier(s) · 8 exemplaire(s)')
  await expect(page.locator('.live-preview-status')).toContainText('Aperçu à jour', {
    timeout: 20000,
  })
  await page.getByLabel('Largeur de la planche', { exact: true }).fill('50')
  await expect(page.locator('.live-preview-error')).toContainText('ne tient pas', {
    timeout: 20000,
  })
  await page.getByLabel('Format de la planche', { exact: true }).selectOption('SRA3')
  await expect(page.locator('.live-preview-status')).toContainText('Aperçu à jour', {
    timeout: 20000,
  })
})

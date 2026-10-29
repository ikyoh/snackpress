import { test, expect } from '@playwright/test'
import path from 'node:path'

const source = path.resolve('apps/web/public/exemple-carte.pdf')
test.setTimeout(60000)

test('Granola : contour automatique et triangles imbriqués dans le PDF final', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1050 })
  await page.goto('/?tool=granola')
  await page.getByRole('button', { name: 'Exemple d’imbrication de triangles' }).click()
  await expect(page.locator('.granola-summary')).toContainText('1 fichier(s) · 2 exemplaire(s)')
  await expect(page.getByLabel('Page du fichier 1', { exact: true })).toBeDisabled()
  await expect(page.getByLabel('Contour du fichier 1', { exact: true })).toHaveValue('auto')
  await expect(page.getByText('Triangle détecté', { exact: true })).toBeVisible({ timeout: 20000 })
  await expect(page.getByRole('img', { name: 'Contour détecté du fichier 1' })).toBeVisible()
  await expect(page.locator('.live-preview-status')).toContainText('Aperçu à jour')
  await expect(page.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
  await page.screenshot({ path: 'test-results/granola-nesting-desktop.png', fullPage: true })
  const generated = page.waitForResponse((r) => r.url().includes('/api/tools/granola/run'))
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  const response = await generated
  expect(response.status(), await response.text()).toBe(201)
  const result = await response.json()
  expect(result.metrics['Paires imbriquées']).toBe(1)
  expect(result.metrics.Planches).toBe(1)
  expect(result.shapes[0].kind).toBe('triangle')
  const plan = await (
    await page.request.get(`/api/tool-jobs/${result.id}/files/plan-imposition.json`)
  ).json()
  expect(plan.sheets[0]).toHaveLength(2)
  expect(plan.sheets[0].some((p: { rotation: number }) => p.rotation >= 180)).toBe(true)
  expect(plan.sheet_format.output.width).toBeLessThan(100)
  expect(plan.settings.gap).toBe(3)
  await expect(page.getByRole('link', { name: /Planches imposées/ })).toBeVisible()
  await page.getByLabel('Contour du fichier 1', { exact: true }).selectOption('rectangle')
  await expect(page.locator('.live-preview-status')).toContainText('Aperçu à jour', {
    timeout: 20000,
  })
  const fullRectangle = page.waitForResponse((r) => r.url().includes('/api/tools/granola/run'))
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  const rectangle = await (await fullRectangle).json()
  expect(rectangle.metrics.Planches).toBe(2)
  expect(rectangle.metrics['Paires imbriquées']).toBe(0)
  await page.getByLabel('Contour du fichier 1', { exact: true }).selectOption('auto')
  await expect(page.getByText('Triangle détecté', { exact: true })).toBeVisible({ timeout: 20000 })
  await page.getByLabel('Optimisation', { exact: true }).selectOption('width')
  await expect(page.locator('.live-preview-status')).toContainText('Aperçu à jour', {
    timeout: 20000,
  })
  const widthRun = page.waitForResponse((r) => r.url().includes('/api/tools/granola/run'))
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  const widthResult = await (await widthRun).json()
  expect(widthResult.metrics.Planches).toBe(1)
  expect(widthResult.metrics['Paires imbriquées']).toBe(1)
  expect(widthResult.metrics['Largeur avec marge (mm)']).toBe(130)
  await page.getByLabel('Optimisation', { exact: true }).selectOption('area')
  await expect(page.locator('.live-preview-status')).toContainText('Aperçu à jour', {
    timeout: 20000,
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('tab', { name: 'Réglages', exact: true }).click()
  await expect(page.getByLabel('Contour du fichier 1', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({
    path: 'test-results/granola-nesting-mobile-settings.png',
    fullPage: true,
  })
  await page.getByRole('tab', { name: 'Aperçu', exact: true }).click()
  await expect(page.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/granola-nesting-mobile-preview.png', fullPage: true })
  await page.request.delete(`/api/tool-jobs/${result.id}`)
  await page.request.delete(`/api/tool-jobs/${rectangle.id}`)
  await page.request.delete(`/api/tool-jobs/${widthResult.id}`)
})

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

test('Granola : proposition de surface minimale, recadrage réversible et export aux bonnes dimensions', async ({
  page,
}) => {
  test.setTimeout(90000)
  await page.setViewportSize({ width: 1440, height: 1050 })
  await page.goto('/?tool=granola')
  await page.getByLabel('Choisir les fichiers').setInputFiles(source)
  await page.getByLabel('Exemplaires du fichier 1').fill('4')
  const proposal = page.getByRole('region', { name: 'Recadrage de la planche', exact: true })
  await expect(proposal).toBeVisible({ timeout: 20000 })
  await expect(proposal.getByRole('checkbox')).toBeChecked()
  await expect(proposal).toContainText('surface en moins')
  await expect(page.locator('.live-preview-status')).toContainText('Aperçu à jour', {
    timeout: 20000,
  })
  await proposal.getByRole('button', { name: 'Appliquer le recadrage' }).click()
  await expect(proposal).toContainText('recadrage appliqué', { timeout: 20000 })
  await expect(proposal).toBeVisible({ timeout: 20000 })
  await expect(page.getByLabel('Format d’export', { exact: true })).toHaveValue('margin')
  await expect(page.getByLabel('Optimisation', { exact: true })).toHaveValue('width')
  await expect(page.getByLabel('Largeur de la planche', { exact: true })).toHaveValue('320')
  await expect(page.getByLabel('Hauteur de la planche', { exact: true })).not.toHaveValue('450')
  await expect(page.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
  await page.screenshot({ path: 'test-results/granola-crop-desktop.png', fullPage: true })
  const generated = page.waitForResponse((r) => r.url().includes('/api/tools/granola/run'))
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  const response = await generated
  expect(response.status(), await response.text()).toBe(201)
  const result = await response.json()
  const plan = await (
    await page.request.get(`/api/tool-jobs/${result.id}/files/plan-imposition.json`)
  ).json()
  expect(plan.settings.crop).toBe('margin')
  expect(plan.settings.optimization).toBe('width')
  expect(plan.sheet_format.output.width).toBe(320)
  expect(new Set(plan.sheets.flat().map((p: { y: number }) => p.y)).size).toBe(1)
  await expect(page.getByLabel('Largeur de la planche', { exact: true })).toHaveValue(
    String(plan.sheet_format.output.width),
  )
  await expect(page.getByLabel('Hauteur de la planche', { exact: true })).toHaveValue(
    String(plan.sheet_format.output.height),
  )
  expect(plan.sheet_format.original).toEqual({ width: 320, height: 450 })
  expect(plan.sheet_format.output.width * plan.sheet_format.output.height).toBeLessThan(320 * 450)
  expect(plan.sheets.flat()).toHaveLength(4)
  expect(Math.min(...plan.sheets.flat().map((p: { x: number }) => p.x))).toBeCloseTo(10)
  await proposal.getByRole('checkbox').uncheck()
  await expect(proposal).toContainText('recadrage appliqué', { timeout: 20000 })
  await expect(page.getByLabel('Format d’export', { exact: true })).toHaveValue('poses')
  const borderless = page.waitForResponse((r) => r.url().includes('/api/tools/granola/run'))
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  const borderlessResponse = await borderless
  expect(borderlessResponse.status(), await borderlessResponse.text()).toBe(201)
  const second = await borderlessResponse.json()
  const borderlessPlan = await (
    await page.request.get(`/api/tool-jobs/${second.id}/files/plan-imposition.json`)
  ).json()
  expect(borderlessPlan.sheet_format.output.width).toBe(plan.sheet_format.output.width)
  expect(borderlessPlan.sheet_format.output.height).toBeCloseTo(
    plan.sheet_format.output.height - 20,
  )
  expect(borderlessPlan.sheets.flat()).toHaveLength(4)
  await expect(page.getByLabel('Largeur de la planche', { exact: true })).toHaveValue(
    String(borderlessPlan.sheet_format.output.width),
  )
  await expect(page.getByLabel('Hauteur de la planche', { exact: true })).toHaveValue(
    String(borderlessPlan.sheet_format.output.height),
  )
  await proposal.getByRole('button', { name: 'Rétablir le format initial' }).click()
  await expect(proposal).toBeVisible({ timeout: 20000 })
  await expect(page.getByLabel('Format d’export', { exact: true })).toHaveValue('none')
  await expect(page.getByLabel('Largeur de la planche', { exact: true })).toHaveValue('320')
  await expect(page.getByLabel('Hauteur de la planche', { exact: true })).toHaveValue('450')
  await expect(page.locator('.pdf-viewer-footer')).toContainText('320 × 450 mm', { timeout: 15000 })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('tab', { name: 'Aperçu', exact: true }).click()
  await expect(proposal).toBeVisible()
  await expect(proposal.getByRole('button', { name: 'Appliquer le recadrage' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/granola-crop-mobile.png', fullPage: true })
  await page.request.delete(`/api/tool-jobs/${result.id}`)
  await page.request.delete(`/api/tool-jobs/${second.id}`)
})

test('Granola : modifier le format recadré conserve les dimensions réelles de la planche', async ({
  page,
}) => {
  await page.goto('/?tool=granola')
  await page.getByLabel('Choisir les fichiers').setInputFiles(source)
  const proposal = page.getByRole('region', { name: 'Recadrage de la planche', exact: true })
  await expect(proposal).toBeVisible({ timeout: 20000 })
  await proposal.getByRole('button', { name: 'Appliquer le recadrage' }).click()
  await expect(proposal).toContainText('recadrage appliqué', { timeout: 20000 })
  await expect(proposal).toBeVisible({ timeout: 20000 })
  const width = page.getByLabel('Largeur de la planche', { exact: true })
  const height = page.getByLabel('Hauteur de la planche', { exact: true })
  const actualWidth = Number(await width.inputValue())
  const actualHeight = await height.inputValue()
  expect(actualWidth).toBe(320)
  expect(Number(actualHeight)).toBeLessThan(450)
  await width.fill(String(actualWidth + 10))
  await expect(height).toHaveValue(actualHeight)
  await expect(page.getByLabel('Format d’export', { exact: true })).toHaveValue('none')
  const generated = page.waitForResponse((r) => r.url().includes('/api/tools/granola/run'))
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  const response = await generated
  expect(response.status(), await response.text()).toBe(201)
  const result = await response.json()
  const plan = await (
    await page.request.get(`/api/tool-jobs/${result.id}/files/plan-imposition.json`)
  ).json()
  expect(plan.sheet_format.output.width).toBeCloseTo(actualWidth + 10)
  expect(plan.sheet_format.output.height).toBeCloseTo(Number(actualHeight))
  expect(plan.settings.crop).toBe('none')
  await page.getByLabel('Format de la planche', { exact: true }).selectOption('A4')
  await expect(width).toHaveValue('210')
  await expect(height).toHaveValue('297')
  await expect(page.getByLabel('Format d’export', { exact: true })).toHaveValue('none')
  await page.request.delete(`/api/tool-jobs/${result.id}`)
  await page.getByLabel('Optimisation', { exact: true }).selectOption('area')
  await expect(proposal).toBeVisible({ timeout: 20000 })
  await proposal.getByRole('button', { name: 'Appliquer le recadrage' }).click()
  await expect(proposal).toBeVisible({ timeout: 20000 })
  await expect(proposal).toContainText('recadrage appliqué')
  expect(Number(await width.inputValue())).toBeLessThan(210)
})

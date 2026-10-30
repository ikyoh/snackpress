import { expect, test } from '@playwright/test'

const svg =
  '<svg xmlns="http://www.w3.org/2000/svg"><path fill-rule="evenodd" d="M0 0H20V10H0Z M5 3H8V7H5Z"/></svg>'

test('Biscuit: signed offsets, SVG import and usable downloads', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/?tool=biscuit')
  await expect(page.getByRole('heading', { name: 'Biscuit.' })).toBeVisible()
  await expect(page.getByText('Aperçu à jour', { exact: true })).toBeVisible({ timeout: 20000 })
  await page.getByLabel('Décalage', { exact: true }).fill('-2')
  await expect(page.getByText('Aperçu à jour', { exact: true })).toBeVisible({ timeout: 20000 })
  await page.getByRole('button', { name: 'Générer les fichiers de découpe' }).click()
  await expect(page.getByText('Vos fichiers sont prêts')).toBeVisible({ timeout: 20000 })
  const metrics = page.locator('.biscuit-results dl')
  await expect(metrics).toContainText('81')
  const svgLink = page.getByRole('link', { name: 'Tracé de découpe SVG' })
  const response = await page.request.get((await svgLink.getAttribute('href'))!)
  expect(response.headers()['content-type']).toContain('image/svg+xml')
  expect(await response.text()).toContain('CutContour')
  await page.screenshot({ path: 'output/biscuit-desktop.png', fullPage: true })
  await page.getByRole('button', { name: 'Tracé SVG', exact: true }).click()
  await page
    .getByLabel('Importer une image ou un SVG')
    .setInputFiles({ name: 'forme.svg', mimeType: 'image/svg+xml', buffer: Buffer.from(svg) })
  await page.getByLabel('Largeur source', { exact: true }).fill('80')
  await page.getByRole('button', { name: 'Générer les fichiers de découpe' }).click()
  await expect(page.getByText('Vos fichiers sont prêts')).toBeVisible({ timeout: 20000 })
  await expect(metrics).toContainText('76')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: 'output/biscuit-mobile.png', fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  expect(errors).toEqual([])
})

test('Biscuit: transparent image, empty state and invalid negative offset', async ({ page }) => {
  await page.goto('/?tool=biscuit')
  await page.getByRole('button', { name: 'Image', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'Chaque découpe commence par une forme.' }),
  ).toBeVisible()
  await expect(page.getByRole('button', { name: 'Générer les fichiers de découpe' })).toBeDisabled()
  // Use a real PNG with a transparent border, generated in the browser.
  const png = await page.evaluate(() => {
    const canvas = document.createElement('canvas')
    canvas.width = canvas.height = 100
    const context = canvas.getContext('2d')!
    context.fillStyle = '#d22678'
    context.fillRect(10, 20, 80, 60)
    return canvas.toDataURL('image/png').split(',')[1]
  })
  await page
    .getByLabel('Importer une image ou un SVG')
    .setInputFiles({ name: 'image.png', mimeType: 'image/png', buffer: Buffer.from(png, 'base64') })
  await page.getByLabel('Largeur source', { exact: true }).fill('100')
  await page.getByLabel('Décalage', { exact: true }).fill('0')
  await page.getByRole('button', { name: 'Générer les fichiers de découpe' }).click()
  await expect(page.getByText('Vos fichiers sont prêts')).toBeVisible({ timeout: 20000 })
  await expect(page.locator('.biscuit-results dl')).toContainText('80')
  await page.getByRole('button', { name: 'Forme', exact: true }).click()
  await page.getByLabel('Décalage', { exact: true }).fill('-100')
  await page.getByRole('button', { name: 'Générer les fichiers de découpe' }).click()
  await expect(page.getByRole('alert').filter({ hasText: 'disparaître' }).first()).toBeVisible({
    timeout: 20000,
  })
})

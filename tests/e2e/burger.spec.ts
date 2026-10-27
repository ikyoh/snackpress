import { openSettings } from './settings'
import { test, expect } from '@playwright/test'

test('Burger : fichiers attendus, finition séparée et repères Pizza', async ({ page }) => {
  await page.goto('/?tool=burger')
  await page.getByLabel('Nombre de fichiers visuels attendus').fill('2')
  await openSettings(page, 'Finitions et fichiers séparés')
  await page.getByRole('button', { name: 'Ajouter une finition' }).click()
  await page.getByLabel('Finition 1', { exact: true }).fill('Dorure')
  await openSettings(page, 'Gabarit')
  await page.getByLabel('Gabarit à superposer').selectOption('pizza')
  const uploader = page.locator('.tool-uploader')
  await expect(uploader).toContainText('Déposer : Visuel 1')
  await page.getByLabel('Choisir les fichiers').setInputFiles('apps/web/public/exemple-carte.pdf')
  await expect(uploader).toContainText('Déposer : Visuel 2')
  await page.getByLabel('Choisir les fichiers').setInputFiles('apps/web/public/exemple-carte.pdf')
  await expect(uploader).toContainText('Déposer : Masque de finition : Dorure')
  await expect(uploader).toContainText('Pour : Visuel 1, Visuel 2.')
  await uploader.screenshot({ path: 'test-results/bat-upload-desktop.png' })
  await page.setViewportSize({ width: 390, height: 844 })
  await uploader.screenshot({ path: 'test-results/bat-upload-mobile.png' })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.setViewportSize({ width: 1280, height: 720 })
  const generate = page.getByRole('button', { name: 'Générer le fichier final', exact: true })
  await expect(generate).toBeDisabled()
  await expect(page.getByText('2 / 3 fichier(s) importé(s).', { exact: false })).toBeVisible()
  await page.getByLabel('Choisir les fichiers').setInputFiles('apps/web/public/exemple-carte.pdf')
  await expect(
    page.locator('.tool-file').filter({ hasText: 'Masque de finition : Dorure' }),
  ).toBeVisible()
  const response = page.waitForResponse((r) => r.url().includes('/api/tools/burger/run'))
  await generate.click()
  const result = await response
  expect(result.status(), await result.text()).toBe(201)
  const data = await result.json()
  expect(data.metrics.Finitions).toBe(1)
  expect(data.metrics['Pages du BAT']).toBe(3)
  expect(data.artifacts.some((a: { name: string }) => a.name === 'fiche-technique.pdf')).toBe(false)
  await expect(page.locator('.tool-success')).toBeVisible()
  await expect(page.locator('canvas[data-ready=true]')).toBeVisible()
})

test('Burger : couverture et intérieur peuvent être répartis en plusieurs fichiers', async ({
  page,
}) => {
  await page.goto('/?tool=burger')
  await page.getByLabel('Type de document').selectOption('brochure')
  await page.getByLabel('Nombre de fichiers visuels attendus').fill('5')
  await page.getByLabel('Fichiers pour la couverture').fill('4')
  await page.getByLabel('Pages intérieures attendues').fill('16')
  await expect(page.getByRole('listitem').filter({ hasText: 'Couverture' })).toHaveCount(4)
  await expect(page.getByRole('listitem').filter({ hasText: 'Intérieur' })).toHaveCount(1)
})

test('Burger : charger un exemple reprend le gabarit et les fichiers attendus', async ({
  page,
}) => {
  test.setTimeout(60_000)
  await page.goto('/?tool=burger')
  await page.getByLabel('Type de document').selectOption('card')
  await openSettings(page, 'Finitions et fichiers séparés')
  await page.getByRole('button', { name: 'Ajouter une finition' }).click()
  await page.getByLabel('Finition 1', { exact: true }).fill('Vernis')
  await openSettings(page, 'Gabarit')
  await page.getByLabel('Gabarit à superposer').selectOption('taco')
  await page.getByLabel('Largeur à plat', { exact: true }).fill('420')
  await page.getByLabel('Hauteur à plat', { exact: true }).fill('180')
  const exampleResponse = page.waitForResponse((r) => r.url().endsWith('/api/tools/burger/example'))
  await page.getByRole('button', { name: 'Charger un exemple' }).click()
  const example = await exampleResponse
  expect(example.status(), await example.text()).toBe(201)
  const exampleId = (await example.json()).id
  await expect(page.locator('.tool-upload-section .tool-file')).toHaveCount(3)
  await expect(page.locator('.tool-file').filter({ hasText: 'Recto' })).toBeVisible()
  await expect(page.locator('.tool-file').filter({ hasText: 'Verso' })).toBeVisible()
  await expect(
    page.locator('.tool-file').filter({ hasText: 'Masque de finition : Vernis' }),
  ).toBeVisible()
  const generate = page.getByRole('button', { name: 'Générer le fichier final', exact: true })
  await expect(generate).toBeEnabled()
  const resultResponse = page.waitForResponse((r) => r.url().endsWith('/api/tools/burger/run'))
  await generate.click()
  const result = await resultResponse
  expect(result.status(), await result.text()).toBe(201)
  const data = await result.json()
  expect(data.metrics.Faces).toBe(2)
  expect(data.metrics.Finitions).toBe(1)
  await expect(page.locator('canvas[data-ready=true]')).toBeVisible()
  const removed = await page.request.get(`/api/tool-jobs/${exampleId}`)
  expect(removed.status()).toBe(404)
})

test('Burger : le format attendu inclut le fond perdu sur les quatre côtés', async ({ page }) => {
  test.setTimeout(60_000)
  await page.goto('/?tool=burger')
  await openSettings(page, 'Gabarit')
  await page.getByLabel('Gabarit à superposer').selectOption('pizza')
  await page.getByLabel('Largeur finie', { exact: true }).fill('800')
  await page.getByLabel('Hauteur finie', { exact: true }).fill('2000')
  await expect(page.getByText(/Fichier attendu : 806 × 2\s?006 mm/)).toBeVisible()
  await page.getByLabel('Choisir les fichiers').setInputFiles('apps/web/public/exemple-carte.pdf')
  const generate = page.getByRole('button', { name: 'Générer le fichier final', exact: true })
  const failedResponse = page.waitForResponse((r) => r.url().endsWith('/api/tools/burger/run'))
  await generate.click()
  const failed = await failedResponse
  expect(failed.status()).toBe(422)
  expect(await failed.text()).toContain('806 × 2006')
  await page.getByRole('button', { name: 'Charger un exemple' }).click()
  await expect(page.locator('.tool-file strong')).toHaveText('exemple-1.pdf')
  await expect(generate).toBeEnabled()
  const response = page.waitForResponse((r) => r.url().endsWith('/api/tools/burger/run'))
  await generate.click()
  const result = await response
  expect(result.status(), await result.text()).toBe(201)
  await expect(page.locator('.tool-success')).toBeVisible()
})

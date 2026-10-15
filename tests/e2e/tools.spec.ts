import { test, expect } from '@playwright/test'

const tools = [
  ['burger', 'Burger', true],
  ['chili-dog', 'Chili Dog', true],
  ['donut', 'Donut', true],
  ['tiramisu', 'Tiramisu', true],
  ['taco', 'Taco', false],
  ['pizza', 'Pizza', false],
  ['burrito', 'Burrito', false],
  ['club-sandwich', 'Club Sandwich', false],
  ['fortune-cookie', 'Fortune Cookie', false],
  ['poke', 'Poké', true],
  ['sushi', 'Sushi', false],
  ['kebab', 'Kebab', false],
  ['layer-cake', 'Layer Cake', true],
  ['bento', 'Bento', true],
] as const

for (const [id, name, needsFile] of tools) {
  test(`${name} : réglages, traitement, aperçu et téléchargement`, async ({ page }) => {
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(e.message))
    await page.goto(`/?tool=${id}`)
    await expect(page.getByRole('heading', { name: `${name}.`, exact: true })).toBeVisible()
    if (needsFile) await page.getByRole('button', { name: 'Charger un exemple' }).click()
    if (id === 'fortune-cookie') await page.getByLabel('Nombre d’exemplaires').fill('3')
    if (id === 'sushi')
      await page.getByLabel('Rainages verticaux depuis le bord gauche').fill('20,60')
    await expect(page.locator('.tool-controls input:invalid')).toHaveCount(0)
    const response = page.waitForResponse((r) => r.url().includes(`/api/tools/${id}/run`))
    await page.getByRole('button', { name: 'Lancer l’outil', exact: true }).click()
    const result = await response
    expect(result.status(), await result.text()).toBe(201)
    await expect(page.locator('.tool-success')).toBeVisible()
    await expect(page.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
    if (id === 'tiramisu') {
      await page.getByLabel('Document à prévisualiser').selectOption('differences.pdf')
      await expect(page.locator('canvas[data-ready=true]')).toBeVisible()
    }
    if (id === 'burger')
      await page.screenshot({ path: 'test-results/burger-desktop.png', fullPage: true })
    const downloadEvent = page.waitForEvent('download')
    await page.locator('.artifact-downloads > a').first().click()
    expect((await downloadEvent).suggestedFilename()).toMatch(/^snackpress-/)
    await page.getByRole('button', { name: 'Supprimer ce travail' }).click()
    await expect(page.locator('.tool-empty')).toBeVisible()
    expect(errors).toEqual([])
  })
}

test('catalogue : tous les outils, recherche et filtre', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.tool-card')).toHaveCount(14)
  await page.screenshot({ path: 'test-results/catalogue-desktop.png', fullPage: true })
  await page.getByLabel('Rechercher un outil').fill('fusion')
  await expect(page.locator('.tool-card')).toHaveCount(1)
  await expect(page.locator('.tool-card h2')).toHaveText('Bento')
  await page.getByLabel('Rechercher un outil').fill('')
  await page.getByRole('button', { name: 'Tracer', exact: true }).click()
  await expect(page.locator('.tool-card')).toHaveCount(4)
  await page.getByLabel('Rechercher un outil').fill('zzzz')
  await expect(page.getByText('Aucun outil ne correspond.')).toBeVisible()
})

test('mobile : catalogue et calcul de dos', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await expect(page.locator('.tool-card')).toHaveCount(14)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/catalogue-mobile.png', fullPage: true })
  await page.getByRole('link', { name: /Club Sandwich/ }).click()
  const response = page.waitForResponse((r) => r.url().includes('/api/tools/club-sandwich/run'))
  await page.getByRole('button', { name: 'Lancer l’outil', exact: true }).click()
  expect((await response).status()).toBe(201)
  await expect(page.locator('.tool-success')).toContainText('6.90')
  await expect(page.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/club-mobile.png', fullPage: true })
})

test('livret piqué : huit pages et navigation du résultat', async ({ page }) => {
  await page.goto('/?tool=layer-cake')
  await page.getByLabel('Imposition', { exact: true }).selectOption('booklet')
  await page.getByRole('button', { name: 'Charger un exemple' }).click()
  const response = page.waitForResponse((r) => r.url().includes('/api/tools/layer-cake/run'))
  await page.getByRole('button', { name: 'Lancer l’outil', exact: true }).click()
  expect((await response).status()).toBe(201)
  await expect(page.locator('.tool-success')).toBeVisible()
  await expect(page.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
  await expect(page.locator('.page-navigation')).toContainText('1 / 4')
  await page.getByRole('button', { name: 'Page suivante' }).click()
  await expect(page.locator('.page-navigation')).toContainText('2 / 4')
  await page.getByRole('button', { name: 'Supprimer ce travail' }).click()
})

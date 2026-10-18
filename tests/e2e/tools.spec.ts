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

test('pizza : forme ronde et coins arrondis', async ({ page }) => {
  await page.goto('/?tool=pizza')
  await page.getByLabel('Rayon des coins', { exact: true }).fill('10')
  await page.getByLabel('Forme', { exact: true }).selectOption('circle')
  await expect(page.getByLabel('Hauteur finie', { exact: true })).toHaveCount(0)
  await expect(page.getByLabel('Rayon des coins', { exact: true })).toHaveCount(0)
  await page.getByLabel('Diamètre fini', { exact: true }).fill('70')
  const response = page.waitForResponse((r) => r.url().includes('/api/tools/pizza/run'))
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  const result = await response
  expect(result.status(), await result.text()).toBe(201)
  await expect(page.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
  await page.getByLabel('Forme', { exact: true }).selectOption('rectangle')
  await expect(page.getByLabel('Rayon des coins', { exact: true })).toHaveValue('10')
  await expect(page.getByLabel('Hauteur finie', { exact: true })).toBeVisible()
})

test('pizza : dimensions fixes ou bornées', async ({ page }) => {
  await page.goto('/?tool=pizza')
  const width = page.getByLabel('Largeur finie', { exact: true })
  await expect(page.getByLabel('Largeur minimale', { exact: true })).toHaveCount(0)
  await page.getByLabel('Réglage de la largeur', { exact: true }).selectOption('bounded')
  await page.getByLabel('Largeur minimale', { exact: true }).fill('50')
  await page.getByLabel('Largeur maximale', { exact: true }).fill('100')
  await width.fill('110')
  expect(await width.evaluate((el: HTMLInputElement) => el.validity.rangeOverflow)).toBe(true)
  await width.fill('70')
  await page.getByLabel('Réglage de la hauteur', { exact: true }).selectOption('bounded')
  await page.getByLabel('Hauteur minimale', { exact: true }).fill('40')
  await page.getByLabel('Hauteur maximale', { exact: true }).fill('90')
  await page.getByLabel('Hauteur finie', { exact: true }).fill('60')
  await page.screenshot({ path: 'test-results/pizza-bounds-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/pizza-bounds-mobile.png', fullPage: true })
  const response = page.waitForResponse((r) => r.url().includes('/api/tools/pizza/run'))
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  const result = await response
  expect(result.status(), await result.text()).toBe(201)
  const data = await result.json()
  expect(data.metrics['Largeur finie (mm)']).toBe(70)
  expect(data.metrics['Hauteur finie (mm)']).toBe(60)
  await page.getByLabel('Forme', { exact: true }).selectOption('circle')
  await expect(page.getByLabel('Réglage de la hauteur', { exact: true })).toHaveCount(0)
  await expect(page.getByLabel('Diamètre minimal', { exact: true })).toHaveValue('50')
  await page.getByLabel('Réglage du diamètre', { exact: true }).selectOption('fixed')
  await expect(page.getByLabel('Diamètre minimal', { exact: true })).toHaveCount(0)
  await page.getByLabel('Diamètre fini', { exact: true }).fill('120')
  expect(
    await page
      .getByLabel('Diamètre fini', { exact: true })
      .evaluate((el: HTMLInputElement) => el.checkValidity()),
  ).toBe(true)
})

test('pizza : sécurité et zones inexploitables par côté', async ({ page }) => {
  await page.goto('/?tool=pizza')
  for (const [label, value] of [
    ['Sécurité — haut', '3'],
    ['Sécurité — bas', '5'],
    ['Sécurité — gauche', '4'],
    ['Sécurité — droite', '6'],
    ['Zone inexploitable — haut', '7'],
    ['Zone inexploitable — bas', '3'],
    ['Zone inexploitable — gauche', '5'],
    ['Zone inexploitable — droite', '2'],
  ])
    await page.getByLabel(label, { exact: true }).fill(value)
  await expect(page.getByRole('group', { name: 'Zone de sécurité', exact: true })).toBeVisible()
  await expect(page.getByRole('group', { name: 'Zone inexploitable', exact: true })).toBeVisible()
  const response = page.waitForResponse((r) => r.url().includes('/api/tools/pizza/run'))
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  const result = await response
  expect(result.status(), await result.text()).toBe(201)
  const data = await result.json()
  const saved = await (
    await page.request.get(`/api/tool-jobs/${data.id}/files/reglages.json`)
  ).json()
  expect(saved.settings.safety_top).toBe(3)
  expect(saved.settings.safety_bottom).toBe(5)
  expect(saved.settings.unusable_left).toBe(5)
  await expect(page.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
  await page.screenshot({ path: 'test-results/pizza-zones-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/pizza-zones-mobile.png', fullPage: true })
})

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
    await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
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
    await expect(
      page.locator(id === 'fortune-cookie' ? '.fortune-preview' : '.live-preview'),
    ).toBeVisible()
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
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
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
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  expect((await response).status()).toBe(201)
  await expect(page.locator('.tool-success')).toBeVisible()
  await expect(page.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
  await expect(page.locator('.page-navigation')).toContainText('1 / 4')
  await page.getByRole('button', { name: 'Page suivante' }).click()
  await expect(page.locator('.page-navigation')).toContainText('2 / 4')
  await expect(page.locator('.pdf-viewer-footer')).toContainText('Page 2 sur 4')
  await page.getByRole('button', { name: 'Supprimer ce travail' }).click()
})

test('aperçu PDF : zoom, ajustement, plein écran et mobile', async ({ page }) => {
  await page.goto('/?tool=taco')
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  const canvas = page.locator('canvas[data-ready=true]')
  await expect(canvas).toBeVisible({ timeout: 15000 })
  await expect(page.locator('.pdf-viewer-footer')).toContainText('327 × 240 mm')
  const initialWidth = await canvas.evaluate((el) => el.getBoundingClientRect().width)
  await page.getByRole('button', { name: 'Agrandir le zoom', exact: true }).click()
  await expect(page.getByLabel('Zoom de l’aperçu')).toHaveText('125 %')
  await expect
    .poll(() => canvas.evaluate((el) => el.getBoundingClientRect().width))
    .toBeGreaterThan(initialWidth)
  await page.getByRole('button', { name: 'Ajuster à l’écran', exact: true }).click()
  await expect(page.getByLabel('Zoom de l’aperçu')).toHaveText('100 %')
  await page.getByRole('button', { name: 'Afficher en plein écran', exact: true }).click()
  await expect
    .poll(() => page.evaluate(() => document.fullscreenElement?.className))
    .toBe('pdf-viewer')
  await page.getByRole('button', { name: 'Quitter le plein écran', exact: true }).click()
  await expect(canvas).toBeVisible()
  await page.locator('.pdf-viewer').screenshot({ path: 'test-results/pdf-viewer-desktop.png' })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(canvas).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.locator('.pdf-viewer').screenshot({ path: 'test-results/pdf-viewer-mobile.png' })
})

test('aperçu PDF indisponible : téléchargement toujours accessible', async ({ page }) => {
  await page.route('**/api/tool-jobs/*/files/*.pdf', (route) => route.abort())
  await page.goto('/?tool=taco')
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  await expect(page.locator('.pdf-viewer-error')).toBeVisible({ timeout: 15000 })
  await expect(page.getByRole('link', { name: 'Télécharger le PDF', exact: true })).toBeVisible()
  await expect(page.locator('.artifact-downloads > a').first()).toBeVisible()
})

test('Fortune Cookie : plusieurs numérotations personnalisées et déplacement', async ({ page }) => {
  await page.goto('/?tool=fortune-cookie')
  await page.getByLabel('Nombre d’exemplaires').fill('2')
  await page.getByLabel('Code', { exact: true }).selectOption('none')
  await page.getByRole('button', { name: 'Ajouter une numérotation' }).click()
  const second = page.getByRole('group', { name: 'Numérotation 2', exact: true })
  await second.getByLabel('Position X').fill('35')
  await second.getByLabel('Position Y').fill('25')
  await second.getByLabel('Taille').fill('18')
  await second.getByLabel('Police').selectOption('Courier')
  await second.getByLabel('Couleur').fill('#ff0000')
  await second.getByLabel('Rotation').fill('45')
  const number = page.getByLabel('Déplacer la numérotation 2')
  await number.scrollIntoViewIfNeeded()
  const box = (await number.boundingBox())!
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width / 2 + 25, box.y + box.height / 2 + 10)
  await page.mouse.up()
  expect(Number(await second.getByLabel('Position X').inputValue())).toBeGreaterThan(35)
  await page.screenshot({ path: 'test-results/fortune-desktop.png', fullPage: true })
  const response = page.waitForResponse((r) => r.url().includes('/api/tools/fortune-cookie/run'))
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  const result = await response
  expect(result.status(), await result.text()).toBe(201)
  const request = result.request().postData()!
  expect(request).toContain('"font":"Courier"')
  expect(request).toContain('"rotation":45')
  await expect(page.locator('canvas[data-ready=true]')).toBeVisible()
  await page.getByRole('button', { name: 'Supprimer la numérotation 1', exact: true }).click()
  await expect(page.locator('.fortune-draggable')).toHaveCount(1)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: 'test-results/fortune-mobile.png', fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

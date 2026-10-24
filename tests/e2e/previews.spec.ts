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
  await openSettings(page, 'Production')
  await page.getByLabel('Nombre d’exemplaires').fill('12')
  await openSettings(page, 'Numérotation')
  await expect(page.getByLabel('Préfixe', { exact: true })).toHaveValue('')
  const live = page.getByLabel('Aperçu automatique', { exact: true })
  await expect(live.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
  await expect(live).toContainText('deux premiers exemplaires')
  await expect(page.getByLabel('Déplacer le repiquage 1')).toBeVisible()
  await openSettings(page, 'Repiquages')
  await expect(
    page.getByRole('group', { name: 'Repiquage 1', exact: true }).getByLabel('Couleur'),
  ).toHaveValue('#000000')
  await page
    .getByRole('group', { name: 'Repiquage 1', exact: true })
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

test('Fortune Cookie : produit, tracés combinés, composants et format conservé', async ({
  page,
}) => {
  test.setTimeout(90000)
  const library = await (await page.request.get('/api/print-catalog/starter')).json()
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({ json: { id: 'fortune-product-test', email: 'atelier@example.com' } }),
  )
  await page.route('**/api/configurations?tool_id=*', (route) => route.fulfill({ json: [] }))
  const product = library.catalog.products[0]
  product.name = 'Cartes atelier'
  const component = product.variants[0].components[0]
  Object.assign(component, {
    width: 100,
    height: 60,
    bleed: 4,
    guides: [
      { tool: 'pizza', settings: { shape: 'ellipse', safety: 5 } },
      { tool: 'burrito', settings: { hem: 5, inset: 5 } },
      { tool: 'taco', settings: { panels: 3 } },
      { tool: 'perforation', settings: { positions: [20] } },
    ],
  })
  const second = structuredClone(component)
  Object.assign(second, {
    id: 'sushi-face',
    name: 'Face Sushi',
    width: 80,
    height: 50,
    bleed: 2,
    guides: [
      {
        tool: 'sushi',
        settings: {
          shape: 'rectangle',
          lines: [{ kind: 'crease', axis: 'vertical', position: 30 }],
        },
      },
    ],
  })
  product.variants[0].components.push(second)
  await page.route('**/api/print-catalog/starter', (route) => route.fulfill({ json: library }))
  await page.route('**/api/print-catalog', (route) => route.fulfill({ json: library }))
  await page.goto('/?tool=fortune-cookie')
  const placement = page.getByLabel('Placement des repiquages sur le support')
  const guides = placement.locator('[data-fortune-product-guides]')
  await expect(page.getByLabel('Produit', { exact: true })).toHaveValue(product.id)
  await expect(page.getByLabel('Source du format')).toHaveCount(0)
  await expect(page.getByLabel('Largeur du support')).toHaveCount(0)
  await expect(page.getByText('Format fini : 100 × 60 mm')).toBeVisible()
  await expect(guides).toBeVisible({ timeout: 15000 })
  await expect(placement).toHaveAttribute('viewBox', '-15 -15 130 90')
  const live = page.getByLabel('Aperçu automatique', { exact: true })
  await expect(live.locator('.pdf-viewer-footer')).toContainText('100 × 60 mm', { timeout: 15000 })
  await expect(live).toContainText(
    'tracés du produit sont visibles uniquement dans l’aperçu de placement',
  )
  await openSettings(page, 'Repiquages')
  const number = page.getByLabel('Déplacer le repiquage 1')
  await number.scrollIntoViewIfNeeded()
  const numberBox = (await number.boundingBox())!
  const sheetBox = (await placement.boundingBox())!
  await page.mouse.move(numberBox.x + numberBox.width / 2, numberBox.y + numberBox.height / 2)
  await page.mouse.down()
  await page.mouse.move(
    numberBox.x + numberBox.width / 2 + (sheetBox.width * 10) / 130,
    numberBox.y + numberBox.height / 2 + (sheetBox.height * 5) / 90,
  )
  await page.mouse.up()
  expect(Number(await page.getByLabel('Position X').inputValue())).toBeCloseTo(16, 0)
  expect(Number(await page.getByLabel('Position Y').inputValue())).toBeCloseTo(54, 0)
  await page.screenshot({ path: 'test-results/fortune-product-guides.png', fullPage: true })
  await openSettings(page, 'Produit')
  await page.getByLabel('Composant à repiquer').selectOption('sushi-face')
  await expect(placement).toHaveAttribute('viewBox', '-2 -2 84 54', { timeout: 15000 })
  await page.getByLabel('Position Y').fill('40')
  await expect(live.locator('.pdf-viewer-footer')).toContainText('80 × 50 mm', { timeout: 15000 })
  await page.screenshot({ path: 'test-results/fortune-product-sushi.png', fullPage: true })
  await page.getByLabel('Composant à repiquer').selectOption(component.id)
  await openSettings(page, 'Production')
  await page.getByLabel('Nombre d’exemplaires').fill('3')
  const final = page.waitForResponse((r) => r.url().includes('/api/tools/fortune-cookie/run'))
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  const response = await final
  expect(response.status(), await response.text()).toBe(201)
  const result = await response.json()
  await expect(page.locator('.tool-result .pdf-viewer-footer')).toContainText('100 × 60 mm', {
    timeout: 15000,
  })
  await expect(page.locator('.artifact-downloads')).toContainText('3 pages')
  const config = await (
    await page.request.get(`/api/tool-jobs/${result.id}/files/reglages.json`)
  ).json()
  config.settings.width = 85
  config.settings.height = 55
  await page.route('**/api/configurations?tool_id=fortune-cookie', (route) =>
    route.fulfill({
      json: [
        {
          id: 'fortune-saved',
          tool_id: 'fortune-cookie',
          name: 'Cartes conservées',
          settings: config.settings,
          schema_version: 1,
          is_default: true,
          revision: 1,
          created_at: '2026-10-24T12:00:00',
          updated_at: '2026-10-24T12:00:00',
        },
      ],
    }),
  )
  await page.reload()
  await expect(page.getByText('Format fini : 100 × 60 mm')).toBeVisible()
  await expect(placement).toHaveAttribute('viewBox', '-15 -15 130 90', { timeout: 15000 })
  await expect(live.locator('.pdf-viewer-footer')).toContainText('100 × 60 mm', { timeout: 15000 })
  // A saved Pizza configuration keeps its format even after adopting products.
  config.settings = {
    count: 3,
    width: 85,
    height: 55,
    bleed: 3,
    pizza_template: { shape: 'circle', width: 100, height: 60, bleed: 4 },
  }
  await page.reload()
  await expect(page.getByText('Format fini : 100 × 100 mm')).toBeVisible()
  await expect(page.getByLabel('Produit', { exact: true })).toHaveValue('saved')
  await expect(placement).toHaveAttribute('viewBox', '-4 -4 108 108', { timeout: 15000 })
  await expect(live.locator('.pdf-viewer-footer')).toContainText('100 × 100 mm', { timeout: 15000 })
})

test('Fortune Cookie : Layer Cake et coupe en souches', async ({ page }) => {
  test.setTimeout(60000)
  const library = await (await page.request.get('/api/print-catalog/starter')).json()
  await page.route('**/api/print-catalog', (route) => route.fulfill({ json: library }))
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({ json: { id: 'fortune-layer-test', email: 'atelier@example.com' } }),
  )
  await page.route('**/api/configurations?tool_id=*', (route) => {
    const layer = new URL(route.request().url()).searchParams.get('tool_id') === 'layer-cake'
    return route.fulfill({
      json: layer
        ? [
            {
              id: 'four-up',
              name: 'Quatre poses',
              tool_id: 'layer-cake',
              settings: {
                mode: 'repeat',
                sheet_width: 210,
                sheet_height: 150,
                margin: 10,
                gap: 6,
                quantity: 999,
              },
              schema_version: 1,
              is_default: false,
              revision: 1,
              created_at: '2026-10-23T12:00:00',
              updated_at: '2026-10-23T12:00:00',
            },
            {
              id: 'booklet',
              name: 'Livret piqué',
              tool_id: 'layer-cake',
              settings: { mode: 'booklet' },
              schema_version: 1,
              is_default: false,
              revision: 1,
              created_at: '2026-10-23T12:00:00',
              updated_at: '2026-10-23T12:00:00',
            },
          ]
        : [],
    })
  })
  await page.goto('/?tool=fortune-cookie')
  await openSettings(page, 'Production')
  await page.getByLabel('Nombre d’exemplaires').fill('1000')
  await openSettings(page, 'Imposition en souches')
  const enabled = page.getByLabel('Imposer avec un gabarit Layer Cake')
  await enabled.check()
  await page.getByLabel('Charger une configuration').selectOption('four-up')
  await page.getByLabel('Billets par souche', { exact: true }).fill('10')
  const live = page.getByLabel('Aperçu automatique', { exact: true })
  await expect(live.locator('.pdf-viewer-footer')).toContainText('85 × 55 mm', { timeout: 15000 })
  await expect(live).toContainText('uniquement pour le téléchargement')
  await expect(live.locator('canvas[data-ready=true]')).toBeVisible()
  await page.screenshot({ path: 'test-results/fortune-souches-preview.png', fullPage: true })
  await page.getByLabel('Charger une configuration').selectOption('booklet')
  await expect(page.getByRole('alert')).toContainText('poses répétées')
  await page.getByLabel('Charger une configuration').selectOption('four-up')
  const final = page.waitForResponse((r) => r.url().includes('/api/tools/fortune-cookie/run'))
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  const response = await final
  expect(response.status(), await response.text()).toBe(201)
  const data = await response.json()
  expect(data.metrics['Feuilles à tirer']).toBe(250)
  expect(data.metrics['Souches']).toBe(100)
  expect(data.metrics['Billets']).toBe(1000)
  const manifestResponse = await page.request.get(
    `/api/tool-jobs/${data.id}/files/plan-souches.json`,
  )
  expect(manifestResponse.ok()).toBe(true)
  const manifest = await manifestResponse.json()
  expect(manifest.sheets[0]).toEqual(['0001', '0251', '0501', '0751'])
  const gathered = [0, 1, 2, 3].flatMap((pose) =>
    manifest.sheets.map((sheet: Array<string | null>) => sheet[pose]).filter(Boolean),
  )
  expect(gathered).toEqual(Array.from({ length: 1000 }, (_, i) => String(i + 1).padStart(4, '0')))
  await expect(page.locator('.tool-result .pdf-viewer-footer')).toContainText('Page 1 sur 1000', {
    timeout: 15000,
  })
  await expect(page.getByLabel('Document à prévisualiser')).toHaveCount(0)
  await expect(page.locator('.artifact-downloads')).toContainText('Plan de coupe')
  await expect(
    page.locator('.artifact-downloads a').filter({ hasText: 'Planche imposée pour coupe' }),
  ).toContainText('250 pages')
  await page.screenshot({ path: 'test-results/fortune-souches-final.png', fullPage: true })
  await enabled.uncheck()
  await expect(live).toContainText('deux premiers exemplaires', { timeout: 15000 })
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

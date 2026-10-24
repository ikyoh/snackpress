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

test('Fortune Cookie : configuration Pizza dans l’aperçu et export sans gabarit', async ({
  page,
}) => {
  test.setTimeout(60000)
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({ json: { id: 'fortune-template-test', email: 'atelier@example.com' } }),
  )
  await page.route('**/api/configurations?tool_id=*', (route) => {
    const pizza = new URL(route.request().url()).searchParams.get('tool_id') === 'pizza'
    return route.fulfill({
      json: pizza
        ? [
            {
              id: 'pizza-oval',
              tool_id: 'pizza',
              name: 'Cartes ovales',
              settings: {
                shape: 'ellipse',
                width: 100,
                height: 60,
                bleed: 4,
                safety: 5,
                unusable_left: 2,
              },
              schema_version: 1,
              is_default: true,
              revision: 1,
              created_at: '2026-10-23T12:00:00',
              updated_at: '2026-10-23T12:00:00',
            },
          ]
        : [],
    })
  })
  await page.goto('/?tool=fortune-cookie')
  await openSettings(page, 'Numérotation')
  await page.getByLabel('Nombre d’exemplaires').fill('3')
  const format = page.getByLabel('Source du format')
  await expect(format).toHaveValue('support')
  await expect(page.getByLabel('Largeur du support')).toHaveValue('85')
  await format.selectOption('pizza')
  await expect(page.getByLabel('Charger une configuration')).toHaveValue('')
  await expect(page.getByLabel('Largeur du support')).toHaveCount(0)
  await page.getByLabel('Charger une configuration').selectOption('pizza-oval')
  await expect(page.getByText('Format fini : 100 × 60 mm')).toBeVisible()
  await expect(page.getByLabel('Hauteur du support')).toHaveCount(0)
  const live = page.getByLabel('Aperçu automatique', { exact: true })
  await expect(live.locator('.pdf-viewer-footer')).toContainText('108 × 68 mm', { timeout: 15000 })
  await expect(live).toContainText('gabarit Pizza est visible uniquement ici')
  await expect(live.locator('canvas[data-ready=true]')).toBeVisible()
  await page.screenshot({ path: 'test-results/fortune-pizza-preview.png', fullPage: true })
  await format.selectOption('support')
  await expect(page.getByLabel('Largeur du support')).toBeEditable()
  await expect(page.getByLabel('Largeur du support')).toHaveValue('100')
  await expect(page.getByLabel('Hauteur du support')).toHaveValue('60')
  await expect(page.getByLabel('Fond perdu sur chaque côté')).toHaveValue('4')
  await expect(live.locator('.pdf-viewer-footer')).toContainText('108 × 68 mm', { timeout: 15000 })
  await format.selectOption('pizza')
  await page.getByLabel('Charger une configuration').selectOption('pizza-oval')
  await expect(live.locator('.pdf-viewer-footer')).toContainText('108 × 68 mm', { timeout: 15000 })
  const final = page.waitForResponse((r) => r.url().includes('/api/tools/fortune-cookie/run'))
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  const response = await final
  expect(response.status(), await response.text()).toBe(201)
  await expect(page.locator('.tool-result .pdf-viewer-footer')).toContainText('108 × 68 mm', {
    timeout: 15000,
  })
  await expect(page.locator('.artifact-downloads')).toContainText('3 pages')
  await page.screenshot({ path: 'test-results/fortune-pizza-final.png', fullPage: true })
  // Older Fortune configurations may still carry different manual support dimensions.
  await page.route('**/api/configurations?tool_id=fortune-cookie', (route) =>
    route.fulfill({
      json: [
        {
          id: 'fortune-saved',
          tool_id: 'fortune-cookie',
          name: 'Billets ronds',
          settings: {
            width: 85,
            height: 55,
            bleed: 3,
            count: 3,
            pizza_template: { shape: 'circle', width: 100, height: 60, bleed: 4 },
          },
          schema_version: 1,
          is_default: true,
          revision: 1,
          created_at: '2026-10-23T12:00:00',
          updated_at: '2026-10-23T12:00:00',
        },
      ],
    }),
  )
  await page.reload()
  await expect(format).toHaveValue('pizza')
  await expect(page.getByText('Format fini : 100 × 100 mm')).toBeVisible()
  await expect(page.getByLabel('Largeur du support')).toHaveCount(0)
  await expect(live.locator('.pdf-viewer-footer')).toContainText('108 × 108 mm', { timeout: 15000 })
})

test('Fortune Cookie : Layer Cake et coupe en souches', async ({ page }) => {
  test.setTimeout(60000)
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
  await openSettings(page, 'Numérotation')
  await page.getByLabel('Nombre d’exemplaires').fill('1000')
  await openSettings(page, 'Imposition en souches')
  const enabled = page.getByLabel('Imposer avec un gabarit Layer Cake')
  await enabled.check()
  await page.getByLabel('Charger une configuration').selectOption('four-up')
  await page.getByLabel('Billets par souche', { exact: true }).fill('10')
  const live = page.getByLabel('Aperçu automatique', { exact: true })
  await expect(live.locator('.pdf-viewer-footer')).toContainText('91 × 61 mm', { timeout: 15000 })
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
  expect(manifest.sheets[0]).toEqual(['SP-0001', 'SP-0251', 'SP-0501', 'SP-0751'])
  const gathered = [0, 1, 2, 3].flatMap((pose) =>
    manifest.sheets.map((sheet: Array<string | null>) => sheet[pose]).filter(Boolean),
  )
  expect(gathered).toEqual(
    Array.from({ length: 1000 }, (_, i) => `SP-${String(i + 1).padStart(4, '0')}`),
  )
  await expect(page.locator('.tool-result .pdf-viewer-footer')).toContainText('Page 1 sur 1000', {
    timeout: 15000,
  })
  await expect(page.getByLabel('Document à prévisualiser')).toHaveCount(0)
  await expect(page.locator('.artifact-downloads')).toContainText('Plan de coupe en souches')
  await expect(
    page.locator('.artifact-downloads a').filter({ hasText: 'Billets imposés' }),
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

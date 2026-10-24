import { expect, test } from '@playwright/test'
import { readdir, readFile } from 'node:fs/promises'
import { join } from 'node:path'

test('catalogue personnel : création, matières, déclinaison, rechargement et BAT libre enregistré', async ({
  page,
}) => {
  test.setTimeout(90_000)
  const email = 'produits@example.com'
  const headers = { 'X-Snackpress-Request': '1' }
  await page.goto('/')
  expect(
    (await page.request.post('/api/auth/register', { headers, data: { email } })).status(),
  ).toBe(200)
  let token = ''
  const mailbox = join(process.env.SNACKPRESS_ACCOUNT_TEST_DATA!, 'mail-outbox')
  for (const file of await readdir(mailbox)) {
    const message = (await readFile(join(mailbox, file), 'utf8'))
      .replace(/=\r?\n/g, '')
      .replace(/=([0-9A-F]{2})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))
    if (message.includes(`To: ${email}`)) token = message.match(/token=([A-Za-z0-9_-]+)/)?.[1] || ''
  }
  expect(token).not.toBe('')
  const password = 'Une longue phrase personnelle 2026'
  expect(
    (await page.request.post('/api/auth/verify', { headers, data: { token, password } })).status(),
  ).toBe(200)
  expect(
    (await page.request.post('/api/auth/login', { headers, data: { email, password } })).status(),
  ).toBe(200)
  const fixedResponse = await page.request.post('/api/configurations?tool_id=pizza', {
    headers,
    data: { name: 'Invitation fixe', settings: { width: 85, height: 55 } },
  })
  expect(fixedResponse.status()).toBe(201)
  const fixed = await fixedResponse.json()
  const boundedResponse = await page.request.post('/api/configurations?tool_id=pizza', {
    headers,
    data: {
      name: 'Invitation variable',
      settings: { width: 100, height: 55, width_mode: 'bounded', width_min: 90, width_max: 150 },
    },
  })
  expect(boundedResponse.status()).toBe(201)
  const bounded = await boundedResponse.json()
  await page.goto('/?view=products')
  await expect(page.getByRole('button', { name: 'Mon compte', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Ajouter un produit', exact: true }).click()
  await page.getByLabel('Nom du produit', { exact: true }).fill('Invitation atelier')
  await page.getByLabel('Nom de la déclinaison', { exact: true }).fill('Petit format')
  await page.getByLabel('Support matière', { exact: true }).selectOption('mat350')
  await expect(
    page.getByLabel('Ajouter un tracé', { exact: true }).locator('option[value=sushi]'),
  ).toHaveCount(1)
  await page
    .getByLabel('Gabarit Pizza', { exact: true })
    .selectOption(`${fixed.id}:${fixed.revision}`)
  await expect(page.getByLabel('Largeur finie (mm)', { exact: true })).toHaveCount(0)
  await expect(page.getByLabel('Hauteur finie (mm)', { exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Dupliquer la déclinaison' }).click()
  await page.getByLabel('Nom de la déclinaison', { exact: true }).fill('Grand format')
  await page
    .getByLabel('Gabarit Pizza', { exact: true })
    .selectOption(`${bounded.id}:${bounded.revision}`)
  await page.screenshot({ path: 'test-results/product-pizza-template-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/product-pizza-template-mobile.png', fullPage: true })
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.getByRole('button', { name: 'Enregistrer le catalogue', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Catalogue enregistré')
  await page.reload()
  await page.getByRole('button', { name: 'Invitation atelier' }).click()
  await expect(page.getByLabel('Déclinaison à modifier').locator('option')).toHaveCount(2)
  await page.goto('/?tool=burger')
  await page.getByLabel('Mode du BAT').selectOption('catalog')
  const productId = await page
    .getByLabel('Produit', { exact: true })
    .getByRole('option', { name: 'Invitation atelier' })
    .getAttribute('value')
  await page.getByLabel('Produit', { exact: true }).selectOption(productId!)
  await expect(page.getByLabel('Déclinaison du produit').locator('option')).toHaveCount(2)
  await expect(page.getByLabel('Largeur finie (mm)', { exact: true })).toHaveCount(0)
  await page.getByLabel('Déclinaison du produit').selectOption({ label: 'Grand format' })
  const width = page.getByLabel('Largeur finie (mm)', { exact: true })
  await expect(width).toHaveAttribute('min', '90')
  await expect(width).toHaveAttribute('max', '150')
  await width.fill('120')
  await expect(page.getByLabel('Hauteur finie (mm)', { exact: true })).toHaveCount(0)
  await page.getByLabel('Mode du BAT').selectOption('free')
  await page.getByLabel('Nom du produit pour ce BAT').fill('Libre sauvegardé')
  await page.getByRole('button', { name: 'Enregistrer comme nouveau produit' }).click()
  await expect(page.locator('.print-selector').getByRole('status')).toContainText(
    'Produit enregistré',
  )
  await page.goto('/?view=products')
  await expect(page.getByRole('button', { name: 'Libre sauvegardé' })).toBeVisible()
  await page.getByRole('button', { name: 'Ajouter un produit', exact: true }).click()
  await page.getByLabel('Nom du produit', { exact: true }).fill('Carte Sushi')
  await page.getByLabel('Support matière', { exact: true }).selectOption('mat350')
  await page
    .getByLabel('Gabarit Pizza', { exact: true })
    .selectOption(`${fixed.id}:${fixed.revision}`)
  await page.getByLabel('Ajouter un tracé', { exact: true }).selectOption('perforation')
  await expect(
    page.getByLabel('Ajouter un tracé', { exact: true }).locator('option[value=sushi]'),
  ).toHaveText('Sushi — découpe et rainage — remplace Pizza')
  await page.getByLabel('Ajouter un tracé', { exact: true }).selectOption('sushi')
  await expect(page.getByLabel('Outil de découpe', { exact: true })).toHaveValue('sushi')
  await expect(page.getByLabel('Gabarit Pizza', { exact: true })).toHaveCount(0)
  await expect(page.getByLabel('Sens des perforations')).toHaveValue('vertical')
  await expect(page.getByLabel('Largeur finie (mm)', { exact: true })).toHaveValue('85')
  await expect(page.getByLabel('Fond perdu attendu (mm)')).toHaveValue('3')
  await page.getByLabel('Contour', { exact: true }).selectOption('circle')
  await page.getByLabel('Diamètre fini (mm)').fill('90')
  await page.getByLabel('Contour', { exact: true }).selectOption('rectangle')
  await expect(page.getByLabel('Hauteur finie (mm)', { exact: true })).toHaveValue('90')
  await page.getByLabel('Largeur finie (mm)', { exact: true }).fill('85')
  await page.getByLabel('Hauteur finie (mm)', { exact: true }).fill('55')
  await page.getByLabel('Rayon des coins (mm)').fill('5')
  for (const [index, [kind, axis, position]] of [
    ['crease', 'vertical', '20'],
    ['cut', 'horizontal', '15'],
  ].entries()) {
    await page.getByRole('button', { name: 'Ajouter un tracé', exact: true }).click()
    await page.getByLabel(`Type du tracé ${index + 1}`, { exact: true }).selectOption(kind)
    await page.getByLabel(`Orientation du tracé ${index + 1}`, { exact: true }).selectOption(axis)
    await page.getByLabel(`Position du tracé ${index + 1}`, { exact: true }).fill(position)
  }
  await page.getByRole('button', { name: 'Enregistrer le catalogue', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Catalogue enregistré')
  await page.reload()
  await page.getByRole('button', { name: 'Carte Sushi' }).click()
  await expect(page.getByLabel('Outil de découpe', { exact: true })).toHaveValue('sushi')
  await expect(page.getByLabel('Rayon des coins (mm)')).toHaveValue('5')
  await expect(page.getByLabel('Position du tracé 2', { exact: true })).toHaveValue('15')
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  expect((await page.locator('.sushi-lines').boundingBox())!.width).toBeGreaterThan(200)
  await page
    .locator('.sushi-lines')
    .screenshot({ path: 'test-results/product-sushi-lines-mobile.png' })
  await page.screenshot({ path: 'test-results/product-sushi-mobile.png', fullPage: true })
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto('/?tool=burger')
  await page.getByLabel('Mode du BAT').selectOption('catalog')
  await page.getByLabel('Produit', { exact: true }).selectOption({ label: 'Carte Sushi' })
  await page.getByLabel('Choisir les fichiers').setInputFiles('apps/web/public/exemple-fond.pdf')
  const proofResponse = page.waitForResponse((r) => r.url().includes('/api/tools/burger/run'))
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  const proof = await proofResponse
  expect(proof.status(), await proof.text()).toBe(201)
  const job = await proof.json()
  const settings = await page.request.get(`/api/tool-jobs/${job.id}/files/reglages.json`)
  const component = (await settings.json()).settings.product_snapshot.variant.components[0]
  expect(component.pizza_template).toBeNull()
  expect(component.guides.map((g: { tool: string }) => g.tool)).toEqual(['perforation', 'sushi'])
  expect(component.guides[1].settings).toMatchObject({
    width: 85,
    height: 55,
    bleed: 3,
    shape: 'rectangle',
    corner_radius: 5,
    lines: [
      { kind: 'crease', axis: 'vertical', position: 20 },
      { kind: 'cut', axis: 'horizontal', position: 15 },
    ],
  })
  const guide = job.artifacts.find((a: { name: string }) => a.name.includes('traces'))
  expect(guide).toBeDefined()
  expect((await page.request.get(`/api/tool-jobs/${job.id}/files/${guide.name}`)).status()).toBe(
    200,
  )
  await page.goto('/?view=products')
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  await page.getByRole('button', { name: 'Façonnages et finitions', exact: true }).click()
  await page.getByRole('button', { name: 'Ajouter une finition' }).click()
  await expect(page.locator('.accordion-trigger')).toHaveCount(7)
  await expect(page.getByLabel('Nom de la finition')).toHaveValue('Nouvelle finition')
  await expect(page.locator('.accordion-trigger[aria-expanded="true"]')).toHaveCount(1)
  await page.getByLabel('Nom de la finition').fill('Finition modifiée')
  await page.locator('.accordion-trigger').first().click()
  await expect(
    page.getByRole('button', { name: 'Finition modifiée', exact: true }),
  ).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByLabel('Nom de la finition')).toHaveCount(1)
  await page.getByRole('button', { name: 'Finition modifiée', exact: true }).click()
  await expect(page.getByLabel('Nom de la finition')).toHaveValue('Finition modifiée')
  await page.getByRole('button', { name: 'Finition modifiée', exact: true }).click()
  await expect(page.getByLabel('Nom de la finition')).toHaveCount(0)
  expect(errors).toEqual([])
})

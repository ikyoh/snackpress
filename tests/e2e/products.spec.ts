import { expect, test } from '@playwright/test'

test('formes de façonnage : dimensions et occurrences dans les produits', async ({ page }) => {
  await page.goto('/?view=products')
  await page.getByRole('button', { name: 'Façonnages et finitions', exact: true }).click()
  await page.getByRole('button', { name: 'Perforation', exact: true }).click()
  await page.getByLabel('Représentation sur le BAT').selectOption('circle')
  await page.getByLabel('Diamètre (mm)', { exact: true }).fill('6')
  await expect(page.locator('.finish-appearance-sample')).toHaveCSS('border-radius', '50%')
  await page.getByRole('button', { name: 'Agrafage', exact: true }).click()
  await page.getByLabel('Représentation sur le BAT').selectOption('rectangle')
  await page.getByLabel('Largeur (mm)', { exact: true }).fill('12')
  await page.getByLabel('Hauteur (mm)', { exact: true }).fill('3')
  await page.getByRole('button', { name: 'Produits', exact: true }).click()
  await page.getByRole('button', { name: /Billet détachable numéroté/ }).click()
  const positions = page.getByRole('region', { name: 'Positions des façonnages' })
  const first = positions.getByRole('group', { name: 'Perforation — occurrence 1', exact: true })
  await first.getByLabel('X depuis la gauche (mm)').fill('5')
  await first.getByLabel('Y depuis le haut (mm)').fill('10')
  await first.getByRole('button', { name: 'Dupliquer cette occurrence' }).click()
  const second = positions.getByRole('group', { name: 'Perforation — occurrence 2', exact: true })
  await expect(second.getByLabel('X depuis la gauche (mm)')).toHaveValue('5')
  await second.getByLabel('X depuis la gauche (mm)').fill('100')
  await second.getByLabel('Page d’application').selectOption('1')
  await positions.getByRole('button', { name: 'Ajouter une occurrence de Perforation' }).click()
  await positions
    .getByRole('group', { name: 'Perforation — occurrence 3', exact: true })
    .getByRole('button', { name: 'Retirer cette occurrence' })
    .click()
  await expect(positions.getByRole('group')).toHaveCount(2)
  await page
    .getByRole('group', { name: 'Options et finitions sélectionnées' })
    .getByLabel('Agrafage', { exact: true })
    .check()
  await expect(positions.getByRole('heading', { name: 'Agrafage — 12 × 3 mm' })).toBeVisible()
  await page.getByRole('button', { name: /Carte recto verso/ }).click()
  await page.getByRole('button', { name: /Billet détachable numéroté/ }).click()
  await expect(second.getByLabel('X depuis la gauche (mm)')).toHaveValue('100')
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await positions.screenshot({ path: 'test-results/finish-shapes-product-mobile.png' })
})

test('formes de façonnage : occurrences dans l’outil BAT et réglages figés', async ({ page }) => {
  await page.route('**/api/print-catalog/starter', async (route) => {
    const response = await route.fetch()
    const library = await response.json()
    for (const finish of library.catalog.finishes) {
      if (finish.id === 'perforation')
        Object.assign(finish.appearance, { mode: 'circle', diameter: 6 })
      if (finish.id === 'staple')
        Object.assign(finish.appearance, { mode: 'rectangle', width: 12, height: 3 })
    }
    library.catalog.products[0].finish_ids = ['perforation', 'staple']
    library.catalog.products = [library.catalog.products[0]]
    await route.fulfill({ response, json: library })
  })
  await page.goto('/?tool=burger')
  await page.getByLabel('Mode du BAT').selectOption('catalog')
  await page.getByLabel('Perforation', { exact: true }).check()
  await page.getByLabel('Agrafage', { exact: true }).check()
  const positions = page.getByRole('region', { name: 'Positions des façonnages' })
  const first = positions.getByRole('group', { name: 'Perforation — occurrence 1', exact: true })
  await first.getByLabel('X depuis la gauche (mm)').fill('5')
  await first.getByLabel('Y depuis le haut (mm)').fill('7')
  await first.getByLabel('Page d’application').selectOption('1')
  await first.getByRole('button', { name: 'Dupliquer cette occurrence' }).click()
  await positions
    .getByRole('group', { name: 'Perforation — occurrence 2', exact: true })
    .getByLabel('X depuis la gauche (mm)')
    .fill('65')
  const staple = positions.getByRole('group', { name: 'Agrafage — occurrence 1', exact: true })
  await staple.getByLabel('X depuis la gauche (mm)').fill('30')
  await staple.getByLabel('Y depuis le haut (mm)').fill('20')
  await staple.getByLabel('Page d’application').selectOption('2')
  const appearance = page.getByRole('region', { name: 'Apparence des finitions sur le BAT' })
  await appearance.getByRole('button', { name: 'Perforation — Forme ronde' }).click()
  await expect(appearance.getByLabel('Diamètre (mm)')).toHaveValue('6')
  await appearance.getByLabel('Diamètre (mm)').fill('8')
  await appearance.getByRole('button', { name: 'Agrafage — Forme rectangulaire' }).click()
  await expect(appearance.getByLabel('Largeur (mm)')).toHaveValue('12')
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await positions.screenshot({ path: 'test-results/finish-shapes-bat-mobile.png' })
  await page.setViewportSize({ width: 1280, height: 900 })
  await positions.screenshot({ path: 'test-results/finish-shapes-bat-desktop.png' })
  await expect(page.locator('.print-selector ol li')).toHaveCount(2)
  for (let i = 0; i < 2; i++) {
    await page.getByLabel('Choisir les fichiers').setInputFiles('apps/web/public/exemple-fond.pdf')
  }
  const response = page.waitForResponse((r) => r.url().includes('/api/tools/burger/run'))
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  const result = await response
  expect(result.status(), await result.text()).toBe(201)
  const job = await result.json()
  const settings = await page.request.get(`/api/tool-jobs/${job.id}/files/reglages.json`)
  const snapshot = (await settings.json()).settings.product_snapshot
  expect(snapshot.variant.finish_placements).toEqual([
    { finish_id: 'perforation', component_id: 'card', x: 5, y: 7, page: 1 },
    { finish_id: 'staple', component_id: 'card', x: 30, y: 20, page: 2 },
    { finish_id: 'perforation', component_id: 'card', x: 65, y: 7, page: 1 },
  ])
  expect(
    snapshot.finishes.find((f: { id: string }) => f.id === 'perforation').appearance.diameter,
  ).toBe(8)
})

test('assistant produit : validation, retours, annulation et création recto verso', async ({
  page,
}) => {
  await page.goto('/?view=products')
  await page.getByRole('button', { name: 'Ajouter un produit', exact: true }).click()
  await page.getByLabel('Nom du produit', { exact: true }).fill('Produit abandonné')
  await page.getByRole('button', { name: 'Annuler la création' }).click()
  await expect(page.getByRole('button', { name: 'Produit abandonné' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Ajouter un produit', exact: true }).click()
  const assistant = page.getByRole('region', { name: 'Assistant de création de produit' })
  await expect(page.getByLabel('Nom de la déclinaison')).toHaveCount(0)
  await expect(page.getByLabel('Nom du composant')).toHaveCount(0)
  await page.getByRole('button', { name: 'Continuer', exact: true }).click()
  await expect(assistant.getByRole('heading', { name: 'Produit', exact: true })).toBeVisible()
  expect(
    await page
      .getByLabel('Nom du produit', { exact: true })
      .evaluate((input: HTMLInputElement) => input.validity.valueMissing),
  ).toBe(true)
  await page.getByLabel('Nom du produit', { exact: true }).fill('Carte guidée')
  await page.getByLabel('Nom du produit', { exact: true }).press('Enter')
  await expect(
    assistant.getByRole('heading', { name: 'Format et papier', exact: true }),
  ).toBeFocused()
  await page.getByLabel('Largeur finie (mm)', { exact: true }).fill('100')
  await page.getByLabel('Hauteur finie (mm)', { exact: true }).fill('70')
  await page.getByLabel('Support matière', { exact: true }).selectOption('mat350')
  await test.info().attach('wizard-desktop-layout', {
    contentType: 'application/json',
    body: JSON.stringify(
      await assistant.evaluate((element) => {
        const body = element.querySelector('.print-wizard-body > p')!
        const format = element.querySelector('.print-wizard-format')!
        const style = getComputedStyle(body)
        const layout = getComputedStyle(format)
        return {
          fontSize: style.fontSize,
          color: style.color,
          background: getComputedStyle(element).backgroundColor,
          gap: layout.gap,
          columns: layout.gridTemplateColumns,
        }
      }),
    ),
  })
  await page.screenshot({ path: 'test-results/product-wizard-format-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await test.info().attach('wizard-mobile-layout', {
    contentType: 'application/json',
    body: JSON.stringify(
      await assistant.evaluate((element) => {
        const layout = getComputedStyle(element.querySelector('.print-wizard-format')!)
        return {
          width: element.getBoundingClientRect().width,
          gap: layout.gap,
          columns: layout.gridTemplateColumns,
        }
      }),
    ),
  })
  await page.screenshot({ path: 'test-results/product-wizard-format-mobile.png', fullPage: true })
  await page.getByRole('button', { name: 'Continuer', exact: true }).click()
  await page.getByLabel('Fichiers PDF attendus', { exact: true }).selectOption('combined')
  await expect(
    page.getByLabel('Ajouter un tracé', { exact: true }).locator('option[value=perforation]'),
  ).toHaveCount(0)
  await page.getByLabel('Ajouter un tracé', { exact: true }).selectOption('sushi')
  await page.getByLabel('Contour', { exact: true }).selectOption('circle')
  await page.getByRole('button', { name: 'Précédent', exact: true }).click()
  await expect(page.getByLabel('Diamètre fini (mm)')).toHaveValue('100')
  await page.getByLabel('Diamètre fini (mm)').fill('85')
  await page.getByRole('button', { name: 'Continuer', exact: true }).click()
  await expect(page.getByLabel('Fichiers PDF attendus', { exact: true })).toHaveValue('combined')
  await expect(page.getByLabel('Contour', { exact: true })).toHaveValue('circle')
  await page.getByLabel('Contour', { exact: true }).selectOption('rectangle')
  await page.getByRole('button', { name: 'Ajouter un tracé', exact: true }).click()
  await page.getByLabel('Position du tracé 1', { exact: true }).fill('20')
  await page.getByRole('button', { name: 'Continuer', exact: true }).click()
  await page.getByRole('button', { name: 'Modifier le format et le papier', exact: true }).click()
  await expect(page.getByLabel('Hauteur finie (mm)', { exact: true })).toHaveValue('85')
  await page.getByLabel('Hauteur finie (mm)', { exact: true }).fill('55')
  await page.getByRole('button', { name: 'Continuer', exact: true }).click()
  await expect(page.getByLabel('Position du tracé 1', { exact: true })).toHaveValue('20')
  await page.getByRole('button', { name: 'Continuer', exact: true }).click()
  await expect(page.getByText('85 × 55 mm', { exact: true })).toBeVisible()
  await expect(page.getByText('Recto verso · 1 PDF de deux pages', { exact: true })).toBeVisible()
  await page.screenshot({ path: 'test-results/product-wizard-review-mobile.png', fullPage: true })
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.screenshot({ path: 'test-results/product-wizard-review-desktop.png', fullPage: true })
  await page.getByRole('button', { name: 'Créer le produit', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Produit ajouté au catalogue temporaire')
  await expect(page.getByLabel('Nom du produit', { exact: true })).toHaveValue('Carte guidée')
  await expect(page.getByLabel('Pages attendues', { exact: true })).toHaveValue('2')
  await expect(page.getByLabel('Position du tracé 1', { exact: true })).toHaveValue('20')
})

test('apparence des finitions : zone, alpha, dégradé et tracé bicolore', async ({ page }) => {
  await page.goto('/?view=products')
  await page.getByRole('button', { name: 'Façonnages et finitions', exact: true }).click()
  await page.locator('.accordion-trigger').first().click()
  const mode = page.getByLabel('Représentation sur le BAT')
  await expect(mode).toHaveValue('none')
  await mode.selectOption('area')
  await page.getByLabel('Couleur', { exact: true }).fill('#123456')
  await page.getByLabel('Opacité (alpha, %)').fill('25')
  await page.getByLabel('Créer un dégradé').check()
  await page.getByLabel('Couleur d’arrivée').fill('#abcdef')
  for (const [index, position] of [25, 50, 75].entries()) {
    await expect(page.getByLabel(`Position de l’étape ${index + 2} (%)`)).toHaveValue(`${position}`)
  }
  for (const [index, [color, position]] of [
    ['#ff0000', '12'],
    ['#00ff00', '47'],
    ['#0000ff', '83'],
  ].entries()) {
    await page.getByLabel(`Couleur de l’étape ${index + 2}`).fill(color)
    await page.getByLabel(`Position de l’étape ${index + 2} (%)`).fill(position)
  }
  await expect(page.locator('.finish-appearance-sample')).toHaveCSS(
    'background-image',
    /rgb\(0, 255, 0\) 47%/,
  )
  await page.getByLabel('Position de l’étape 3 (%)').fill('95')
  await expect(page.getByLabel('Position de l’étape 3 (%)')).toHaveValue('83')
  await page.getByLabel('Position de l’étape 3 (%)').fill('47')
  await page.getByLabel('Angle du dégradé (°)').fill('45')
  await expect(page.locator('.finish-appearance-sample')).toHaveCSS('opacity', '0.25')
  await page.screenshot({ path: 'test-results/finish-appearance-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/finish-appearance-mobile.png', fullPage: true })
  await mode.selectOption('path')
  await expect(page.getByLabel('Opacité (alpha, %)')).toHaveCount(0)
  await expect(page.getByLabel('Créer un dégradé')).toHaveCount(0)
  await expect(page.getByLabel('Couleur du tracé', { exact: true })).toHaveValue('#123456')
  await expect(page.getByLabel('Couleur du pointillé', { exact: true })).toHaveValue('#ffffff')
  await page.getByLabel('Couleur du pointillé', { exact: true }).fill('#fce300')
  const strokes = page.locator('.finish-appearance-path rect')
  await expect(strokes.nth(0)).toHaveAttribute('stroke', '#123456')
  await expect(strokes.nth(1)).toHaveAttribute('stroke', '#fce300')
  await expect(strokes.nth(1)).toHaveAttribute('stroke-dasharray', '8 4')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/finish-path-mobile.png', fullPage: true })
  await page.setViewportSize({ width: 1280, height: 720 })
  await page.screenshot({ path: 'test-results/finish-path-desktop.png', fullPage: true })
  await mode.selectOption('none')
  await expect(page.locator('.finish-appearance-preview')).toHaveCount(0)
  await mode.selectOption('area')
  await expect(page.getByLabel('Couleur d’arrivée')).toHaveValue('#abcdef')
  await expect(page.getByLabel('Couleur de l’étape 3')).toHaveValue('#00ff00')
  await expect(page.getByLabel('Position de l’étape 3 (%)')).toHaveValue('47')
  await expect(page.getByLabel('Opacité (alpha, %)')).toHaveValue('25')
  await mode.selectOption('path')
  await expect(page.getByLabel('Couleur du pointillé', { exact: true })).toHaveValue('#fce300')
})

test('catalogue produit : dégradé à cinq étapes, BAT et spécifications figées', async ({
  page,
}) => {
  test.setTimeout(60_000)
  await page.goto('/?tool=burger')
  await page.getByLabel('Mode du BAT').selectOption('catalog')
  await expect(page.getByLabel('Produit', { exact: true })).toHaveValue('card')
  await expect(page.getByText('Fichier attendu : 91 × 61 mm.', { exact: true })).toBeVisible()
  await page.getByLabel('Vernis sélectif', { exact: true }).check()
  const appearance = page.getByRole('region', { name: 'Apparence des finitions sur le BAT' })
  await appearance.getByRole('button', { name: 'Vernis sélectif — Aucun effet' }).click()
  await appearance.getByLabel('Représentation sur le BAT').selectOption('area')
  await appearance.getByLabel('Couleur', { exact: true }).fill('#ff0000')
  await appearance.getByLabel('Opacité (alpha, %)').fill('35')
  await appearance.getByLabel('Créer un dégradé').check()
  await appearance.getByLabel('Couleur d’arrivée').fill('#ffff00')
  await appearance.getByLabel('Couleur de l’étape 2').fill('#ff0000')
  await appearance.getByLabel('Position de l’étape 2 (%)').fill('12')
  await appearance.getByLabel('Couleur de l’étape 3').fill('#00ff00')
  await appearance.getByLabel('Position de l’étape 3 (%)').fill('47')
  await appearance.getByLabel('Couleur de l’étape 4').fill('#0000ff')
  await appearance.getByLabel('Position de l’étape 4 (%)').fill('83')
  await appearance.getByLabel('Représentation sur le BAT').selectOption('path')
  await appearance.getByLabel('Couleur du pointillé').fill('#0000ff')
  await appearance.getByLabel('Représentation sur le BAT').selectOption('area')
  await appearance.screenshot({ path: 'test-results/bat-finish-settings-desktop.png' })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await appearance.screenshot({ path: 'test-results/bat-finish-settings-mobile.png' })
  await page.setViewportSize({ width: 1280, height: 720 })
  await expect(page.locator('.print-selector ol li')).toHaveCount(3)
  const uploader = page.locator('.tool-uploader')
  await expect(uploader).toContainText('Déposer : Carte — Recto')
  await page.getByLabel('Choisir les fichiers').setInputFiles('apps/web/public/exemple-fond.pdf')
  await expect(uploader).toContainText('Déposer : Carte — Verso')
  await page.getByLabel('Choisir les fichiers').setInputFiles('apps/web/public/exemple-fond.pdf')
  await expect(uploader).toContainText('Déposer : Carte — Masque de finition : Vernis sélectif')
  await expect(uploader).toContainText('Pour : Recto, Verso. 2 pages, dans l’ordre des visuels.')
  await page.getByLabel('Choisir les fichiers').setInputFiles('apps/web/public/exemple-carte.pdf')
  const response = page.waitForResponse((r) => r.url().includes('/api/tools/burger/run'))
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  const result = await response
  expect(result.status(), await result.text()).toBe(201)
  const data = await result.json()
  expect(data.metrics.Composants).toBe(1)
  for (const item of data.artifacts) {
    expect((await page.request.get(`/api/tool-jobs/${data.id}/files/${item.name}`)).status()).toBe(
      200,
    )
  }
  const settings = await page.request.get(`/api/tool-jobs/${data.id}/files/reglages.json`)
  const frozen = (await settings.json()).settings.product_snapshot
  expect(frozen.variant.finish_ids).toEqual(['varnish'])
  expect(frozen.finishes.find((f: { id: string }) => f.id === 'varnish').appearance).toMatchObject({
    mode: 'area',
    color: '#ff0000',
    dash_color: '#0000ff',
    alpha: 0.35,
    gradient: true,
    end_color: '#ffff00',
    gradient_stops: [
      { color: '#ff0000', position: 12 },
      { color: '#00ff00', position: 47 },
      { color: '#0000ff', position: 83 },
    ],
  })
  await expect(page.locator('.tool-success')).toBeVisible()
})

test('billet numéroté : perforation, série, BAT premier et dernier, mode libre', async ({
  page,
}) => {
  await page.goto('/?tool=burger')
  await page.getByLabel('Mode du BAT').selectOption('catalog')
  await page.getByLabel('Catégorie de produit').selectOption('tickets')
  await expect(page.getByLabel('Produit', { exact: true })).toHaveValue('ticket')
  await page.getByLabel('Adapter les spécifications pour ce BAT').check()
  await page.getByLabel('Largeur finie (mm)', { exact: true }).fill('85')
  await page.getByLabel('Hauteur finie (mm)', { exact: true }).fill('55')
  await page.getByLabel('Quantité de billets (100 maximum)').fill('3')
  await page.getByLabel('Préfixe', { exact: true }).fill('T-')
  await page.getByLabel('Suffixe', { exact: true }).fill('-A')
  for (const input of await page.getByLabel('Position Y (mm)', { exact: true }).all())
    await input.fill('45')
  await page.getByLabel('Choisir les fichiers').setInputFiles('apps/web/public/exemple-fond.pdf')
  const response = page.waitForResponse((r) => r.url().includes('/api/tools/burger/run'))
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  const result = await response
  expect(result.status(), await result.text()).toBe(201)
  const data = await result.json()
  expect(data.metrics['Pages du BAT']).toBe(5)
  const series = data.artifacts.find((a: { name: string }) => a.name.includes('serie-billets'))
  expect(series.pages).toBe(3)
  expect((await page.request.get(`/api/tool-jobs/${data.id}/files/${series.name}`)).status()).toBe(
    200,
  )
  await page.getByLabel('Mode du BAT').selectOption('free')
  await expect(page.getByLabel('Nom du produit pour ce BAT')).toHaveValue('Produit sur mesure')
  await page.getByLabel('Ajouter un tracé').selectOption('taco')
  await page.getByLabel('Ajouter un tracé').selectOption('pizza')
  await page.getByLabel('Ajouter un tracé', { exact: true }).selectOption('sushi')
  await expect(
    page.getByRole('group', { name: 'Sushi — découpe et rainage', exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('group', { name: 'Pizza — coupe et sécurité', exact: true }),
  ).toBeVisible()
  await expect(page.getByLabel('Contour', { exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Ajouter un tracé', exact: true }).click()
  await page.getByLabel('Position du tracé 1', { exact: true }).fill('10')
  await page
    .getByRole('group', { name: 'Pizza — coupe et sécurité', exact: true })
    .getByRole('button', { name: 'Retirer ce tracé', exact: true })
    .click()
  await page.getByLabel('Contour', { exact: true }).selectOption('rectangle')
  await page.getByLabel('Ajouter un tracé', { exact: true }).selectOption('pizza')
  await expect(page.getByLabel('Contour', { exact: true })).toHaveCount(0)
  await expect(page.getByLabel('Position du tracé 1', { exact: true })).toHaveValue('10')
  await expect(
    page.getByRole('group', { name: 'Taco — plis et panneaux', exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Enregistrer comme nouveau produit' }),
  ).toBeVisible()
})

test('catalogue : bibliothèques, catégories et mobile', async ({ page }) => {
  await page.goto('/?view=products')
  await expect(page.getByRole('heading', { name: 'Produits d’impression.' })).toBeVisible()
  await page.getByRole('button', { name: 'Billet détachable numéroté' }).click()
  await expect(page.getByLabel('Quantité de billets (100 maximum)')).toHaveValue('50')
  await page.screenshot({ path: 'test-results/print-catalog-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/print-catalog-mobile.png', fullPage: true })
  await page.getByRole('button', { name: 'Supports matières', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'Bibliothèque des supports matières' }),
  ).toBeVisible()
  const supports = page.locator('.accordion-trigger')
  await expect(page.getByLabel('Nom du support')).toHaveCount(0)
  await supports.nth(0).click()
  await expect(supports.nth(0)).toHaveAttribute('aria-expanded', 'true')
  await page.getByLabel('Nom du support').fill('Support modifié')
  await supports.nth(1).click()
  await expect(supports.nth(0)).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByLabel('Nom du support')).toHaveCount(1)
  await supports.nth(0).click()
  await expect(page.getByLabel('Nom du support')).toHaveValue('Support modifié')
  await supports.nth(0).click()
  await expect(page.getByLabel('Nom du support')).toHaveCount(0)
  await page.getByRole('button', { name: 'Ajouter un support', exact: true }).click()
  await expect(page.getByLabel('Nom du support')).toHaveValue('Nouveau support')
  await expect(page.locator('.accordion-trigger[aria-expanded="true"]')).toHaveCount(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('button', { name: 'Catégories', exact: true }).click()
  await page.getByRole('button', { name: 'Ajouter une catégorie' }).click()
  await expect(page.getByLabel('Nom de la catégorie')).toHaveCount(9)
  await expect(page.getByRole('button', { name: 'Enregistrer le catalogue' })).toBeDisabled()
})

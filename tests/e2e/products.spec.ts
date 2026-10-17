import { expect, test } from '@playwright/test'

test('catalogue produit : carte, masque de finition, BAT et spécifications figées', async ({
  page,
}) => {
  await page.goto('/?tool=burger')
  await page.getByLabel('Mode du BAT').selectOption('catalog')
  await expect(page.getByLabel('Produit', { exact: true })).toHaveValue('card')
  await page.getByLabel('Vernis sélectif', { exact: true }).check()
  await expect(page.locator('.print-selector ol li')).toHaveCount(3)
  await page
    .getByLabel('Choisir les fichiers')
    .setInputFiles([
      'apps/web/public/exemple-fond.pdf',
      'apps/web/public/exemple-fond.pdf',
      'apps/web/public/exemple-carte.pdf',
    ])
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
  expect((await settings.json()).settings.product_snapshot.variant.finish_ids).toEqual(['varnish'])
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
  expect(data.metrics['Pages du BAT']).toBe(4)
  const series = data.artifacts.find((a: { name: string }) => a.name.includes('serie-billets'))
  expect(series.pages).toBe(3)
  expect((await page.request.get(`/api/tool-jobs/${data.id}/files/${series.name}`)).status()).toBe(
    200,
  )
  await page.getByLabel('Mode du BAT').selectOption('free')
  await expect(page.getByLabel('Nom du produit pour ce BAT')).toHaveValue('Produit sur mesure')
  await page.getByLabel('Ajouter un tracé').selectOption('taco')
  await page.getByLabel('Ajouter un tracé').selectOption('pizza')
  await expect(page.getByLabel('Ajouter un tracé').locator('option[value=sushi]')).toHaveCount(0)
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

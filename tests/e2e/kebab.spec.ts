import { expect, test } from '@playwright/test'

test('Kebab : produit, fiche PDF et lien de partage', async ({ page, browser }) => {
  await page.goto('/?tool=kebab')
  await expect(page.getByLabel('Produit', { exact: true })).toHaveValue('card')
  await expect(page.getByLabel('Mode du BAT')).toHaveCount(0)
  await expect(page.getByLabel('Papier', { exact: true })).toHaveCount(0)
  await page.getByLabel('Produit', { exact: true }).selectOption('brochure')
  await expect(page.getByText('Couverture — format fini', { exact: false })).toBeVisible()
  await expect(page.getByText('Intérieur — format fini', { exact: false })).toBeVisible()
  const response = page.waitForResponse((r) => r.url().includes('/api/tools/kebab/run'))
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  const generated = await response
  expect(generated.status(), await generated.text()).toBe(201)
  const result = await generated.json()
  const settings = await (
    await page.request.get(`/api/tool-jobs/${result.id}/files/reglages.json`)
  ).json()
  expect(settings.settings.product_snapshot.product_name).toBe('Brochure agrafée')
  expect(settings.settings.product_snapshot.variant.components).toHaveLength(2)
  await expect(page.locator('.artifact-stage canvas[data-ready=true]')).toBeVisible()
  const share = page.getByRole('region', { name: 'Partager le PDF', exact: true })
  const url = await share.getByLabel('Lien de partage').inputValue()
  expect(url).toMatch(/\/api\/tool-jobs\/[a-f0-9]+\/files\/fiche-fabrication.pdf$/)
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write'])
  await share.getByRole('button', { name: 'Copier le lien du PDF' }).click()
  await expect(share.getByRole('status')).toHaveText('Lien copié.')
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(url)
  const visitor = await browser.newContext()
  try {
    const pdf = await visitor.request.get(url)
    expect(pdf.status()).toBe(200)
    expect(pdf.headers()['content-type']).toBe('application/pdf')
    expect((await pdf.body()).subarray(0, 5).toString()).toBe('%PDF-')
  } finally {
    await visitor.close()
  }
  await page.screenshot({ path: 'test-results/kebab-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('tab', { name: 'Aperçu', exact: true }).click()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/kebab-mobile.png', fullPage: true })
  const deletion = page.waitForResponse(
    (r) => r.url().endsWith(`/api/tool-jobs/${result.id}`) && r.request().method() === 'DELETE',
  )
  await page.getByRole('button', { name: 'Supprimer ce travail' }).click()
  expect((await deletion).status()).toBe(204)
  await expect(share).toHaveCount(0)
})

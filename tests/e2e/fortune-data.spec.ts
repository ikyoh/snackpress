import { test, expect } from '@playwright/test'
import { openSettings } from './settings'

test('Fortune Cookie : repiquages CSV, alignements, codes-barres et configuration enregistrée', async ({
  page,
}) => {
  test.setTimeout(90000)
  let saved: Record<string, unknown> | null = null
  const library = await (await page.request.get('/api/print-catalog/starter')).json()
  await page.route('**/api/print-catalog', (route) => route.fulfill({ json: library }))
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({ json: { id: 'fortune-csv', email: 'atelier@example.com' } }),
  )
  await page.route('**/api/configurations?tool_id=*', (route) =>
    route.fulfill({
      json: saved
        ? [
            {
              id: 'csv-preset',
              tool_id: 'fortune-cookie',
              name: 'Invitations CSV',
              settings: saved,
              schema_version: 1,
              is_default: true,
              revision: 1,
              created_at: '2026-10-24T12:00:00',
              updated_at: '2026-10-24T12:00:00',
            },
          ]
        : [],
    }),
  )
  await page.goto('/?tool=fortune-cookie')
  await openSettings(page, 'Données CSV')
  await page.getByLabel('Importer un CSV', { exact: true }).setInputFiles({
    name: 'invitations.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(
      'nom;reference;ean\nÉlodie;00017;590123412345\nZoé;00018;5901234123457\nAlice;00019;4006381333931\n',
    ),
  })
  await expect(page.getByText('3 lignes chargées')).toBeVisible()
  await expect(page.getByLabel('Nombre d’exemplaires')).toHaveValue('3')
  await openSettings(page, 'Repiquages')
  const first = page.getByRole('group', { name: 'Repiquage 1', exact: true })
  await first.getByLabel('Source du repiquage').selectOption('csv')
  await first.getByLabel('Colonne CSV').selectOption('nom')
  await first.getByLabel('Alignement').selectOption('center')
  await first.getByLabel('Position X').fill('42')
  await first.getByLabel('Position Y').fill('12')
  const text = page.getByLabel('Déplacer le repiquage 1').locator('text')
  await expect(text).toContainText('Élodie')
  await expect(text).toHaveAttribute('text-anchor', 'middle')
  await first.getByLabel('Alignement').selectOption('right')
  await expect(text).toHaveAttribute('text-anchor', 'end')
  await first.getByLabel('Alignement').selectOption('left')
  await expect(text).toHaveAttribute('text-anchor', 'start')
  await first.getByLabel('Alignement').selectOption('center')
  for (const [index, column, kind, x, y] of [
    [2, 'reference', 'code128', 5, 32],
    [3, 'ean', 'ean13', 80, 50],
  ] as const) {
    await page.getByRole('button', { name: 'Ajouter un repiquage', exact: true }).click()
    const item = page.getByRole('group', { name: `Repiquage ${index}`, exact: true })
    await item.getByLabel('Source du repiquage').selectOption('csv')
    await item.getByLabel('Colonne CSV').selectOption(column)
    await item.getByLabel('Rendu du repiquage').selectOption(kind)
    await item.getByLabel('Position X').fill(String(x))
    await item.getByLabel('Position Y').fill(String(y))
    if (index === 3) await item.getByLabel('Alignement').selectOption('right')
  }
  await expect(
    page.getByLabel('Code-barres Code 128', { exact: true }).locator('rect'),
  ).not.toHaveCount(0)
  await expect(
    page.getByLabel('Code-barres EAN-13', { exact: true }).locator('rect'),
  ).not.toHaveCount(0)
  await expect(page.getByLabel('Déplacer le repiquage 2').locator('text')).toHaveText('00017')
  await expect(page.getByLabel('Déplacer le repiquage 3').locator('text')).toHaveText(
    '5901234123457',
  )
  for (const label of ['Code-barres Code 128', 'Code-barres EAN-13']) {
    const symbol = page.getByLabel(label, { exact: true })
    const frame = (await symbol.boundingBox())!
    const bar = (await symbol.locator('rect').last().boundingBox())!
    expect(bar.height / frame.height).toBeGreaterThan(0.95)
  }
  const live = page.getByLabel('Aperçu automatique', { exact: true })
  await expect(live.locator('.pdf-viewer-footer')).toContainText('85 × 55 mm', { timeout: 15000 })
  await expect(live.getByRole('status').filter({ hasText: 'Aperçu à jour' })).toBeVisible({
    timeout: 15000,
  })
  await page.screenshot({ path: 'test-results/fortune-csv-preview.png', fullPage: true })
  const final = page.waitForResponse((r) => r.url().includes('/api/tools/fortune-cookie/run'))
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  const response = await final
  expect(response.status(), await response.text()).toBe(201)
  await expect(page.locator('.artifact-downloads')).toContainText('3 pages')
  const request = response.request().postData()!
  expect(request).toContain('00017')
  expect(request).toContain('"align":"center"')
  const result = await response.json()
  const config = await page.request.get(`/api/tool-jobs/${result.id}/files/reglages.json`)
  saved = (await config.json()).settings
  await page.reload()
  await openSettings(page, 'Repiquages')
  await expect(first.getByLabel('Source du repiquage')).toHaveValue('csv')
  await expect(first.getByLabel('Alignement')).toHaveValue('center')
  await expect(text).toContainText('Élodie')
  await expect(
    page.getByRole('group', { name: 'Repiquage 3', exact: true }).getByLabel('Rendu du repiquage'),
  ).toHaveValue('ean13')
})

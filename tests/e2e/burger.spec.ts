import { test, expect } from '@playwright/test'

test('Burger : fichiers attendus, finition séparée et repères Pizza', async ({ page }) => {
  await page.goto('/?tool=burger')
  await page.getByLabel('Nombre de fichiers visuels attendus').fill('2')
  await page.getByRole('button', { name: 'Ajouter une finition' }).click()
  await page.getByLabel('Finition 1', { exact: true }).fill('Dorure')
  await page.getByLabel('Gabarit à superposer').selectOption('pizza')
  await page
    .getByLabel('Choisir les fichiers')
    .setInputFiles(['apps/web/public/exemple-carte.pdf', 'apps/web/public/exemple-carte.pdf'])
  const generate = page.getByRole('button', { name: 'Générer le fichier final', exact: true })
  await expect(generate).toBeDisabled()
  await expect(page.getByText('2 / 3 fichier(s) importé(s).', { exact: false })).toBeVisible()
  await page.getByLabel('Choisir les fichiers').setInputFiles('apps/web/public/exemple-carte.pdf')
  await expect(page.locator('.tool-file').filter({ hasText: 'Finition : Dorure' })).toBeVisible()
  const response = page.waitForResponse((r) => r.url().includes('/api/tools/burger/run'))
  await generate.click()
  const result = await response
  expect(result.status(), await result.text()).toBe(201)
  const data = await result.json()
  expect(data.metrics.Finitions).toBe(1)
  expect(data.metrics['Pages du BAT']).toBe(10)
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

import { test, expect } from '@playwright/test'

test('import, géométrie, verso, export et suppression', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  await page.goto('/?tool=imposition')
  await expect(page.getByText('Tout commence par votre PDF.')).toBeVisible()
  await page.getByRole('button', { name: 'Essayer avec une carte exemple' }).click()
  await expect(page.getByText('Exemple — Studio Papier.pdf')).toBeVisible()
  await expect(page.getByRole('img', { name: /Recto : 21 poses/ })).toBeVisible()
  await page.getByRole('tab', { name: 'Verso', exact: true }).click()
  await expect(page.getByRole('img', { name: /Verso : 21 poses/ })).toBeVisible()
  await page.getByLabel('Quantité souhaitée').fill('500')
  await expect(page.getByText('+ 4 de marge')).toBeVisible()
  await page.getByRole('button', { name: 'Générer le PDF' }).click()
  await expect(page.getByRole('link', { name: 'Télécharger le PDF' })).toBeVisible()
  await expect(page.locator('canvas.pdf-canvas[data-ready=true]')).toBeVisible()
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('link', { name: 'Télécharger le PDF' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe('snackpress-output.pdf')
  await page.screenshot({ path: 'test-results/atelier-desktop.png', fullPage: true })
  await page.getByRole('button', { name: 'Supprimer le document' }).click()
  await expect(page.getByText('Tout commence par votre PDF.')).toBeVisible()
  expect(errors).toEqual([])
})

test('mobile, aide et modèle local', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/?tool=imposition')
  await page.getByRole('button', { name: 'Mode d’emploi' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await page.getByText('Mes modèles', { exact: true }).click()
  await page.getByRole('textbox', { name: 'Nom du modèle' }).fill('Presse SRA3')
  await page.getByRole('button', { name: 'Enregistrer le modèle' }).click()
  await page.reload()
  await page.getByText('Mes modèles', { exact: true }).click()
  await expect(
    page.getByLabel('Charger un modèle').locator('option', { hasText: 'Presse SRA3' }),
  ).toHaveCount(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  await page.screenshot({ path: 'test-results/atelier-mobile.png', fullPage: true })
})

import { test, expect } from '@playwright/test'
import { openSettings } from './settings'

for (const mobile of [false, true]) {
  test(`Pizza : la saisie conserve le panneau ouvert (${mobile ? 'mobile' : 'bureau'})`, async ({
    page,
  }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/?tool=pizza')
    const live = page.getByLabel('Aperçu automatique', { exact: true })
    if (mobile) await page.getByRole('tab', { name: 'Aperçu', exact: true }).click()
    await expect(live.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
    if (mobile) await page.getByRole('tab', { name: 'Réglages', exact: true }).click()

    // An unfinished value in another panel must not interrupt the current edit.
    await page.getByLabel('Largeur finie', { exact: true }).fill('2500')
    const safety = page.getByRole('button', { name: 'Zone de sécurité', exact: true })
    await safety.click()
    const top = page.getByLabel('Sécurité — haut', { exact: true })
    await top.fill('6')
    await expect(live.getByRole('alert', { includeHidden: true })).toContainText(
      'Corrigez les réglages',
    )
    await expect(safety).toHaveAttribute('aria-expanded', 'true')
    await expect(top).toBeFocused()
    await page.getByLabel('Sécurité — bas', { exact: true }).fill('5')
    await expect(safety).toContainText('H 6 · B 5')

    // Explicit submission still reveals and focuses the invalid field.
    await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Format', exact: true })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    await expect(page.getByLabel('Largeur finie', { exact: true })).toBeFocused()
  })
}

test('Taco : l’aperçu conserve les panneaux et le focus pendant les modifications', async ({
  page,
}) => {
  await page.goto('/?tool=taco')
  const live = page.getByLabel('Aperçu automatique', { exact: true })
  await expect(live.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
  await page.getByLabel('Largeur à plat', { exact: true }).fill('2500')
  const format = page
    .locator('details.settings-section')
    .filter({ has: page.getByText('Format', { exact: true }) })
  await format.locator('summary').click()
  await openSettings(page, 'Pliage')
  const panels = page.getByLabel('Nombre de panneaux', { exact: true })
  await panels.fill('4')
  await expect(live.getByRole('alert', { includeHidden: true })).toContainText(
    'Corrigez les réglages',
  )
  await expect(format).not.toHaveAttribute('open')
  await expect(panels).toBeFocused()
  await page.getByLabel('Retrait du panneau rentrant', { exact: true }).fill('3')
  await expect(panels).toHaveValue('4')
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  await expect(format).toHaveAttribute('open', '')
  await expect(page.getByLabel('Largeur à plat', { exact: true })).toBeFocused()
})

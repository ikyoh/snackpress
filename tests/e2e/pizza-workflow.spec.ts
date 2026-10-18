import { test, expect } from '@playwright/test'

test.setTimeout(60_000)

for (const mobile of [false, true]) {
  test(`Pizza : réglages communs, côtés indépendants et export (${mobile ? 'mobile' : 'bureau'})`, async ({
    page,
  }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/?tool=pizza')
    await expect(page.getByLabel('Réglage de la largeur', { exact: true })).toBeHidden()
    await page.getByRole('button', { name: 'Zone de sécurité', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Format', exact: true })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    const common = page.getByLabel('Sécurité — tous les côtés', { exact: true })
    await common.fill('5')
    const safety = page.locator('[data-pizza-section=safety]')
    await safety.getByRole('checkbox').check()
    for (const side of ['haut', 'bas', 'gauche', 'droite'])
      await expect(page.getByLabel(`Sécurité — ${side}`, { exact: true })).toHaveValue('5')
    await page.getByLabel('Sécurité — droite', { exact: true }).fill('8')
    await expect(safety).toContainText('H 5 · B 5 · G 5 · D 8 mm')
    await safety.getByRole('checkbox').uncheck()
    await expect(common).toHaveValue('5')
    await safety.getByRole('checkbox').check()
    await expect(page.getByLabel('Sécurité — droite', { exact: true })).toHaveValue('5')
    await page.getByLabel('Sécurité — droite', { exact: true }).fill('7')
    await page.getByRole('button', { name: 'Zone inexploitable', exact: true }).click()
    await page.getByLabel('Zone inexploitable — tous les côtés', { exact: true }).fill('2')
    // The last focused setting remains identifiable after switching mobile tabs.
    if (mobile) await page.getByRole('tab', { name: 'Aperçu', exact: true }).click()
    await expect(page.locator('[data-pizza-highlight=unusable_all]')).toBeVisible({
      timeout: 15000,
    })
    await expect(page.locator('.pdf-overlay-label')).toContainText(
      'Zone inexploitable — tous les côtés',
    )
    await page.getByLabel('Document de l’aperçu automatique').selectOption('legende.pdf')
    await expect(page.locator('.pdf-overlay')).toHaveCount(0)
    await page.getByLabel('Document de l’aperçu automatique').selectOption('gabarit.pdf')
    await expect(page.locator('[data-pizza-highlight=unusable_all]')).toBeVisible({
      timeout: 15000,
    })
    if (mobile) await page.getByRole('tab', { name: 'Réglages', exact: true }).click()
    const response = page.waitForResponse((r) => r.url().includes('/api/tools/pizza/run'))
    await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
    const result = await response
    expect(result.status(), await result.text()).toBe(201)
    const data = await result.json()
    const saved = await (
      await page.request.get(`/api/tool-jobs/${data.id}/files/reglages.json`)
    ).json()
    expect(saved.settings.safety_right).toBe(7)
    expect(saved.settings.safety_left).toBe(5)
    for (const side of ['top', 'bottom', 'left', 'right'])
      expect(saved.settings[`unusable_${side}`]).toBe(2)
    expect(saved.settings).not.toHaveProperty('safety_all')
    expect(saved.settings).not.toHaveProperty('unusable_all')
  })
}

test('Pizza : erreurs locales, reprise de saisie et limites avancées', async ({ page }) => {
  await page.goto('/?tool=pizza')
  const radius = page.getByLabel('Rayon des coins', { exact: true })
  await radius.fill('30')
  await expect(radius).toHaveAttribute('aria-invalid', 'true')
  await expect(page.locator('.field-error')).toContainText('27,5 mm')
  await radius.fill('10')
  await expect(radius).not.toHaveAttribute('aria-invalid')
  await page.getByRole('button', { name: 'Zone de sécurité', exact: true }).click()
  const common = page.getByLabel('Sécurité — tous les côtés', { exact: true })
  await common.fill('28')
  await expect(common).toHaveAttribute('aria-invalid', 'true')
  await expect(page.locator('.field-error')).toContainText('moins de 55 mm')
  await common.fill('')
  await expect(page.locator('.field-error')).toContainText('Renseignez une valeur')
  await expect(common).toBeFocused()
  await common.fill('4')
  await expect(page.locator('.field-error')).toHaveCount(0)
  await page.locator('.pizza-dimension-limits > summary').click()
  await page.getByLabel('Réglage de la largeur').selectOption('bounded')
  await page.getByLabel('Largeur minimale', { exact: true }).fill('90')
  await expect(page.getByLabel('Largeur finie', { exact: true })).toHaveAttribute(
    'aria-invalid',
    'true',
  )
  await page.getByLabel('Largeur finie', { exact: true }).fill('100')
  await page.getByLabel('Largeur maximale', { exact: true }).fill('80')
  await expect(page.getByLabel('Largeur maximale', { exact: true })).toHaveAttribute(
    'aria-invalid',
    'true',
  )
  await page.getByLabel('Largeur maximale', { exact: true }).fill('3000')
  await page.locator('.pizza-dimension-limits > summary').click()
  await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
  // Submission reveals advanced errors without closing the other panels.
  await expect(page.getByLabel('Largeur maximale', { exact: true })).toBeFocused()
  await expect(page.getByRole('button', { name: 'Zone de sécurité', exact: true })).toHaveAttribute(
    'aria-expanded',
    'true',
  )
  await page.getByLabel('Largeur maximale', { exact: true }).fill('120')
  await expect(page.locator('.field-error')).toHaveCount(0)
  await expect(page.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
})

test('Pizza : une configuration asymétrique et bornée conserve toutes ses valeurs', async ({
  page,
}) => {
  // Isolate saved-settings behavior without creating an account in the local database.
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({ json: { id: 'pizza-test', email: 'pizza@example.com' } }),
  )
  await page.route('**/api/configurations?tool_id=pizza', (route) =>
    route.fulfill({
      json: [
        {
          id: 'asymmetric',
          name: 'Gabarit asymétrique',
          is_default: true,
          settings: {
            shape: 'rectangle',
            width: 100,
            height: 60,
            bleed: 3,
            corner_radius: 0,
            width_mode: 'bounded',
            width_min: 90,
            width_max: 150,
            height_mode: 'fixed',
            safety_top: 3,
            safety_bottom: 4,
            safety_left: 5,
            safety_right: 6,
            unusable_top: 0,
            unusable_bottom: 0,
            unusable_left: 0,
            unusable_right: 0,
          },
        },
      ],
    }),
  )
  await page.goto('/?tool=pizza')
  await expect(page.getByLabel('Largeur finie', { exact: true })).toHaveValue('100')
  await expect(page.getByLabel('Largeur minimale', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Largeur minimale', { exact: true })).toHaveValue('90')
  await page.getByRole('button', { name: 'Zone de sécurité', exact: true }).click()
  await expect(page.locator('[data-pizza-section=safety]').getByRole('checkbox')).toBeChecked()
  await expect(page.getByLabel('Sécurité — haut', { exact: true })).toHaveValue('3')
  await expect(page.getByLabel('Sécurité — droite', { exact: true })).toHaveValue('6')
  await page.getByLabel('Largeur finie', { exact: true }).fill('110')
  await expect(page.getByLabel('Sécurité — droite', { exact: true })).toHaveValue('6')
})

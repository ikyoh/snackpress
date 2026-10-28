import { test, expect } from '@playwright/test'

test.setTimeout(60_000)

for (const mobile of [false, true]) {
  test(`Pizza : tester un fichier et revenir au gabarit (${mobile ? 'mobile' : 'bureau'})`, async ({
    page,
  }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/?tool=pizza')
    await page.getByLabel('Largeur finie', { exact: true }).fill('100')
    await page.getByLabel('Hauteur finie', { exact: true }).fill('60')
    await page.getByLabel('Fond perdu', { exact: true }).fill('4')
    await page.getByRole('button', { name: 'Zone de sécurité', exact: true }).press('Enter')
    await page.locator('[data-pizza-section=safety]').getByRole('checkbox').check()
    await page.getByLabel('Sécurité — droite', { exact: true }).fill('7')
    await page.getByRole('button', { name: 'Zone inexploitable', exact: true }).press('Enter')
    await page.getByLabel('Zone inexploitable — tous les côtés', { exact: true }).fill('2')
    const launch = page.getByRole('button', { name: 'Tester un fichier avec ce gabarit' })
    await launch.scrollIntoViewIfNeeded()
    await page.screenshot({
      path: `test-results/pizza-launch-${mobile ? 'mobile' : 'desktop'}.png`,
      fullPage: true,
    })
    await launch.click()
    await expect(page).toHaveURL('/?tool=burger')
    await expect(page.getByRole('heading', { name: 'Tester un fichier' })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Gabarit à tester' })).toContainText(
      '108 × 68 mm',
    )
    await expect(page.getByLabel('Mode du BAT')).toHaveCount(0)
    await expect(page.getByLabel('Gabarit à superposer')).toHaveCount(0)
    // The transferred settings survive a reload without a saved configuration.
    await page.reload()
    await expect(page.getByRole('heading', { name: 'Tester un fichier' })).toBeVisible()
    await page.screenshot({
      path: `test-results/pizza-test-import-${mobile ? 'mobile' : 'desktop'}.png`,
      fullPage: true,
    })
    await page.getByLabel('Choisir les fichiers').setInputFiles('apps/web/public/exemple-carte.pdf')
    if (mobile) await expect(page.getByRole('tab', { name: 'Aperçu', exact: true })).toBeFocused()
    await expect(page.locator('.live-preview-error')).toContainText('format incompatible', {
      timeout: 15_000,
    })
    await expect(page.getByText('Format et fond perdu du PDF conformes au gabarit.')).toHaveCount(0)
    if (mobile) await page.getByRole('tab', { name: 'Réglages', exact: true }).click()
    const exampleResponse = page.waitForResponse((response) =>
      response.url().endsWith('/api/tools/burger/example'),
    )
    await page.getByRole('button', { name: 'Charger un exemple' }).click()
    const example = await exampleResponse
    expect(example.status(), await example.text()).toBe(201)
    const renderResponse = await page.waitForResponse(
      (response) =>
        response.url().endsWith('/render') &&
        response.request().postDataJSON()?.settings?.template_tool === 'pizza' &&
        response.status() === 200,
    )
    const transferred = renderResponse.request().postDataJSON().settings
    expect(transferred.template_settings).toMatchObject({
      width: 100,
      height: 60,
      bleed: 4,
      safety_right: 7,
      unusable_left: 2,
    })
    expect(transferred.expected_files).toBe(1)
    expect(transferred.finishes).toEqual([])
    if (mobile) await page.getByRole('tab', { name: 'Aperçu', exact: true }).click()
    await expect(page.getByText('Format et fond perdu du PDF conformes au gabarit.')).toBeVisible()
    await expect(page.locator('.page-navigation')).toContainText('2 / 3')
    await expect(page.locator('canvas[data-ready=true]')).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({
      path: `test-results/pizza-file-test-${mobile ? 'mobile' : 'desktop'}.png`,
      fullPage: true,
    })
    if (mobile) await page.getByRole('tab', { name: 'Réglages', exact: true }).click()
    const finalResponse = page.waitForResponse((response) =>
      response.url().endsWith('/api/tools/burger/run'),
    )
    await page.getByRole('button', { name: 'Générer le BAT', exact: true }).click()
    const final = await finalResponse
    expect(final.status(), await final.text()).toBe(201)
    const job = await final.json()
    const saved = await (
      await page.request.get(`/api/tool-jobs/${job.id}/files/reglages.json`)
    ).json()
    expect(saved.settings.template_settings).toMatchObject({
      width: 100,
      height: 60,
      bleed: 4,
      safety_right: 7,
      unusable_right: 2,
    })
    await expect(page.locator('.page-navigation')).toContainText('2 / 3')
    if (mobile) await page.getByRole('tab', { name: 'Réglages', exact: true }).click()
    await page.getByRole('button', { name: 'Revenir au gabarit Pizza' }).click()
    await expect(page).toHaveURL('/?tool=pizza')
    await expect(page.getByLabel('Largeur finie', { exact: true })).toHaveValue('100')
    await page.getByRole('button', { name: 'Zone de sécurité', exact: true }).click()
    await expect(page.getByLabel('Sécurité — droite', { exact: true })).toHaveValue('7')
    await page.goForward()
    await expect(page.getByRole('heading', { name: 'Tester un fichier' })).toBeVisible()
    await page.goBack()
    await expect(page.getByLabel('Largeur finie', { exact: true })).toHaveValue('100')
  })
}

test('Pizza : un gabarit invalide ne lance pas le test', async ({ page }) => {
  await page.goto('/?tool=pizza')
  await page.getByLabel('Rayon des coins', { exact: true }).fill('30')
  await page.getByRole('button', { name: 'Tester un fichier avec ce gabarit' }).click()
  await expect(page).toHaveURL('/?tool=pizza')
  await expect(page.getByLabel('Rayon des coins', { exact: true })).toBeFocused()
})

test('Pizza : les configurations par défaut ne remplacent pas le gabarit transmis', async ({
  page,
}) => {
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({ json: { id: 'pizza-test', email: 'pizza@example.com' } }),
  )
  await page.route('**/api/configurations?tool_id=*', (route) =>
    route.fulfill({
      json: [
        {
          id: 'default',
          name: 'Défaut',
          is_default: true,
          settings: { width: 85, height: 55, bleed: 3, shape: 'rectangle', corner_radius: 0 },
        },
      ],
    }),
  )
  await page.goto('/?tool=pizza')
  await expect(page.getByLabel('Charger une configuration')).toHaveValue('default')
  await page.getByLabel('Largeur finie', { exact: true }).fill('110')
  await page.getByRole('button', { name: 'Tester un fichier avec ce gabarit' }).click()
  await expect(page.getByRole('region', { name: 'Gabarit à tester' })).toContainText('110 × 55 mm')
  await page.getByRole('button', { name: 'Revenir au gabarit Pizza' }).click()
  await expect(page.getByLabel('Charger une configuration')).toHaveValue('')
  await expect(page.getByLabel('Largeur finie', { exact: true })).toHaveValue('110')
})

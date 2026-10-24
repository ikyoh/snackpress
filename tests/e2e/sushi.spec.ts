import { test, expect } from '@playwright/test'

for (const mobile of [false, true]) {
  test(`Sushi : rayon des coins du contour rectangle (${mobile ? 'mobile' : 'bureau'})`, async ({
    page,
  }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/?tool=sushi')
    const radius = page.getByLabel('Rayon des coins', { exact: true })
    await expect(radius).toHaveCount(0)
    await page.getByLabel('Contour', { exact: true }).selectOption('rectangle')
    await expect(radius).toHaveValue('0')
    await expect(radius).toHaveAttribute('max', '27.5')
    await radius.fill('28')
    expect(await radius.evaluate((input: HTMLInputElement) => input.validity.rangeOverflow)).toBe(
      true,
    )
    await radius.fill('10')
    await page.getByLabel('Fond perdu', { exact: true }).fill('3')
    await page.getByLabel('Contour', { exact: true }).selectOption('none')
    await expect(radius).toHaveCount(0)
    await page.getByLabel('Contour', { exact: true }).selectOption('rectangle')
    await expect(radius).toHaveValue('10')
    if (mobile) await page.getByRole('tab', { name: 'Aperçu', exact: true }).click()
    await expect(
      page.getByLabel('Aperçu automatique', { exact: true }).locator('canvas[data-ready=true]'),
    ).toBeVisible({ timeout: 20000 })
    if (mobile) await page.getByRole('tab', { name: 'Réglages', exact: true }).click()
    const response = page.waitForResponse((r) => r.url().includes('/api/tools/sushi/run'))
    await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
    const result = await response
    expect(result.status(), await result.text()).toBe(201)
    const job = await result.json()
    const exported = await page.request.get(`/api/tool-jobs/${job.id}/files/reglages.json`)
    expect((await exported.json()).settings).toMatchObject({
      shape: 'rectangle',
      corner_radius: 10,
      bleed: 3,
    })
    if (mobile) await page.getByRole('tab', { name: 'Aperçu', exact: true }).click()
    await expect(page.locator('.tool-success')).toBeVisible()
    await page.getByRole('button', { name: 'Supprimer ce travail', exact: true }).click()
  })

  test(`Sushi : fond perdu, contour facultatif et tracés libres (${mobile ? 'mobile' : 'bureau'})`, async ({
    page,
  }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/?tool=sushi')
    await expect(page.getByLabel('Contour', { exact: true })).toHaveValue('none')
    await page.getByLabel('Fond perdu', { exact: true }).fill('3')
    for (const [index, [kind, axis, position]] of [
      ['crease', 'vertical', '20'],
      ['cut', 'horizontal', '15'],
      ['cut', 'vertical', '0'],
      ['crease', 'horizontal', '55'],
    ].entries()) {
      await page.getByRole('button', { name: 'Ajouter un tracé', exact: true }).click()
      await page.getByLabel(`Type du tracé ${index + 1}`, { exact: true }).selectOption(kind)
      await page.getByLabel(`Orientation du tracé ${index + 1}`, { exact: true }).selectOption(axis)
      await page.getByLabel(`Position du tracé ${index + 1}`, { exact: true }).fill(position)
    }
    const first = page.getByLabel('Position du tracé 1', { exact: true })
    await first.fill('90')
    expect(await first.evaluate((input: HTMLInputElement) => input.validity.rangeOverflow)).toBe(
      true,
    )
    await first.fill('20')
    await page.getByLabel('Contour', { exact: true }).selectOption('circle')
    await page.getByLabel('Largeur', { exact: true }).fill('100')
    await expect(
      page.getByLabel('Hauteur (égale à la largeur pour un cercle)', { exact: true }),
    ).toHaveValue('100')
    await page.getByLabel('Contour', { exact: true }).selectOption('none')
    await page.getByRole('button', { name: 'Supprimer le tracé 3', exact: true }).click()
    await expect(page.locator('.sushi-line')).toHaveCount(3)
    await expect(page.getByLabel('Type du tracé 3', { exact: true })).toHaveValue('crease')
    await expect(page.getByLabel('Orientation du tracé 3', { exact: true })).toHaveValue(
      'horizontal',
    )
    const live = page.getByLabel('Aperçu automatique', { exact: true })
    if (mobile) await page.getByRole('tab', { name: 'Aperçu', exact: true }).click()
    await expect(live.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 20000 })
    if (mobile) await page.getByRole('tab', { name: 'Réglages', exact: true }).click()
    const response = page.waitForResponse((r) => r.url().includes('/api/tools/sushi/run'))
    await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
    const result = await response
    expect(result.status(), await result.text()).toBe(201)
    const job = await result.json()
    const settingsResponse = await page.request.get(`/api/tool-jobs/${job.id}/files/reglages.json`)
    const data = await settingsResponse.json()
    expect(data.settings).toMatchObject({
      bleed: 3,
      shape: 'none',
      lines: [
        { kind: 'crease', axis: 'vertical', position: 20 },
        { kind: 'cut', axis: 'horizontal', position: 15 },
        { kind: 'crease', axis: 'horizontal', position: 55 },
      ],
    })
    if (mobile) await page.getByRole('tab', { name: 'Aperçu', exact: true }).click()
    await expect(page.locator('.tool-success')).toBeVisible()
    const download = page.waitForEvent('download')
    await page.locator('.artifact-downloads > a').first().click()
    expect((await download).suggestedFilename()).toContain('contours.pdf')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.getByRole('button', { name: 'Supprimer ce travail', exact: true }).click()
  })
}

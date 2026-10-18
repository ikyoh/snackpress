import { test, expect } from '@playwright/test'
import { openSettings } from './settings'

test.setTimeout(60_000)

for (const mobile of [false, true]) {
  test(`Taco : faces coordonnées, retournement et export (${mobile ? 'mobile' : 'bureau'})`, async ({
    page,
  }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 })
    else await page.setViewportSize({ width: 1440, height: 1000 })
    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))
    await page.goto('/?tool=taco')
    await expect(page.getByLabel('Retrait du panneau rentrant')).toHaveCount(0)
    await expect(page.getByLabel('Côté du rabat rentrant au recto')).toHaveCount(0)
    await openSettings(page, 'Pliage')
    await page.getByLabel('Type de pli', { exact: true }).selectOption('roll')
    await expect(page.getByLabel('Retrait du panneau rentrant')).toBeVisible()
    await page.getByLabel('Côté du rabat rentrant au recto').selectOption('left')
    await page.getByLabel('Face représentée au recto').selectOption('inside')
    await expect(page.getByLabel('Retournement du verso')).toHaveValue('left_right')
    if (mobile) await page.getByRole('tab', { name: 'Aperçu', exact: true }).click()
    const live = page.getByLabel('Aperçu automatique', { exact: true })
    await expect(live.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
    const faces = live.getByRole('group', { name: 'Face du plan de pliage' })
    await expect(faces.getByRole('button', { name: 'Recto', exact: true })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    await faces.getByRole('button', { name: 'Verso', exact: true }).focus()
    await page.keyboard.press('Enter')
    await expect(live.locator('.pdf-viewer-footer')).toContainText('Page 2 sur 2')
    if (mobile) await page.getByRole('tab', { name: 'Réglages', exact: true }).click()
    const render = page.waitForResponse(
      (r) =>
        r.url().endsWith('/render') &&
        r.request().postDataJSON()?.settings?.turn === 'top_bottom' &&
        r.status() === 200,
    )
    await page.getByLabel('Retournement du verso').selectOption('top_bottom')
    await render
    if (mobile) await page.getByRole('tab', { name: 'Aperçu', exact: true }).click()
    await expect(live.getByRole('status').filter({ hasText: 'Aperçu à jour' })).toBeVisible({
      timeout: 15000,
    })
    await expect(faces.getByRole('button', { name: 'Verso', exact: true })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    await expect(live.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({
      path: `test-results/taco-${mobile ? 'mobile' : 'desktop'}-verso.png`,
      fullPage: true,
    })
    if (mobile) await page.getByRole('tab', { name: 'Réglages', exact: true }).click()
    const response = page.waitForResponse((r) => r.url().includes('/api/tools/taco/run'))
    await page.getByRole('button', { name: 'Générer le fichier final', exact: true }).click()
    const exported = await response
    expect(exported.status(), await exported.text()).toBe(201)
    const data = await exported.json()
    expect(data.artifacts.find((a: { name: string }) => a.name === 'plan-pliage.pdf').pages).toBe(2)
    const settings = await (
      await page.request.get(`/api/tool-jobs/${data.id}/files/reglages.json`)
    ).json()
    expect(settings.settings).toMatchObject({
      turn: 'top_bottom',
      flap_side: 'left',
      recto_face: 'inside',
    })
    const finalFaces = page.getByRole('group', { name: 'Face du plan de pliage' })
    await finalFaces.getByRole('button', { name: 'Verso', exact: true }).click()
    await expect(page.locator('.pdf-viewer-footer')).toContainText('Page 2 sur 2')
    await expect(page.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
    await page.getByLabel('Document à prévisualiser').selectOption('fiche-pliage.pdf')
    await expect(page.getByRole('group', { name: 'Face du plan de pliage' })).toHaveCount(0)
    expect(errors).toEqual([])
  })
}

test('Taco : un ancien gabarit conserve ses réglages avec le verso par défaut', async ({
  page,
}) => {
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({ json: { id: 'taco-test', email: 'taco@example.com' } }),
  )
  await page.route('**/api/configurations?tool_id=taco', (route) =>
    route.fulfill({
      json: [
        {
          id: 'legacy',
          name: 'Dépliant existant',
          is_default: true,
          settings: { width: 297, height: 210, fold: 'roll', panels: 3, allowance: 2 },
        },
      ],
    }),
  )
  await page.goto('/?tool=taco')
  await expect(page.getByLabel('Largeur à plat')).toHaveValue('297')
  await openSettings(page, 'Pliage')
  await expect(page.getByLabel('Type de pli', { exact: true })).toHaveValue('roll')
  await expect(page.getByLabel('Retournement du verso')).toHaveValue('left_right')
  await expect(page.getByLabel('Côté du rabat rentrant au recto')).toHaveValue('right')
  await expect(page.getByLabel('Face représentée au recto')).toHaveValue('outside')
  const live = page.getByLabel('Aperçu automatique', { exact: true })
  await expect(live.locator('canvas[data-ready=true]')).toBeVisible({ timeout: 15000 })
  await live.getByRole('button', { name: 'Verso', exact: true }).click()
  await expect(live.locator('.pdf-viewer-footer')).toContainText('Page 2 sur 2')
})

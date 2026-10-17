import { expect, test } from '@playwright/test'
import { readdir, readFile } from 'node:fs/promises'
import { join } from 'node:path'

test('catalogue personnel : création, matières, déclinaison, rechargement et BAT libre enregistré', async ({
  page,
}) => {
  const email = 'produits@example.com'
  const headers = { 'X-Snackpress-Request': '1' }
  await page.goto('/')
  expect(
    (await page.request.post('/api/auth/register', { headers, data: { email } })).status(),
  ).toBe(200)
  let token = ''
  const mailbox = join(process.env.SNACKPRESS_ACCOUNT_TEST_DATA!, 'mail-outbox')
  for (const file of await readdir(mailbox)) {
    const message = (await readFile(join(mailbox, file), 'utf8'))
      .replace(/=\r?\n/g, '')
      .replace(/=([0-9A-F]{2})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))
    if (message.includes(`To: ${email}`)) token = message.match(/token=([A-Za-z0-9_-]+)/)?.[1] || ''
  }
  expect(token).not.toBe('')
  const password = 'Une longue phrase personnelle 2026'
  expect(
    (await page.request.post('/api/auth/verify', { headers, data: { token, password } })).status(),
  ).toBe(200)
  expect(
    (await page.request.post('/api/auth/login', { headers, data: { email, password } })).status(),
  ).toBe(200)
  await page.goto('/?view=products')
  await expect(page.getByRole('button', { name: 'Mon compte', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Ajouter un produit', exact: true }).click()
  await page.getByLabel('Nom du produit', { exact: true }).fill('Invitation atelier')
  await page.getByLabel('Nom de la déclinaison', { exact: true }).fill('Petit format')
  await page.getByLabel('Support matière', { exact: true }).selectOption('mat350')
  await page.getByLabel('Ajouter un tracé').selectOption('pizza')
  await page.getByRole('button', { name: 'Dupliquer la déclinaison' }).click()
  await page.getByLabel('Nom de la déclinaison', { exact: true }).fill('Grand format')
  await page.getByLabel('Largeur finie (mm)', { exact: true }).fill('100')
  await page.getByRole('button', { name: 'Enregistrer le catalogue', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Catalogue enregistré')
  await page.reload()
  await page.getByRole('button', { name: 'Invitation atelier' }).click()
  await expect(page.getByLabel('Déclinaison à modifier').locator('option')).toHaveCount(2)
  await page.goto('/?tool=burger')
  await page.getByLabel('Mode du BAT').selectOption('catalog')
  const productId = await page
    .getByLabel('Produit', { exact: true })
    .getByRole('option', { name: 'Invitation atelier' })
    .getAttribute('value')
  await page.getByLabel('Produit', { exact: true }).selectOption(productId!)
  await expect(page.getByLabel('Déclinaison du produit').locator('option')).toHaveCount(2)
  await page.getByLabel('Mode du BAT').selectOption('free')
  await page.getByLabel('Nom du produit pour ce BAT').fill('Libre sauvegardé')
  await page.getByRole('button', { name: 'Enregistrer comme nouveau produit' }).click()
  await expect(page.locator('.print-selector').getByRole('status')).toContainText(
    'Produit enregistré',
  )
  await page.goto('/?view=products')
  await expect(page.getByRole('button', { name: 'Libre sauvegardé' })).toBeVisible()
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  await page.getByRole('button', { name: 'Façonnages et finitions', exact: true }).click()
  await page.getByRole('button', { name: 'Ajouter une finition' }).click()
  await expect(page.locator('.accordion-trigger')).toHaveCount(7)
  await expect(page.getByLabel('Nom de la finition')).toHaveValue('Nouvelle finition')
  await expect(page.locator('.accordion-trigger[aria-expanded="true"]')).toHaveCount(1)
  await page.getByLabel('Nom de la finition').fill('Finition modifiée')
  await page.locator('.accordion-trigger').first().click()
  await expect(
    page.getByRole('button', { name: 'Finition modifiée', exact: true }),
  ).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByLabel('Nom de la finition')).toHaveCount(1)
  await page.getByRole('button', { name: 'Finition modifiée', exact: true }).click()
  await expect(page.getByLabel('Nom de la finition')).toHaveValue('Finition modifiée')
  await page.getByRole('button', { name: 'Finition modifiée', exact: true }).click()
  await expect(page.getByLabel('Nom de la finition')).toHaveCount(0)
  expect(errors).toEqual([])
})

import { expect, test, type Page } from '@playwright/test'
import { readdir, readFile } from 'node:fs/promises'
import { join } from 'node:path'

const password = 'Une longue phrase personnelle 2026'
async function mailLink(email: string, kind: string) {
  let link = ''
  await expect
    .poll(async () => {
      const folder = join(process.env.SNACKPRESS_ACCOUNT_TEST_DATA!, 'mail-outbox')
      const files = await readdir(folder).catch(() => [])
      for (const file of files) {
        const text = (await readFile(join(folder, file), 'utf8'))
          .replace(/=\r?\n/g, '')
          .replace(/=([0-9A-F]{2})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))
        if (text.includes(`To: ${email}`)) {
          const found = text.match(
            new RegExp(`http://127\\.0\\.0\\.1:5175/#account=${kind}&token=[A-Za-z0-9_-]+`),
          )
          if (found) link = found[0]
        }
      }
      return !!link
    })
    .toBe(true)
  return link
}
async function login(page: Page, email: string, value = password) {
  await page.getByRole('button', { name: 'Se connecter', exact: true }).click()
  await page.getByLabel('Adresse e-mail').fill(email)
  await page.getByLabel('Mot de passe', { exact: true }).fill(value)
  await page.getByRole('dialog').getByRole('button', { name: 'Se connecter', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Mon compte', exact: true })).toBeVisible()
}
async function register(page: Page, email: string) {
  await page.goto('/?tool=pizza')
  await page.getByRole('button', { name: 'Se connecter', exact: true }).click()
  await page.getByRole('button', { name: 'Créer un compte', exact: true }).click()
  await page.getByLabel('Adresse e-mail').fill(email)
  await page.getByRole('button', { name: 'Recevoir le lien d’activation' }).click()
  await expect(page.getByRole('dialog').getByRole('status')).toContainText('activation')
  await page.goto(await mailLink(email, 'verify'))
  expect(page.url()).not.toContain('token=')
  await page.getByLabel('Mot de passe', { exact: true }).fill(password)
  await page.getByLabel('Confirmer le mot de passe').fill(password)
  await page.getByRole('button', { name: 'Activer mon compte' }).click()
  await expect(page.getByRole('dialog').getByRole('status')).toContainText('Compte activé')
  await page.getByLabel('Adresse e-mail').fill(email)
  await page.getByLabel('Mot de passe', { exact: true }).fill(password)
  await page.getByRole('dialog').getByRole('button', { name: 'Se connecter', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Mon compte', exact: true })).toBeVisible()
  await page.goto('/?tool=pizza')
}

test('compte, configurations, autre appareil, conflit et suppression', async ({
  page,
  browser,
}) => {
  const email = 'atelier@example.com'
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/?tool=pizza')
  await page.getByRole('button', { name: 'Se connecter', exact: true }).click()
  await page.screenshot({ path: 'test-results/accounts-login-desktop.png' })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: 'test-results/accounts-login-mobile.png' })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.keyboard.press('Escape')
  await page.setViewportSize({ width: 1440, height: 1000 })
  await register(page, email)
  await page.getByLabel('Largeur finie', { exact: true }).fill('100')
  await page.getByText('Enregistrer ou gérer les configurations', { exact: true }).click()
  await page.getByLabel('Nom de la configuration').fill('Cartes atelier')
  await page.getByRole('button', { name: 'Enregistrer sous…' }).click()
  await expect(
    page.getByRole('region', { name: 'Mes configurations' }).getByRole('status'),
  ).toContainText('enregistrée')
  await page.getByRole('button', { name: 'Définir par défaut', exact: true }).click()
  await expect(
    page.getByRole('region', { name: 'Mes configurations' }).getByRole('status'),
  ).toContainText('ouverture')
  await page.reload()
  await expect(page.getByLabel('Largeur finie', { exact: true })).toHaveValue('100')
  await page.screenshot({
    path: 'test-results/accounts-configurations-desktop.png',
    fullPage: true,
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: 'test-results/accounts-configurations-mobile.png', fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.setViewportSize({ width: 1440, height: 1000 })
  // A fresh browser context has no session, then retrieves the server-side default.
  const context = await browser.newContext({ baseURL: 'http://127.0.0.1:5175' })
  const other = await context.newPage()
  await other.goto('/?tool=pizza')
  await expect(other.getByText('Cartes atelier', { exact: true })).toHaveCount(0)
  await login(other, email)
  await expect(other.getByLabel('Largeur finie', { exact: true })).toHaveValue('100')
  await other.getByText('Enregistrer ou gérer les configurations', { exact: true }).click()
  await other.getByLabel('Largeur finie', { exact: true }).fill('110')
  await expect(other.getByText(/Modifiée —/)).toBeVisible()
  await other.getByRole('button', { name: 'Mettre à jour', exact: true }).click()
  await expect(
    other.getByRole('region', { name: 'Mes configurations' }).getByRole('status'),
  ).toContainText('mise à jour')
  await page.getByText('Enregistrer ou gérer les configurations', { exact: true }).click()
  await page.getByLabel('Largeur finie', { exact: true }).fill('120')
  await page.getByRole('button', { name: 'Mettre à jour', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('autre appareil')
  await page.getByRole('button', { name: 'Actualiser la liste' }).click()
  await page.getByLabel('Charger une configuration').selectOption('')
  await page
    .getByLabel('Charger une configuration')
    .selectOption({ label: 'Cartes atelier — par défaut' })
  await expect(page.getByLabel('Largeur finie', { exact: true })).toHaveValue('110')
  await page.getByLabel('Nom de la configuration').fill('Copie atelier')
  await page.getByRole('button', { name: 'Dupliquer', exact: true }).click()
  await expect(
    page.getByRole('region', { name: 'Mes configurations' }).getByRole('status'),
  ).toContainText('dupliquée')
  await page.getByLabel('Nom de la configuration').fill('Cartes bis')
  await page.getByRole('button', { name: 'Renommer', exact: true }).click()
  await expect(
    page.getByRole('region', { name: 'Mes configurations' }).getByRole('status'),
  ).toContainText('renommée')
  await page.getByRole('button', { name: 'Supprimer', exact: true }).click()
  await page.getByRole('button', { name: 'Confirmer la suppression', exact: true }).click()
  await expect(
    page.getByRole('region', { name: 'Mes configurations' }).getByRole('status'),
  ).toContainText('supprimée')
  await page.getByRole('button', { name: 'Mon compte', exact: true }).click()
  await page.getByRole('button', { name: 'Se déconnecter', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Se connecter pour sauvegarder' })).toBeVisible()
  await expect(page.getByLabel('Charger une configuration')).toHaveCount(0)
  await context.close()
  expect(errors).toEqual([])
})

test('import des anciens modèles et récupération de compte', async ({ page }) => {
  const email = 'import@example.com'
  await register(page, email)
  await page.evaluate(() =>
    localStorage.setItem(
      'snackpress-profiles',
      JSON.stringify({
        'Presse SRA3': { sheet_width: 330, sheet_height: 480, confirm_trim: true },
      }),
    ),
  )
  await page.goto('/?tool=imposition')
  await page.getByRole('button', { name: 'Importer dans ce compte' }).click()
  await expect(
    page.getByRole('region', { name: 'Mes configurations' }).getByRole('status'),
  ).toContainText('1 modèle(s) importé(s)')
  await page.getByLabel('Charger une configuration').selectOption({ label: 'Presse SRA3' })
  await expect(page.getByRole('spinbutton', { name: 'Largeur mm', exact: true })).toHaveValue('330')
  expect(await page.evaluate(() => !!localStorage.getItem('snackpress-profiles'))).toBe(true)
  await page.getByRole('button', { name: 'Mon compte', exact: true }).click()
  await page.getByRole('button', { name: 'Se déconnecter', exact: true }).click()
  await page.getByRole('button', { name: 'Se connecter', exact: true }).click()
  await page.getByRole('button', { name: 'Mot de passe oublié ?' }).click()
  await page.getByLabel('Adresse e-mail').fill(email)
  await page.getByRole('button', { name: 'Recevoir le lien de réinitialisation' }).click()
  await expect(page.getByRole('dialog').getByRole('status')).toContainText('réinitialisation')
  await page.goto(await mailLink(email, 'reset'))
  await page.getByLabel('Mot de passe', { exact: true }).fill(password + ' nouveau')
  await page.getByLabel('Confirmer le mot de passe').fill(password + ' nouveau')
  await page.getByRole('button', { name: 'Enregistrer le mot de passe' }).click()
  await expect(page.getByRole('dialog').getByRole('status')).toContainText('Mot de passe modifié')
  await page.getByLabel('Adresse e-mail').fill(email)
  await page.getByLabel('Mot de passe', { exact: true }).fill(password + ' nouveau')
  await page.getByRole('dialog').getByRole('button', { name: 'Se connecter', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Mon compte', exact: true })).toBeVisible()
  await page.goto('/?tool=imposition')
  await expect(
    page.getByLabel('Charger une configuration').locator('option', { hasText: 'Presse SRA3' }),
  ).toHaveCount(1)
})

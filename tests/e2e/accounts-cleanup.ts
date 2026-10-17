import { rm } from 'node:fs/promises'
import { basename } from 'node:path'
export default async function () {
  const folder = process.env.SNACKPRESS_ACCOUNT_TEST_DATA
  if (folder && basename(folder).startsWith('snackpress-accounts-')) {
    await rm(folder, { recursive: true, force: true })
  }
}

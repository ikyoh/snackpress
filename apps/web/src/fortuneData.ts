import Papa from 'papaparse'

export type CsvData = { columns: string[]; rows: string[][] }
export type Repiquage = {
  x: number
  y: number
  color: string
  size: number
  font: string
  rotation: number
  align: 'left' | 'center' | 'right'
  source: 'sequence' | 'csv'
  column: string
  rendering: 'text' | 'code128' | 'ean13'
  barcode_width: number
  barcode_height: number
}

export const newRepiquage = (height: number): Repiquage => ({
  x: 6,
  y: Math.max(0, height - 6),
  color: '#183d36',
  size: 8,
  font: 'SnackBold',
  rotation: 0,
  align: 'left',
  source: 'sequence',
  column: '',
  rendering: 'text',
  barcode_width: 40,
  barcode_height: 12,
})

export function parseCsv(buffer: ArrayBuffer): CsvData {
  if (buffer.byteLength > 1024 * 1024) throw new Error('Le fichier CSV est limité à 1 Mo.')
  let text: string
  try {
    text = new TextDecoder('utf-8', { fatal: true }).decode(buffer)
  } catch {
    text = new TextDecoder('windows-1252').decode(buffer)
  }
  text = text.replace(/^\uFEFF/, '')
  const delimiter = [',', ';', '\t']
    .map((value) => ({
      value,
      columns:
        Papa.parse<string[]>(text, { delimiter: value, preview: 1, skipEmptyLines: 'greedy' })
          .data[0]?.length ?? 0,
    }))
    .sort((a, b) => b.columns - a.columns)[0].value
  const parsed = Papa.parse<string[]>(text, {
    delimiter,
    skipEmptyLines: 'greedy',
    dynamicTyping: false,
  })
  if (parsed.errors.length)
    throw new Error('CSV invalide : vérifiez les guillemets et les séparateurs.')
  const [header, ...rows] = parsed.data
  const columns = (header ?? []).map((name) => name.trim())
  if (
    !columns.length ||
    columns.length > 100 ||
    columns.some((name) => !name || name.length > 256) ||
    new Set(columns).size !== columns.length
  )
    throw new Error('Le CSV doit contenir de 1 à 100 colonnes avec des noms non vides et uniques.')
  if (!rows.length || rows.length > 1000)
    throw new Error('Le CSV doit contenir de 1 à 1 000 lignes de données, après l’en-tête.')
  if (rows.some((row) => row.length !== columns.length || row.some((value) => value.length > 4000)))
    throw new Error(
      'Chaque ligne doit contenir les mêmes colonnes que l’en-tête, avec 4 000 caractères maximum par champ.',
    )
  return { columns, rows }
}

export function repiquageValue(
  item: Repiquage,
  serial: string,
  data: CsvData | null,
  row = 0,
): string {
  return item.source === 'sequence'
    ? serial
    : (data?.rows[row]?.[data.columns.indexOf(item.column)] ?? '')
}

export function barcodeError(value: string, kind: Repiquage['rendering']): string {
  if (kind === 'text') return ''
  if (kind === 'code128')
    return /^[\x20-\x7E]+$/.test(value)
      ? ''
      : 'Code 128 : caractères ASCII imprimables uniquement, valeur non vide.'
  if (!/^[0-9]{12,13}$/.test(value)) return 'EAN-13 : 12 ou 13 chiffres requis.'
  const key =
    (10 -
      ([...value.slice(0, 12)].reduce((sum, digit, i) => sum + Number(digit) * (i % 2 ? 3 : 1), 0) %
        10)) %
    10
  return value.length === 13 && Number(value[12]) !== key
    ? 'EAN-13 : clé de contrôle incorrecte.'
    : ''
}

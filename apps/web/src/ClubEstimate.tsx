import type { components } from '../../../packages/api-client/schema'

type Field = components['schemas']['ToolField']
const millimetres = new Intl.NumberFormat('fr-FR', {
  minimumFractionDigits: 3,
  maximumFractionDigits: 3,
})

export function ClubEstimate({
  fields,
  values,
}: {
  fields: Field[]
  values: Record<string, string | number>
}) {
  const current = Object.fromEntries(
    fields.map((field) => [field.key, values[field.key] ?? field.default]),
  )
  const valid =
    ['bulk', 'caliper'].includes(String(current.mode)) &&
    fields
      .filter(
        (field) =>
          field.type === 'number' &&
          (current.mode === 'caliper'
            ? !['gsm', 'bulk'].includes(field.key)
            : field.key !== 'caliper'),
      )
      .every((field) => {
        const value = Number(current[field.key])
        return (
          current[field.key] !== '' &&
          Number.isFinite(value) &&
          (field.min == null || value >= field.min) &&
          (field.max == null || value <= field.max)
        )
      }) &&
    Number(current.pages) % 2 === 0
  const leaves = Number(current.pages) / 2
  const microns =
    current.mode === 'caliper'
      ? Number(current.caliper)
      : Number(current.gsm) * Number(current.bulk)
  const block = (leaves * microns) / 1000
  const glue = Number(current.glue)

  return (
    <div className="club-estimate" role="status" aria-live="polite" aria-atomic="true">
      <span>Dos estimé</span>
      <output aria-label="Dos estimé">
        {valid ? `${millimetres.format(block + glue)} mm` : '—'}
      </output>
      <p>
        {valid
          ? `${millimetres.format(block)} mm de bloc papier + ${millimetres.format(glue)} mm de colle`
          : 'Renseignez des valeurs valides et un nombre pair de pages.'}
      </p>
    </div>
  )
}

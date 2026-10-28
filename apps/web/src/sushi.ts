import type { components } from '../../../packages/api-client/schema'

type Field = components['schemas']['ToolField']

export function visibleSushiField(key: string, values: Record<string, unknown>, imported = false) {
  if (imported)
    return [
      'pdf_box',
      'pdf_inset',
      'cut_name',
      'cut_width',
      'cut_cyan',
      'cut_magenta',
      'cut_yellow',
      'cut_black',
    ].includes(key)
  if (['pdf_box', 'pdf_inset'].includes(key)) return false
  return key !== 'corner_radius' || values.shape === 'rectangle'
}

export function sushiField(field: Field, values: Record<string, unknown>): Field {
  if (field.key !== 'corner_radius') return field
  return {
    ...field,
    max: Math.min(Number(values.width ?? 85), Number(values.height ?? 55)) / 2,
  }
}

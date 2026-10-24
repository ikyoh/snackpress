import type { components } from '../../../packages/api-client/schema'

type Field = components['schemas']['ToolField']

export function visibleSushiField(key: string, values: Record<string, unknown>) {
  return key !== 'corner_radius' || values.shape === 'rectangle'
}

export function sushiField(field: Field, values: Record<string, unknown>): Field {
  if (field.key !== 'corner_radius') return field
  return {
    ...field,
    max: Math.min(Number(values.width ?? 85), Number(values.height ?? 55)) / 2,
  }
}

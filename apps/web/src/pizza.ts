import type { components } from '../../../packages/api-client/schema'

type Field = components['schemas']['ToolField']
type Values = Record<string, unknown>

export function pizzaValue(field: Field, values: Values): string | number {
  return (values[field.key] ??
    (field.key.startsWith('safety_') ? values.safety : undefined) ??
    field.default) as string | number
}

export function visiblePizzaField(key: string, values: Values) {
  if (values.shape === 'circle' && (key.startsWith('height') || key === 'corner_radius'))
    return false
  if (values.shape === 'ellipse' && key === 'corner_radius') return false
  const axis = key.startsWith('width_') ? 'width' : 'height'
  if (key.endsWith('_min') || key.endsWith('_max')) return values[`${axis}_mode`] === 'bounded'
  return true
}

export function pizzaField(field: Field, values: Values): Field {
  const next = { ...field }
  if (values.shape === 'circle') {
    const labels: Record<string, string> = {
      width: 'Diamètre fini',
      width_mode: 'Réglage du diamètre',
      width_min: 'Diamètre minimal',
      width_max: 'Diamètre maximal',
    }
    next.label = labels[field.key] ?? field.label
  }
  if (['width', 'height'].includes(field.key) && values[`${field.key}_mode`] === 'bounded') {
    next.min = Number(values[`${field.key}_min`] ?? 0.1)
    next.max = Number(values[`${field.key}_max`] ?? 2000)
    next.help = `Choisissez une valeur entre ${next.min} et ${next.max} mm.`
  }
  for (const axis of ['width', 'height']) {
    if (field.key === `${axis}_min`) next.max = Number(values[`${axis}_max`] ?? 2000)
    if (field.key === `${axis}_max`) next.min = Number(values[`${axis}_min`] ?? 0.1)
  }
  return next
}

import type { components } from '../../../packages/api-client/schema'

type Field = components['schemas']['ToolField']
type Values = Record<string, unknown>

export const pizzaSides = ['top', 'bottom', 'left', 'right'] as const
export type PizzaValues = Record<string, string | number>

export function pizzaErrors(fields: Field[], values: Values): Record<string, string> {
  const errors: Record<string, string> = {}
  const measure = (key: string) => {
    const field = fields.find((field) => field.key === key)
    const value = field ? pizzaValue(field, values) : values[key]
    return value === '' || value == null ? NaN : Number(value)
  }
  const format = (value: number) => value.toLocaleString('fr-FR', { maximumFractionDigits: 3 })
  for (const field of fields) {
    if (field.type !== 'number' || !visiblePizzaField(field.key, values)) continue
    const value = measure(field.key)
    const limits = pizzaField(field, values)
    if (!Number.isFinite(value)) errors[field.key] = 'Renseignez une valeur en millimètres.'
    else if (limits.min != null && value < limits.min)
      errors[field.key] = `Valeur minimale : ${format(limits.min)} mm.`
    else if (limits.max != null && value > limits.max)
      errors[field.key] = `Valeur maximale : ${format(limits.max)} mm.`
  }
  const width = measure('width')
  const height = values.shape === 'circle' ? width : measure('height')
  if (
    values.shape === 'rectangle' &&
    width > 0 &&
    height > 0 &&
    measure('corner_radius') * 2 > Math.min(width, height)
  )
    errors.corner_radius = `Le rayon doit être inférieur ou égal à ${format(Math.min(width, height) / 2)} mm (moitié du plus petit côté).`
  for (const axis of ['width', 'height']) {
    if (axis === 'height' && values.shape === 'circle') continue
    if (values[`${axis}_mode`] !== 'bounded') continue
    const min = measure(`${axis}_min`)
    const max = measure(`${axis}_max`)
    if (min > max) {
      errors[`${axis}_min`] = 'Le minimum doit être inférieur ou égal au maximum.'
      errors[`${axis}_max`] = 'Le maximum doit être supérieur ou égal au minimum.'
    }
  }
  for (const prefix of ['safety', 'unusable']) {
    for (const [start, end, dimension, label] of [
      ['left', 'right', width, 'la largeur'],
      ['top', 'bottom', height, values.shape === 'circle' ? 'le diamètre' : 'la hauteur'],
    ] as const) {
      if (!Number.isFinite(dimension) || dimension <= 0) continue
      if (measure(`${prefix}_${start}`) + measure(`${prefix}_${end}`) >= dimension) {
        const message = `Les retraits opposés doivent totaliser moins de ${format(dimension)} mm (${label}).`
        errors[`${prefix}_${start}`] ??= message
        errors[`${prefix}_${end}`] ??= message
      }
    }
  }
  return errors
}

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

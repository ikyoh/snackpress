import { describe, expect, it } from 'vitest'
import { pizzaErrors, pizzaSides, type PizzaValues } from './pizza'
import type { components } from '../../../packages/api-client/schema'

type Field = components['schemas']['ToolField']
const fields: Field[] = [
  ...['width', 'height', 'width_min', 'width_max', 'height_min', 'height_max'].map((key) => ({
    key,
    min: 0.1,
    max: 2000,
  })),
  { key: 'corner_radius', min: 0, max: 1000 },
  { key: 'bleed', min: 0, max: 30 },
  ...pizzaSides.flatMap((side) => [
    { key: `safety_${side}`, min: 0, max: 100 },
    { key: `unusable_${side}`, min: 0, max: 2000 },
  ]),
].map((field) => ({
  ...field,
  type: 'number',
  label: field.key,
  default: 0,
  unit: 'mm',
  step: 0.5,
  help: '',
  options: [],
}))
const defaults: PizzaValues = {
  shape: 'rectangle',
  width: 85,
  height: 55,
  corner_radius: 0,
  bleed: 3,
  width_mode: 'fixed',
  width_min: 0.1,
  width_max: 2000,
  height_mode: 'fixed',
  height_min: 0.1,
  height_max: 2000,
  ...Object.fromEntries(
    pizzaSides.flatMap((side) => [
      [`safety_${side}`, 4],
      [`unusable_${side}`, 0],
    ]),
  ),
}

describe('contraintes géométriques de Pizza', () => {
  it('accepte le format courant et les valeurs décimales', () => {
    expect(pizzaErrors(fields, defaults)).toEqual({})
    expect(pizzaErrors(fields, { ...defaults, width: 85.25, safety_top: 3.15 })).toEqual({})
  })
  it('signale les saisies vides et les limites par champ', () => {
    expect(pizzaErrors(fields, { ...defaults, width: '', bleed: 31 })).toMatchObject({
      width: 'Renseignez une valeur en millimètres.',
      bleed: 'Valeur maximale : 30 mm.',
    })
  })
  it('ne produit pas de contraintes de retrait impossibles si une dimension est invalide', () => {
    expect(pizzaErrors(fields, { ...defaults, width: -1 })).toEqual({
      width: 'Valeur minimale : 0,1 mm.',
    })
  })
  it('limite les coins arrondis à la moitié du petit côté', () => {
    expect(pizzaErrors(fields, { ...defaults, corner_radius: 28 }).corner_radius).toContain(
      '27,5 mm',
    )
    expect(pizzaErrors(fields, { ...defaults, corner_radius: 27.5 })).toEqual({})
  })
  it('contrôle les retraits opposés et garde une surface intérieure', () => {
    const errors = pizzaErrors(fields, { ...defaults, safety_left: 81, unusable_top: 55 })
    expect(errors.safety_left).toContain('moins de 85 mm')
    expect(errors.safety_right).toBe(errors.safety_left)
    expect(errors.unusable_bottom).toContain('moins de 55 mm')
  })
  it('utilise le diamètre du cercle et ignore la hauteur et le rayon conservés', () => {
    const errors = pizzaErrors(fields, {
      ...defaults,
      shape: 'circle',
      width: 40,
      height: '',
      corner_radius: 1000,
      safety_top: 36,
    })
    expect(errors.height).toBeUndefined()
    expect(errors.corner_radius).toBeUndefined()
    expect(errors.safety_top).toContain('40 mm (le diamètre)')
  })
  it('contrôle les bornes actives sans bloquer sur les bornes désactivées', () => {
    const values = { ...defaults, width_min: 100, width_max: 50 }
    expect(pizzaErrors(fields, values)).toEqual({})
    const errors = pizzaErrors(fields, { ...values, width_mode: 'bounded' })
    expect(errors.width_min).toContain('minimum')
    expect(errors.width_max).toContain('maximum')
    expect(errors.width).toBeDefined()
  })
})

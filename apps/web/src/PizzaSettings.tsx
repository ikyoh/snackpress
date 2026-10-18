import { useEffect, useId, useState, type ReactNode } from 'react'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from './components/ui/accordion'
import { pizzaField, pizzaSides, pizzaValue, visiblePizzaField, type PizzaValues } from './pizza'
import type { components } from '../../../packages/api-client/schema'

type Field = components['schemas']['ToolField']
type FieldOptions = {
  displayLabel?: string
  value?: string | number
  update?: (value: string | number) => void
  error?: string
}

export function PizzaSettings({
  fields,
  values,
  sections,
  onSectionsChange,
  onChange,
  onFocusField,
  errors,
  renderField,
}: {
  fields: Field[]
  values: PizzaValues
  sections: string[]
  onSectionsChange: (sections: string[]) => void
  onChange: (patch: PizzaValues) => void
  onFocusField: (key: string) => void
  errors: Record<string, string>
  renderField: (field: Field, options: FieldOptions) => ReactNode
}) {
  const id = useId()
  const [separate, setSeparate] = useState({ safety: false, unusable: false })
  const [advanced, setAdvanced] = useState(false)
  const hasLimits =
    values.width_mode === 'bounded' ||
    (values.shape !== 'circle' && values.height_mode === 'bounded')
  useEffect(() => {
    if (hasLimits) setAdvanced(true)
  }, [hasLimits])
  const value = (key: string) => {
    const field = fields.find((field) => field.key === key)
    return field ? pizzaValue(field, values) : 0
  }
  const number = (value: string | number) =>
    value === '' ? 'À renseigner' : Number(value).toLocaleString('fr-FR')
  const summary = (prefix: string) => {
    const numbers = pizzaSides.map((side) => value(`${prefix}_${side}`))
    if (prefix === 'unusable' && numbers.every((value) => value !== '' && Number(value) === 0))
      return 'Aucune zone inexploitable'
    if (numbers.every((value) => value === numbers[0]))
      return numbers[0] === '' ? 'À renseigner' : `${number(numbers[0])} mm sur tous les côtés`
    return `H ${number(numbers[0])} · B ${number(numbers[1])} · G ${number(numbers[2])} · D ${number(numbers[3])} mm`
  }
  const groups = [
    {
      key: 'format',
      title: 'Format',
      summary: `${values.shape === 'circle' ? 'Rond' : values.shape === 'ellipse' ? 'Ovale' : 'Rectangle'} · ${number(value('width'))} × ${number(values.shape === 'circle' ? value('width') : value('height'))} mm`,
      help: 'Dimensions finies, forme et fond perdu.',
    },
    {
      key: 'safety',
      title: 'Zone de sécurité',
      summary: summary('safety'),
      help: 'Gardez les textes et éléments importants à l’intérieur du trait vert pointillé.',
    },
    {
      key: 'unusable',
      title: 'Zone inexploitable',
      summary: summary('unusable'),
      help: 'Bandes hachurées en jaune à laisser libres. 0 mm = aucune bande.',
    },
  ]
  const visible = fields.filter((field) => visiblePizzaField(field.key, values))
  const isAdvanced = (field: Field) => /^(width|height)_(mode|min|max)$/.test(field.key)
  const render = (field: Field, options: FieldOptions = {}) => (
    <div
      className={`pizza-setting ${field.type === 'number' ? 'pizza-setting-number' : ''} ${field.key.endsWith('_all') ? 'pizza-setting-common' : ''}`}
      key={field.key}
      onFocusCapture={() => onFocusField(field.key)}
    >
      {renderField(pizzaField(field, values), { error: errors[field.key], ...options })}
    </div>
  )
  return (
    <Accordion
      className="pizza-settings"
      type="multiple"
      value={sections}
      onValueChange={onSectionsChange}
    >
      {groups.map((group) => {
        const prefix = group.key as 'safety' | 'unusable'
        const sides = pizzaSides.map((side) => value(`${prefix}_${side}`))
        const unequal = sides.some((value) => value !== sides[0])
        const split = group.key !== 'format' && (separate[prefix] || unequal)
        return (
          <AccordionItem key={group.key} value={group.key} data-pizza-section={group.key}>
            <AccordionTrigger
              aria-label={group.title}
              aria-describedby={`${id}-${group.key}-summary`}
            >
              <span>
                <span className="pizza-section-title">{group.title}</span>
                <small id={`${id}-${group.key}-summary`}>{group.summary}</small>
              </span>
            </AccordionTrigger>
            <AccordionContent forceMount hidden={!sections.includes(group.key)}>
              <p className="field-hint">{group.help}</p>
              {group.key === 'format' ? (
                <>
                  <div className="tool-fields pizza-fields-format">
                    {visible
                      .filter(
                        (field) => !/^(safety|unusable)_/.test(field.key) && !isAdvanced(field),
                      )
                      .map((field) => render(field))}
                  </div>
                  <details
                    className="pizza-dimension-limits"
                    open={advanced}
                    onToggle={(event) => setAdvanced(event.currentTarget.open)}
                  >
                    <summary>
                      Limites de dimensions
                      {hasLimits ? ' · actives' : ''}
                    </summary>
                    <p className="field-hint">
                      Pour un gabarit réutilisable, définissez les dimensions autorisées.
                    </p>
                    <div className="tool-fields">
                      {visible.filter(isAdvanced).map((field) => render(field))}
                    </div>
                  </details>
                </>
              ) : (
                <>
                  <label className="pizza-side-toggle">
                    <input
                      type="checkbox"
                      checked={split}
                      aria-describedby={unequal ? `${id}-${prefix}-link-help` : undefined}
                      onChange={(event) => {
                        setSeparate((old) => ({ ...old, [prefix]: event.target.checked }))
                        if (!event.target.checked)
                          onChange(
                            Object.fromEntries(
                              pizzaSides.map((side) => [`${prefix}_${side}`, sides[0]]),
                            ),
                          )
                      }}
                    />
                    Régler chaque côté séparément
                  </label>
                  {unequal && (
                    <p className="field-hint" id={`${id}-${prefix}-link-help`}>
                      Décochez pour appliquer la valeur du haut aux quatre côtés.
                    </p>
                  )}
                  <div className={`tool-fields pizza-fields-${prefix}`}>
                    {split
                      ? visible
                          .filter((field) => field.key.startsWith(`${prefix}_`))
                          .map((field) =>
                            render(field, {
                              displayLabel: field.label
                                .split(' — ')[1]
                                ?.replace(/^./, (letter) => letter.toUpperCase()),
                            }),
                          )
                      : (() => {
                          const source = fields.find((field) => field.key === `${prefix}_top`)!
                          return render(
                            {
                              ...source,
                              key: `${prefix}_all`,
                              label: `${prefix === 'safety' ? 'Sécurité' : 'Zone inexploitable'} — tous les côtés`,
                            },
                            {
                              displayLabel: 'Tous les côtés',
                              value: sides[0],
                              update: (value) =>
                                onChange(
                                  Object.fromEntries(
                                    pizzaSides.map((side) => [`${prefix}_${side}`, value]),
                                  ),
                                ),
                              error: pizzaSides
                                .map((side) => errors[`${prefix}_${side}`])
                                .find(Boolean),
                            },
                          )
                        })()}
                  </div>
                </>
              )}
            </AccordionContent>
          </AccordionItem>
        )
      })}
    </Accordion>
  )
}

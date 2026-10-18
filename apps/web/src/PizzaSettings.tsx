import { useId, type ReactNode } from 'react'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from './components/ui/accordion'
import { pizzaValue, visiblePizzaField } from './pizza'
import type { components } from '../../../packages/api-client/schema'

type Field = components['schemas']['ToolField']
type Values = Record<string, string | number>

export function PizzaSettings({
  fields,
  values,
  section,
  onSectionChange,
  renderField,
}: {
  fields: Field[]
  values: Values
  section: string
  onSectionChange: (section: string) => void
  renderField: (field: Field, shortLabel?: string) => ReactNode
}) {
  const id = useId()
  const value = (key: string) => {
    const field = fields.find((field) => field.key === key)
    return field ? pizzaValue(field, values) : 0
  }
  const sides = ['top', 'bottom', 'left', 'right']
  const summary = (prefix: string) => {
    const numbers = sides.map((side) => Number(value(`${prefix}_${side}`)).toLocaleString('fr-FR'))
    if (prefix === 'unusable' && numbers.every((number) => number === '0'))
      return 'Aucune zone inexploitable'
    return `H ${numbers[0]} · B ${numbers[1]} · G ${numbers[2]} · D ${numbers[3]} mm`
  }
  const groups = [
    {
      key: 'format',
      title: 'Format',
      summary: `${values.shape === 'circle' ? 'Rond' : values.shape === 'ellipse' ? 'Ovale' : 'Rectangle'} · ${value('width')} × ${values.shape === 'circle' ? value('width') : value('height')} mm`,
      help: 'Dimensions finies, forme et fond perdu.',
    },
    {
      key: 'safety',
      title: 'Zone de sécurité',
      summary: summary('safety'),
      help: 'Retrait depuis chaque bord du format fini. Limite verte en pointillés.',
    },
    {
      key: 'unusable',
      title: 'Zone inexploitable',
      summary: summary('unusable'),
      help: 'Limite jaune en pointillés et hachures diagonales. 0 mm = aucune bande sur ce côté.',
    },
  ]
  return (
    <Accordion
      className="pizza-settings"
      type="single"
      collapsible
      value={section}
      onValueChange={onSectionChange}
    >
      {groups.map((group) => (
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
          <AccordionContent forceMount hidden={section !== group.key}>
            <p className="field-hint">{group.help}</p>
            <div className={`tool-fields pizza-fields-${group.key}`}>
              {fields
                .filter(
                  (field) =>
                    visiblePizzaField(field.key, values) &&
                    (group.key === 'format'
                      ? !/^(safety|unusable)_/.test(field.key)
                      : field.key.startsWith(`${group.key}_`)),
                )
                .map((field) => (
                  <div
                    className={`pizza-setting ${field.type === 'number' ? 'pizza-setting-number' : ''}`}
                    key={field.key}
                  >
                    {renderField(
                      field,
                      group.key === 'format'
                        ? undefined
                        : field.label
                            .split(' — ')[1]
                            ?.replace(/^./, (letter) => letter.toUpperCase()),
                    )}
                  </div>
                ))}
            </div>
          </AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  )
}

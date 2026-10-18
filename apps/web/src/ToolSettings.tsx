import type { ReactNode } from 'react'
import { SettingsSection } from './SettingsSection'
import type { components } from '../../../packages/api-client/schema'

type Field = components['schemas']['ToolField']
type Group = { title: string; keys: string[] }
const groups: Record<string, Group[]> = {
  burger: [
    { title: 'Projet', keys: ['title', 'client', 'paper'] },
    { title: 'Consignes', keys: ['notes'] },
  ],
  donut: [
    { title: 'Format et fond perdu', keys: ['bleed', 'image_width'] },
    { title: 'Remplissage et export', keys: ['method', 'dpi', 'output'] },
  ],
  tiramisu: [
    { title: 'Comparaison', keys: ['tolerance', 'opacity'] },
    { title: 'Résolution', keys: ['dpi'] },
  ],
  taco: [
    { title: 'Format', keys: ['width', 'height'] },
    { title: 'Pliage', keys: ['fold', 'panels', 'allowance'] },
  ],
  burrito: [
    { title: 'Format', keys: ['width', 'height'] },
    { title: 'Ourlets et fourreau', keys: ['hem', 'sleeve'] },
    { title: 'Œillets', keys: ['spacing', 'inset'] },
  ],
  'club-sandwich': [
    { title: 'Ouvrage', keys: ['pages', 'glue'] },
    { title: 'Papier', keys: ['mode', 'gsm', 'bulk', 'caliper'] },
  ],
  'fortune-cookie': [
    { title: 'Support', keys: ['width', 'height', 'text'] },
    { title: 'Numérotation', keys: ['count', 'start', 'digits', 'prefix'] },
    { title: 'Code', keys: ['code', 'payload'] },
  ],
  poke: [{ title: 'Échantillonnage', keys: ['dpi'] }],
  sushi: [
    { title: 'Format', keys: ['width', 'height', 'shape'] },
    { title: 'Tracés et tons directs', keys: ['creases', 'cut_name', 'crease_name'] },
  ],
  kebab: [
    { title: 'Projet', keys: ['title', 'client'] },
    { title: 'Fabrication', keys: ['paper', 'quantity', 'colors'] },
    { title: 'Finitions et consignes', keys: ['finishing', 'notes'] },
  ],
  'layer-cake': [
    { title: 'Feuille', keys: ['sheet_width', 'sheet_height', 'margin'] },
    { title: 'Assemblage', keys: ['mode', 'gap', 'quantity', 'flip'] },
  ],
  bento: [
    { title: 'Opération', keys: ['operation'] },
    { title: 'Pages', keys: ['pages', 'rotation'] },
  ],
}

export function ToolSettings({
  toolId,
  fields,
  values,
  renderField,
}: {
  toolId: string
  fields: Field[]
  values: Record<string, string | number>
  renderField: (field: Field) => ReactNode
}) {
  const definitions = groups[toolId] ?? [
    { title: 'Réglages', keys: fields.map((field) => field.key) },
  ]
  const known = new Set(definitions.flatMap((group) => group.keys))
  const remaining = fields.filter((field) => !known.has(field.key))
  const sections = remaining.length
    ? [...definitions, { title: 'Autres réglages', keys: remaining.map((field) => field.key) }]
    : definitions
  return (
    <div className="grouped-tool-settings">
      {sections.map((group, index) => {
        const members = fields.filter((field) => group.keys.includes(field.key))
        if (!members.length) return null
        const summary = members
          .slice(0, 2)
          .map((field) => {
            const value = values[field.key] ?? field.default
            if (field.type === 'select')
              return (
                field.options?.find((option) => option.value === String(value))?.label ??
                String(value)
              )
            if (field.type === 'number')
              return `${field.label} : ${Number(value).toLocaleString('fr-FR')}${field.unit ? ` ${field.unit}` : ''}`
            return String(value || 'À renseigner').slice(0, 65)
          })
          .join(' · ')
        return (
          <SettingsSection
            key={group.title}
            title={group.title}
            summary={summary}
            defaultOpen={index === 0}
          >
            <div className="tool-fields grouped-tool-fields">
              {members.map((field) => (
                <div
                  key={field.key}
                  className={`grouped-setting ${field.type === 'number' ? 'grouped-setting-number' : ''}`}
                >
                  {renderField(field)}
                </div>
              ))}
            </div>
          </SettingsSection>
        )
      })}
    </div>
  )
}

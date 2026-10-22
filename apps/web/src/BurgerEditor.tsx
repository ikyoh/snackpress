import { pizzaField, pizzaValue, visiblePizzaField } from './pizza'
import { visibleTacoField } from './taco'
import { SettingsSection } from './SettingsSection'
import { Configurations } from './Configurations'
import { ProductSelector, snapshotFiles, type FileRequirement, type Snapshot } from './PrintCatalog'
import type { components } from '../../../packages/api-client/schema'

type Tool = components['schemas']['ToolDefinition']
type Fields = Record<string, string | number>
export type BurgerOptions = {
  source_mode: 'classic' | 'catalog' | 'free'
  product_snapshot: Snapshot | null
  document_type: 'custom' | 'card' | 'brochure'
  expected_files: number
  cover_files: number
  interior_pages: number
  finishes: string[]
  template_tool: string
  template_settings: Fields
}
export const burgerDefaults: BurgerOptions = {
  source_mode: 'classic',
  product_snapshot: null,
  document_type: 'custom',
  expected_files: 1,
  cover_files: 1,
  interior_pages: 4,
  finishes: [],
  template_tool: 'none',
  template_settings: {},
}
export function burgerFiles(options: BurgerOptions): FileRequirement[] {
  if (options.product_snapshot) return snapshotFiles(options.product_snapshot)
  const count = Math.max(0, Math.min(80, options.expected_files))
  const labels = Array.from({ length: count }, (_, i) =>
    options.document_type === 'card'
      ? i === 0
        ? 'Recto'
        : 'Verso'
      : options.document_type === 'brochure'
        ? i < options.cover_files
          ? `Couverture — fichier ${i + 1}`
          : `Intérieur — fichier ${i - options.cover_files + 1}`
        : `Visuel ${i + 1}`,
  )
  const scope =
    labels.length <= 4
      ? labels.join(', ')
      : options.document_type === 'brochure'
        ? 'Couverture et intérieur'
        : `Visuels 1 à ${count}`
  return [
    ...labels.map((label) => ({ label })),
    ...options.finishes.map((name) => ({
      label: `Masque de finition : ${name || 'à nommer'}`,
      hint: `Pour : ${scope}. Une page commune ou plusieurs pages dans l’ordre des visuels.`,
    })),
    ...(options.template_tool === 'pdf' ? [{ label: 'Gabarit PDF' }] : []),
  ]
}
export function burgerLabels(options: BurgerOptions): string[] {
  return burgerFiles(options).map((file) => file.label)
}
export function BurgerEditor({
  options,
  tools,
  onChange,
  renderField,
}: {
  options: BurgerOptions
  tools: Tool[]
  onChange: (next: BurgerOptions) => void
  renderField: (
    field: Tool['fields'][number],
    value: string | number,
    update: (value: string | number) => void,
  ) => React.ReactNode
}) {
  const template = tools.find((tool) => tool.id === options.template_tool)
  const templateValues = Object.fromEntries(
    template?.fields.map((field) => [
      field.key,
      options.template_settings[field.key] ?? field.default,
    ]) || [],
  )
  const width = Number(templateValues.width)
  const height = templateValues.shape === 'circle' ? width : Number(templateValues.height)
  const bleed = Number(templateValues.bleed)
  const format = (n: number) => n.toLocaleString('fr-FR')
  function update(patch: Partial<BurgerOptions>) {
    onChange({ ...options, ...patch })
  }
  return (
    <>
      <ProductSelector
        sourceMode={options.source_mode}
        snapshot={options.product_snapshot}
        tools={tools}
        onChange={(product_snapshot, source_mode) =>
          update({
            product_snapshot,
            ...(source_mode
              ? { source_mode: source_mode === 'legacy' ? 'classic' : source_mode }
              : {}),
          })
        }
      />
      {!options.product_snapshot && options.source_mode === 'classic' && (
        <section className="tool-settings-section sectioned-settings">
          <SettingsSection
            title="Composition du BAT"
            summary={`${options.expected_files} fichier(s) visuel(s)`}
            defaultOpen
          >
            <div className="tool-fields">
              <label className="field tool-field">
                Type de document
                <select
                  value={options.document_type}
                  onChange={(e) => {
                    const type = e.target.value as BurgerOptions['document_type']
                    update({
                      document_type: type,
                      expected_files: type === 'custom' ? 1 : 2,
                      cover_files: 1,
                    })
                  }}
                >
                  <option value="custom">Document personnalisé</option>
                  <option value="card">Carte de visite recto verso</option>
                  <option value="brochure">Brochure</option>
                </select>
              </label>
              <label className="field tool-field">
                Nombre de fichiers visuels attendus
                <input
                  type="number"
                  min={options.document_type === 'brochure' ? 2 : 1}
                  max="80"
                  required
                  readOnly={options.document_type === 'card'}
                  value={options.expected_files || ''}
                  onChange={(e) => update({ expected_files: Number(e.target.value) })}
                />
              </label>
              {options.document_type === 'brochure' && (
                <>
                  <label className="field tool-field">
                    Fichiers pour la couverture (4 pages au total)
                    <input
                      type="number"
                      min="1"
                      max={Math.min(4, options.expected_files - 1)}
                      required
                      value={options.cover_files || ''}
                      onChange={(e) => update({ cover_files: Number(e.target.value) })}
                    />
                  </label>
                  <label className="field tool-field">
                    Pages intérieures attendues
                    <input
                      type="number"
                      min="1"
                      max="200"
                      required
                      value={options.interior_pages || ''}
                      onChange={(e) => update({ interior_pages: Number(e.target.value) })}
                    />
                  </label>
                  <p className="field-hint wide-field">
                    Importez d’abord la couverture, puis l’intérieur. Les pages peuvent être
                    regroupées dans des PDF ou réparties entre plusieurs fichiers.
                  </p>
                </>
              )}
            </div>
          </SettingsSection>
          <SettingsSection
            title="Finitions et fichiers séparés"
            summary={options.finishes.join(', ') || 'Aucune finition'}
          >
            <p className="field-hint">
              Un PDF supplémentaire par finition, regroupant les pages concernées.
            </p>
            {options.finishes.map((name, i) => (
              <div className="tool-file" key={i}>
                <label className="field tool-field">
                  Finition {i + 1}
                  <input
                    required
                    maxLength={80}
                    value={name}
                    placeholder="Vernis, dorure, blanc de soutien…"
                    onChange={(e) =>
                      update({
                        finishes: options.finishes.map((s, j) => (i === j ? e.target.value : s)),
                      })
                    }
                  />
                </label>
                <button
                  type="button"
                  aria-label={`Retirer la finition ${i + 1}`}
                  onClick={() => update({ finishes: options.finishes.filter((_, j) => j !== i) })}
                >
                  Retirer
                </button>
              </div>
            ))}
            <button
              type="button"
              className="example-button"
              disabled={options.finishes.length >= 12}
              onClick={() => update({ finishes: [...options.finishes, ''] })}
            >
              Ajouter une finition
            </button>
          </SettingsSection>
          <SettingsSection
            title="Gabarit"
            summary={
              template?.name ?? (options.template_tool === 'pdf' ? 'Gabarit PDF' : 'Sans gabarit')
            }
          >
            <label className="field tool-field">
              Gabarit à superposer
              <select
                value={options.template_tool}
                onChange={(e) => {
                  const tool = tools.find((t) => t.id === e.target.value)
                  update({
                    template_tool: e.target.value,
                    template_settings: Object.fromEntries(
                      tool?.fields.map((f) => [f.key, f.default]) || [],
                    ),
                  })
                }}
              >
                <option value="none">Sans gabarit</option>
                <option value="pizza">Pizza — coupe et sécurité</option>
                <option value="taco">Taco — plis et panneaux</option>
                <option value="burrito">Burrito — ourlets, œillets et fourreau</option>
                <option value="sushi">Sushi — découpe et rainage</option>
                <option value="pdf">Charger un gabarit PDF</option>
              </select>
            </label>
            {template && (
              <>
                <Configurations
                  compact
                  toolId={template.id}
                  settings={options.template_settings}
                  onLoad={(settings) => update({ template_settings: settings as Fields })}
                />
                <div className="tool-fields">
                  {template.fields
                    .filter((f) => {
                      if (template.id === 'pizza')
                        return visiblePizzaField(f.key, options.template_settings)
                      return (
                        template.id !== 'taco' || visibleTacoField(f.key, options.template_settings)
                      )
                    })
                    .map((field) => (
                      <div key={field.key}>
                        {renderField(
                          template.id === 'pizza'
                            ? pizzaField(field, options.template_settings)
                            : field,
                          template.id === 'pizza'
                            ? pizzaValue(field, options.template_settings)
                            : (options.template_settings[field.key] ?? field.default),
                          (value) =>
                            update({
                              template_settings: {
                                ...options.template_settings,
                                [field.key]: value,
                              },
                            }),
                        )}
                      </div>
                    ))}
                </div>
              </>
            )}
            {options.template_tool !== 'none' && (
              <p className="field-hint">
                {options.template_tool === 'pizza' ? (
                  <>
                    Format fini : {format(width)} × {format(height)} mm. Fond perdu :{' '}
                    {format(bleed)} mm sur chaque côté.{' '}
                    <strong>
                      Fichier attendu : {format(width + 2 * bleed)} × {format(height + 2 * bleed)}{' '}
                      mm.
                    </strong>{' '}
                    Le BAT présente les visuels avec finitions au format fini, puis avec les repères
                    de gabarit, puis les éléments séparés avec repères.
                  </>
                ) : (
                  'Le BAT présente les visuels avec finitions au format fini, puis avec les repères de gabarit, puis les éléments séparés avec repères. Le format doit correspondre au format fini ou au gabarit complet, sans déformation.'
                )}
                {options.template_tool === 'pdf' &&
                  ' Ajoutez le gabarit PDF en dernier : une page commune ou deux pages recto / verso de même format. Ses zones blanches laisseront voir le visuel.'}
                {(options.template_tool === 'taco' || options.template_tool === 'pdf') &&
                  ' Avec deux faces de gabarit, les repères recto et verso alternent dans l’ordre des pages des fichiers visuels. Chaque fichier de finition reprend cette alternance à partir du recto.'}
              </p>
            )}
          </SettingsSection>
          <p className="privacy-note">
            {burgerLabels(options).length} fichier(s) attendu(s), dont {options.expected_files}{' '}
            visuel(s),
            {` ${options.finishes.length}`} finition(s)
            {options.template_tool === 'pdf' ? ' et 1 gabarit' : ''}. L’ordre ci-dessous détermine
            le rôle de chaque fichier.
          </p>
          <ol className="field-hint">
            {burgerLabels(options).map((label, i) => (
              <li key={i}>{label}</li>
            ))}
          </ol>
        </section>
      )}
    </>
  )
}

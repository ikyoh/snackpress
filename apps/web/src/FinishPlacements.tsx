import { Copy, Plus, Trash2 } from 'lucide-react'
import { Button } from './components/ui/button'
import type { Component, Finish, Variant } from './PrintCatalog'

export type FinishPlacement = {
  finish_id: string
  component_id: string
  x: number
  y: number
  page: number | null
}

export function isPositionedFinish(finish: Finish) {
  return finish.appearance?.mode === 'circle' || finish.appearance?.mode === 'rectangle'
}

export function finishSize(finish: Finish) {
  return finish.appearance?.mode === 'circle'
    ? [finish.appearance.diameter ?? 5, finish.appearance.diameter ?? 5]
    : [finish.appearance?.width ?? 10, finish.appearance?.height ?? 2]
}

function newPlacement(finish: Finish, component: Component): FinishPlacement {
  const [width, height] = finishSize(finish)
  return {
    finish_id: finish.id,
    component_id: component.id,
    x: Math.max(0, (component.width - width) / 2),
    y: Math.max(0, (component.height - height) / 2),
    page: null,
  }
}

export function syncFinishPlacements(variant: Variant, finishes: Finish[]): Variant {
  const selected = finishes.filter(
    (f) => variant.finish_ids.includes(f.id) && isPositionedFinish(f),
  )
  const placements = (variant.finish_placements ?? []).filter(
    (p) =>
      selected.some((f) => f.id === p.finish_id) &&
      variant.components.some((c) => c.id === p.component_id),
  )
  for (const finish of selected) {
    if (placements.some((p) => p.finish_id === finish.id)) continue
    placements.push(newPlacement(finish, variant.components[0]))
  }
  return { ...variant, finish_placements: placements }
}

export function FinishPlacements({
  variant,
  finishes,
  onChange,
}: {
  variant: Variant
  finishes: Finish[]
  onChange: (variant: Variant) => void
}) {
  const selected = finishes.filter(
    (f) => variant.finish_ids.includes(f.id) && isPositionedFinish(f),
  )
  if (!selected.length) return null
  const placements = variant.finish_placements ?? []
  const change = (next: FinishPlacement[]) => onChange({ ...variant, finish_placements: next })
  const update = (index: number, patch: Partial<FinishPlacement>) =>
    change(placements.map((p, i) => (i === index ? { ...p, ...patch } : p)))
  return (
    <section aria-label="Positions des façonnages" className="finish-placements">
      <h3>Positions des façonnages</h3>
      <p className="field-hint">
        X et Y placent le coin supérieur gauche de la forme, depuis le coin supérieur gauche du
        format fini, hors fond perdu. Ajoutez une occurrence pour chaque perforation ou agrafe.
      </p>
      {selected.map((finish) => {
        const [width, height] = finishSize(finish)
        return (
          <div className="print-block" key={finish.id}>
            <h4>
              {finish.name} —{' '}
              {finish.appearance?.mode === 'circle' ? `Ø ${width} mm` : `${width} × ${height} mm`}
            </h4>
            {placements.map((placement, index) => {
              if (placement.finish_id !== finish.id) return null
              const component = variant.components.find((c) => c.id === placement.component_id)
              if (!component) return null
              const pages = component.slots
                .filter((s) => s.role === 'visual')
                .reduce((n, s) => n + s.pages, 0)
              const number = placements
                .slice(0, index + 1)
                .filter((p) => p.finish_id === finish.id).length
              const invalid =
                placement.x < 0 ||
                placement.y < 0 ||
                placement.x + width > component.width ||
                placement.y + height > component.height
              const invalidPage = placement.page !== null && placement.page > pages
              return (
                <fieldset className="print-block" key={index}>
                  <legend>
                    {finish.name} — occurrence {number}
                  </legend>
                  <div className="finish-appearance-fields">
                    <label className="field">
                      <span>Composant</span>
                      <select
                        value={placement.component_id}
                        onChange={(e) =>
                          update(index, { component_id: e.target.value, page: null })
                        }
                      >
                        {variant.components.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      <span>Page d’application</span>
                      <select
                        value={placement.page ?? ''}
                        aria-invalid={invalidPage || undefined}
                        onChange={(e) =>
                          update(index, { page: e.target.value ? Number(e.target.value) : null })
                        }
                      >
                        <option value="">Toutes les pages</option>
                        {Array.from({ length: pages }, (_, i) => (
                          <option key={i} value={i + 1}>
                            Page {i + 1}
                          </option>
                        ))}
                      </select>
                    </label>
                    {(['x', 'y'] as const).map((axis) => (
                      <label className="field" key={axis}>
                        <span>
                          {axis === 'x' ? 'X depuis la gauche (mm)' : 'Y depuis le haut (mm)'}
                        </span>
                        <input
                          type="number"
                          min="0"
                          max={Math.max(
                            0,
                            axis === 'x' ? component.width - width : component.height - height,
                          )}
                          step="any"
                          required
                          value={placement[axis]}
                          aria-invalid={invalid || undefined}
                          onChange={(e) => update(index, { [axis]: e.target.valueAsNumber || 0 })}
                        />
                      </label>
                    ))}
                  </div>
                  {invalid && (
                    <p className="alert error" role="alert">
                      La forme doit rester dans le format fini du composant.
                    </p>
                  )}
                  {invalidPage && (
                    <p className="alert error" role="alert">
                      Choisissez une page présente dans le composant.
                    </p>
                  )}
                  <div className="print-actions">
                    <Button
                      variant="outline"
                      className="print-action-button"
                      type="button"
                      disabled={placements.length >= 200}
                      onClick={() => change([...placements, { ...placement }])}
                    >
                      <Copy size={18} aria-hidden="true" /> Dupliquer cette occurrence
                    </Button>
                    <Button
                      variant="outline"
                      className="print-action-button print-action-button-remove"
                      type="button"
                      onClick={() => change(placements.filter((_, i) => i !== index))}
                    >
                      <Trash2 size={18} aria-hidden="true" /> Retirer cette occurrence
                    </Button>
                  </div>
                </fieldset>
              )
            })}
            {!placements.some((p) => p.finish_id === finish.id) && (
              <p className="alert error" role="alert">
                Ajoutez au moins une position pour {finish.name}.
              </p>
            )}
            <Button
              variant="outline"
              className="print-action-button"
              type="button"
              disabled={placements.length >= 200}
              onClick={() => change([...placements, newPlacement(finish, variant.components[0])])}
            >
              <Plus size={18} aria-hidden="true" /> Ajouter une occurrence de {finish.name}
            </Button>
          </div>
        )
      })}
    </section>
  )
}

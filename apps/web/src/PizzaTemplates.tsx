import { useEffect, useState } from 'react'
import { RotateCw } from 'lucide-react'
import { useAccount } from './Account'
import { request } from './api'
import { Button } from './components/ui/button'
import type { components } from '../../../packages/api-client/schema'
import type { Component, Guide } from './PrintCatalog'

type Configuration = components['schemas']['ConfigurationResponse']

export function usePizzaTemplates(enabled: boolean) {
  const { user, loading: accountLoading } = useAccount()
  const [state, setState] = useState({
    owner: '',
    items: [] as Configuration[],
    loading: false,
    error: '',
  })
  const [epoch, setEpoch] = useState(0)
  useEffect(() => {
    if (!enabled || !user || accountLoading) return
    const owner = user.id
    const controller = new AbortController()
    setState({ owner, items: [], loading: true, error: '' })
    request<Configuration[]>('/api/configurations?tool_id=pizza', {
      signal: controller.signal,
      headers: { 'X-Snackpress-Account': owner },
    })
      .then((items) => {
        if (!controller.signal.aborted) setState({ owner, items, loading: false, error: '' })
      })
      .catch((error: Error) => {
        if (!controller.signal.aborted)
          setState({ owner, items: [], loading: false, error: error.message })
      })
    return () => controller.abort()
  }, [enabled, user?.id, accountLoading, epoch])
  return {
    ...(state.owner === user?.id ? state : { items: [], loading: !!user, error: '' }),
    signedIn: !!user,
    reload: () => setEpoch((value) => value + 1),
  }
}

export function PizzaTemplatePicker({
  component,
  source,
  onChange,
}: {
  component: Component
  source: ReturnType<typeof usePizzaTemplates>
  onChange: (patch: Partial<Component>) => void
}) {
  return (
    <div className="print-template-picker">
      <label className="field">
        <span>Gabarit Pizza</span>
        <select
          aria-label="Gabarit Pizza"
          value={
            component.pizza_template
              ? `${component.pizza_template.id}:${component.pizza_template.revision}`
              : ''
          }
          disabled={source.loading}
          onChange={(event) => {
            const selected = source.items.find(
              (item) => `${item.id}:${item.revision}` === event.target.value,
            )
            if (!selected) return
            const settings = structuredClone(selected.settings) as Guide['settings']
            onChange({
              pizza_template: { id: selected.id, name: selected.name, revision: selected.revision },
              width: Number(settings.width),
              height:
                settings.shape === 'circle' ? Number(settings.width) : Number(settings.height),
              bleed: Number(settings.bleed),
              guides: [
                ...component.guides.filter((g) => !['pizza', 'sushi'].includes(g.tool)),
                { tool: 'pizza', settings },
              ],
            })
          }}
        >
          <option value="" disabled={!!component.pizza_template}>
            Format actuel — choisir un gabarit
          </option>
          {component.pizza_template &&
            !source.items.some(
              (item) =>
                item.id === component.pizza_template?.id &&
                item.revision === component.pizza_template.revision,
            ) && (
              <option value={`${component.pizza_template.id}:${component.pizza_template.revision}`}>
                {component.pizza_template.name} — copie conservée
              </option>
            )}
          {source.items.map((item) => (
            <option
              key={item.id}
              value={`${item.id}:${item.revision}`}
              disabled={Number(item.settings.width) <= 5 || Number(item.settings.height) <= 5}
            >
              {item.name}
            </option>
          ))}
        </select>
      </label>
      <p className="field-hint">
        {component.width} × {component.height} mm · Fond perdu : {component.bleed} mm
      </p>
      {component.pizza_template &&
        component.guides
          .filter((g) => g.tool === 'pizza')
          .map((g) => (
            <p className="field-hint" key="bounds">
              {(['width', 'height'] as const)
                .filter((axis) => !(g.settings.shape === 'circle' && axis === 'height'))
                .map((axis) => {
                  const label =
                    axis === 'width'
                      ? g.settings.shape === 'circle'
                        ? 'Diamètre'
                        : 'Largeur'
                      : 'Hauteur'
                  return g.settings[`${axis}_mode`] === 'bounded'
                    ? `${label} : de ${g.settings[`${axis}_min`]} à ${g.settings[`${axis}_max`]} mm`
                    : `${label} fixe : ${component[axis]} mm`
                })
                .join(' · ')}
            </p>
          ))}
      {component.pizza_template && (
        <p className="field-hint">
          Les dimensions fixes et les bornes min/max sont reprises du gabarit. Les dimensions
          variables se choisissent dans le BAT.
        </p>
      )}
      {source.loading && <p role="status">Chargement des gabarits Pizza…</p>}
      {source.error && <p role="alert">{source.error}</p>}
      {!source.loading && !source.items.length && (
        <p className="field-hint">
          {source.signedIn
            ? 'Enregistrez un gabarit dans Pizza pour le retrouver ici.'
            : 'Connectez-vous pour retrouver vos gabarits Pizza.'}
        </p>
      )}
      <div className="print-actions">
        <Button asChild variant="outline" className="print-action-button">
          <a href="/?tool=pizza">Configurer un gabarit Pizza</a>
        </Button>
        {source.signedIn && (
          <Button
            type="button"
            variant="outline"
            className="print-action-button"
            disabled={source.loading}
            onClick={source.reload}
          >
            <RotateCw size={18} aria-hidden="true" /> Actualiser les gabarits
          </Button>
        )}
      </div>
    </div>
  )
}

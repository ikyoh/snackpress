import { useEffect, useState } from 'react'
import {
  makeSnapshot,
  newComponent,
  usePrintCatalog,
  type Component,
  type Snapshot,
} from './PrintCatalog'
import { post, request } from './api'
import { SettingsSection } from './SettingsSection'

export function fortuneComponent(snapshot: Snapshot | null, id: string): Component | null {
  return (
    snapshot?.variant.components.find((c) => c.id === id) ?? snapshot?.variant.components[0] ?? null
  )
}

export function legacyFortuneProduct(fields: Record<string, unknown>): Snapshot {
  const pizza = fields.pizza_template as Record<string, string | number> | null
  const component = newComponent()
  return {
    schema_version: 1,
    product_name: 'Produit de la configuration importée',
    category_name: 'Configuration Fortune Cookie',
    materials: [],
    finishes: [],
    variant: {
      id: 'fortune-import',
      name: 'Format conservé',
      finish_ids: [],
      components: [
        {
          ...component,
          id: 'fortune-support',
          width: Number(pizza?.width ?? fields.width ?? 85),
          height: Number(
            pizza?.shape === 'circle' ? pizza.width : (pizza?.height ?? fields.height ?? 55),
          ),
          bleed: Number(pizza?.bleed ?? fields.bleed ?? 3),
          guides: pizza ? [{ tool: 'pizza', settings: pizza }] : [],
        },
      ],
    },
  }
}

const compatible = (c: Component) =>
  c.width >= 40 && c.width <= 500 && c.height >= 40 && c.height <= 500 && c.bleed <= 20

export function FortuneProduct({
  snapshot,
  componentId,
  onChange,
}: {
  snapshot: Snapshot | null
  componentId: string
  onChange: (snapshot: Snapshot, componentId: string) => void
}) {
  const source = usePrintCatalog()
  const catalog = source.library?.catalog
  const [productId, setProductId] = useState('')
  const component = fortuneComponent(snapshot, componentId)
  useEffect(() => {
    if (!catalog) return
    if (!snapshot) {
      const product = catalog.products.find((p) =>
        p.variants.some((v) => v.components.some(compatible)),
      )
      const variant = product?.variants.find((v) => v.components.some(compatible))
      if (product && variant) {
        setProductId(product.id)
        onChange(makeSnapshot(product, variant, catalog), variant.components.find(compatible)!.id)
      }
    } else {
      const product = catalog.products.find(
        (p) =>
          p.name === snapshot.product_name && p.variants.some((v) => v.id === snapshot.variant.id),
      )
      setProductId(product?.id ?? '')
    }
  }, [catalog, snapshot, onChange])
  const product = catalog?.products.find((p) => p.id === productId)
  return (
    <SettingsSection
      title="Produit"
      defaultOpen
      summary={
        snapshot
          ? `${snapshot.product_name} · ${component?.width} × ${component?.height} mm`
          : 'Choisir un produit'
      }
    >
      <label className="field">
        <span>Produit</span>
        <select
          aria-label="Produit"
          required
          value={productId || (snapshot ? 'saved' : '')}
          disabled={!catalog}
          onChange={(e) => {
            const product = catalog?.products.find((p) => p.id === e.target.value)
            const variant = product?.variants.find((v) => v.components.some(compatible))
            if (product && variant && catalog) {
              setProductId(product.id)
              onChange(
                makeSnapshot(product, variant, catalog),
                variant.components.find(compatible)!.id,
              )
            }
          }}
        >
          {!product && (
            <option value={snapshot ? 'saved' : ''} disabled>
              {snapshot ? `${snapshot.product_name} — copie conservée` : 'Choisir un produit…'}
            </option>
          )}
          {catalog?.products.map((p) => (
            <option
              key={p.id}
              value={p.id}
              disabled={!p.variants.some((v) => v.components.some(compatible))}
            >
              {p.name}
            </option>
          ))}
        </select>
      </label>
      {product && (
        <label className="field">
          <span>Déclinaison du produit</span>
          <select
            aria-label="Déclinaison du produit"
            value={snapshot?.variant.id ?? ''}
            onChange={(e) => {
              const variant = product.variants.find((v) => v.id === e.target.value)
              if (variant && catalog)
                onChange(
                  makeSnapshot(product, variant, catalog),
                  variant.components.find(compatible)!.id,
                )
            }}
          >
            {product.variants.map((v) => (
              <option key={v.id} value={v.id} disabled={!v.components.some(compatible)}>
                {v.name}
              </option>
            ))}
          </select>
        </label>
      )}
      {snapshot && snapshot.variant.components.length > 1 && (
        <label className="field">
          <span>Composant à repiquer</span>
          <select
            aria-label="Composant à repiquer"
            value={component?.id}
            onChange={(e) => onChange(snapshot, e.target.value)}
          >
            {snapshot.variant.components.map((c) => (
              <option key={c.id} value={c.id} disabled={!compatible(c)}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      )}
      {component && (
        <p className="field-hint">
          Format fini : {component.width} × {component.height} mm · Fond perdu : {component.bleed}{' '}
          mm par côté.
        </p>
      )}
      <p className="field-hint">
        Le produit définit le format et le fond perdu. Tous ses tracés Pizza, Burrito, Sushi, Taco
        et perforations sont affichés dans le placement des repiquages. L’aperçu PDF montre le
        format fini, sans tracés ni fonds perdus.
      </p>
      {!catalog && !source.error && <p role="status">Chargement des produits…</p>}
      {catalog && !catalog.products.length && (
        <p>Ajoutez un produit dans le catalogue pour définir le format.</p>
      )}
      {source.error && (
        <p role="alert">
          {source.error}{' '}
          <button type="button" onClick={source.reload}>
            Recharger le catalogue
          </button>
        </p>
      )}
      <a href="/?view=products">Gérer les produits d’impression</a>
    </SettingsSection>
  )
}

export type PlacementGuides = { url: string; x: number; y: number; width: number; height: number }

export function useFortuneGuides(component: Component | null) {
  const serialized = JSON.stringify(component)
  const [state, setState] = useState<{
    key: string
    guides: PlacementGuides | null
    error: string
  }>({ key: '', guides: null, error: '' })
  useEffect(() => {
    if (!component) return
    const controller = new AbortController()
    const timer = setTimeout(() => {
      request<PlacementGuides>(
        '/api/tools/fortune-cookie/guides',
        post(JSON.parse(serialized), controller.signal),
      )
        .then((guides) => {
          if (!controller.signal.aborted) setState({ key: serialized, guides, error: '' })
        })
        .catch((error: Error) => {
          if (!controller.signal.aborted)
            setState({ key: serialized, guides: null, error: error.message })
        })
    }, 200)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [serialized])
  return state.key === serialized ? state : { guides: null, error: '' }
}

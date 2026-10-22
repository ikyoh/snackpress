import { useEffect, useState, type ReactNode } from 'react'
import { Copy, Plus, RotateCw, Save, Trash2 } from 'lucide-react'
import { useAccount } from './Account'
import { post, request } from './api'
import { Button } from './components/ui/button'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from './components/ui/accordion'
import type { components } from '../../../packages/api-client/schema'
import { PizzaTemplatePicker, usePizzaTemplates } from './PizzaTemplates'
import { visibleTacoField } from './taco'
import './print-catalog.css'

type Tool = components['schemas']['ToolDefinition']
export type Category = { id: string; name: string; parent_id: string | null }
export type Material = {
  id: string
  name: string
  family: string
  gsm: number | null
  thickness: number | null
  description: string
}
export type Finish = {
  id: string
  name: string
  mask: boolean
  material_ids: string[]
  excludes: string[]
  appearance?: FinishAppearance
}
type FinishAppearance = {
  mode: 'none' | 'area' | 'path'
  color: string
  dash_color: string
  alpha: number
  gradient: boolean
  end_color: string
  gradient_stops: GradientStop[] | null
  angle: number
}
type GradientStop = { color: string; position: number }
const defaultFinishAppearance: FinishAppearance = {
  mode: 'none',
  color: '#e6007e',
  dash_color: '#ffffff',
  alpha: 0.4,
  gradient: false,
  end_color: '#ffd54f',
  gradient_stops: null,
  angle: 0,
}

function defaultGradientStops(start: string, end: string): GradientStop[] {
  return [25, 50, 75].map((position) => ({
    position,
    color:
      '#' +
      [1, 3, 5]
        .map((index) => {
          const from = parseInt(start.slice(index, index + 2), 16)
          const to = parseInt(end.slice(index, index + 2), 16)
          return Math.round(from + ((to - from) * position) / 100)
            .toString(16)
            .padStart(2, '0')
        })
        .join(''),
  }))
}

function FinishAppearanceEditor({
  finish,
  onChange,
}: {
  finish: Finish
  onChange: (appearance: FinishAppearance) => void
}) {
  const style = { ...defaultFinishAppearance, ...finish.appearance }
  const update = (patch: Partial<FinishAppearance>) => onChange({ ...style, ...patch })
  const stops = style.gradient_stops ?? defaultGradientStops(style.color, style.end_color)
  const updateStop = (index: number, patch: Partial<GradientStop>) =>
    update({ gradient_stops: stops.map((stop, i) => (i === index ? { ...stop, ...patch } : stop)) })
  const gradientColors = [
    `${style.color} 0%`,
    ...stops.map((stop) => `${stop.color} ${stop.position}%`),
    `${style.end_color} 100%`,
  ].join(', ')
  return (
    <div className="finish-appearance">
      <Select
        label="Représentation sur le BAT"
        value={style.mode}
        onChange={(mode) => update({ mode: mode as FinishAppearance['mode'] })}
      >
        <option value="none">Aucune représentation</option>
        <option value="area">Zone</option>
        <option value="path">Tracé</option>
      </Select>
      {style.mode !== 'none' && (
        <>
          <p className="field-help">
            {finish.mask
              ? 'Le noir du PDF de masque définit la zone ; le blanc reste transparent.'
              : 'Sans PDF de masque, la représentation suit le format fini entier.'}
            {style.mode === 'path' &&
              ' Le pointillé se superpose au tracé continu et suit les mêmes contours.'}
          </p>
          <div className="finish-appearance-fields">
            <label className="field">
              <span>
                {style.mode === 'path'
                  ? 'Couleur du tracé'
                  : style.gradient
                    ? 'Couleur de départ · 0 %'
                    : 'Couleur'}
              </span>
              <input
                type="color"
                value={style.color}
                onChange={(e) => update({ color: e.target.value })}
              />
            </label>
            {style.mode === 'path' && (
              <label className="field">
                <span>Couleur du pointillé</span>
                <input
                  type="color"
                  value={style.dash_color}
                  onChange={(e) => update({ dash_color: e.target.value })}
                />
              </label>
            )}
            {style.mode === 'area' && (
              <Num
                label="Opacité (alpha, %)"
                value={Math.round(style.alpha * 100)}
                min={0}
                max={100}
                step="1"
                onChange={(value) => update({ alpha: value / 100 })}
              />
            )}
          </div>
          {style.mode === 'area' && (
            <>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={style.gradient}
                  onChange={(e) => update({ gradient: e.target.checked })}
                />
                <span>Créer un dégradé</span>
              </label>
              {style.gradient && (
                <>
                  <p className="field-help">
                    5 étapes : début à 0 %, fin à 100 %. Réglez les couleurs et les positions des
                    étapes 2, 3 et 4.
                  </p>
                  {stops.map((stop, index) => (
                    <div className="finish-appearance-fields" key={index}>
                      <label className="field">
                        <span>Couleur de l’étape {index + 2}</span>
                        <input
                          type="color"
                          value={stop.color}
                          onChange={(e) => updateStop(index, { color: e.target.value })}
                        />
                      </label>
                      <Num
                        label={`Position de l’étape ${index + 2} (%)`}
                        value={stop.position}
                        min={index === 0 ? 0 : stops[index - 1].position}
                        max={index === 2 ? 100 : stops[index + 1].position}
                        step="any"
                        onChange={(position) =>
                          updateStop(index, {
                            position: Math.max(
                              index === 0 ? 0 : stops[index - 1].position,
                              Math.min(index === 2 ? 100 : stops[index + 1].position, position),
                            ),
                          })
                        }
                      />
                    </div>
                  ))}
                  <div className="finish-appearance-fields">
                    <label className="field">
                      <span>Couleur d’arrivée · 100 %</span>
                      <input
                        type="color"
                        value={style.end_color}
                        onChange={(e) => update({ end_color: e.target.value })}
                      />
                    </label>
                    <Num
                      label="Angle du dégradé (°)"
                      value={style.angle}
                      min={0}
                      max={360}
                      step="1"
                      onChange={(angle) => update({ angle })}
                    />
                  </div>
                </>
              )}
            </>
          )}
          <div
            className="finish-appearance-preview"
            role="img"
            aria-label={`Aperçu de la finition ${finish.name}`}
          >
            <span
              className="finish-appearance-sample"
              style={
                style.mode === 'path'
                  ? undefined
                  : {
                      opacity: style.alpha,
                      background: style.gradient
                        ? `linear-gradient(${90 - style.angle}deg, ${gradientColors})`
                        : style.color,
                    }
              }
            >
              {style.mode === 'path' && (
                <svg
                  className="finish-appearance-path"
                  viewBox="0 0 100 60"
                  preserveAspectRatio="none"
                  aria-hidden="true"
                >
                  <rect
                    x="1"
                    y="1"
                    width="98"
                    height="58"
                    fill="none"
                    stroke={style.color}
                    strokeWidth="2"
                    vectorEffect="non-scaling-stroke"
                  />
                  <rect
                    x="1"
                    y="1"
                    width="98"
                    height="58"
                    fill="none"
                    stroke={style.dash_color}
                    strokeWidth="2"
                    strokeDasharray="8 4"
                    vectorEffect="non-scaling-stroke"
                  />
                </svg>
              )}
            </span>
            <span>Aperçu de la finition</span>
          </div>
          <p className="field-help">
            Les finitions sont visibles dans les pages de présentation et de contrôle du BAT.
          </p>
        </>
      )}
    </div>
  )
}
export type Slot = { id: string; name: string; pages: number; role: 'visual' | 'mask' }
export type Guide = {
  tool: 'pizza' | 'taco' | 'burrito' | 'sushi' | 'perforation'
  settings: Record<string, string | number | number[]>
}
export type Tickets = {
  start: number
  count: number
  digits: number
  prefix: string
  suffix: string
  per_book: number
  binding: 'loose' | 'stapled' | 'glued'
  placements: { x: number; y: number; size: number; offset: number; face: number }[]
  code: 'none' | 'qr' | 'code128'
  payload: string
  code_x: number
  code_y: number
}
export type Component = {
  pizza_template?: { id: string; name: string; revision: number } | null
  id: string
  name: string
  width: number
  height: number
  bleed: number
  material_id: string
  page_multiple: number
  slots: Slot[]
  guides: Guide[]
  tickets: Tickets | null
}
export type Variant = { id: string; name: string; components: Component[]; finish_ids: string[] }
export type Product = {
  id: string
  name: string
  category_id: string
  description: string
  material_ids: string[]
  finish_ids: string[]
  variants: Variant[]
}
export type PrintCatalog = {
  categories: Category[]
  materials: Material[]
  finishes: Finish[]
  products: Product[]
}
export type Snapshot = {
  schema_version: 1
  product_name: string
  category_name: string
  variant: Variant
  materials: Material[]
  finishes: Finish[]
}
type Library = { catalog: PrintCatalog; revision: number }
export const newId = () => crypto.randomUUID()
const clone = <T,>(value: T): T => structuredClone(value)
export const newComponent = (): Component => ({
  id: newId(),
  name: 'Composant',
  width: 85,
  height: 55,
  bleed: 3,
  material_id: '',
  page_multiple: 1,
  slots: [{ id: newId(), name: 'Recto', pages: 1, role: 'visual' }],
  guides: [],
  tickets: null,
})
export const newVariant = (): Variant => ({
  id: newId(),
  name: 'Sur mesure',
  components: [newComponent()],
  finish_ids: [],
})
const newTickets = (height: number): Tickets => ({
  start: 1,
  count: 50,
  digits: 4,
  prefix: '',
  suffix: '',
  per_book: 25,
  binding: 'loose',
  placements: [
    { x: 5, y: height - 10, size: 10, offset: 0, face: 1 },
    { x: 40, y: height - 10, size: 10, offset: 0, face: 1 },
  ],
  code: 'none',
  payload: '{n}',
  code_x: 60,
  code_y: 5,
})

export function usePrintCatalog() {
  const { user, loading: accountLoading } = useAccount()
  const [library, setLibrary] = useState<Library | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [epoch, setEpoch] = useState(0)
  useEffect(() => {
    setLibrary(null)
    setError('')
    if (accountLoading) return
    const controller = new AbortController()
    request<Library>(user ? '/api/print-catalog' : '/api/print-catalog/starter', {
      signal: controller.signal,
      headers: user ? { 'X-Snackpress-Account': user.id } : {},
    })
      .then(setLibrary)
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message)
      })
    return () => controller.abort()
  }, [user?.id, accountLoading, epoch])
  async function save(catalog: PrintCatalog) {
    if (!user || !library) throw new Error('Connectez-vous pour enregistrer le catalogue.')
    setBusy(true)
    setError('')
    try {
      const saved = await request<Library>('/api/print-catalog', {
        ...post({ catalog, revision: library.revision }),
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'X-Snackpress-Account': user.id },
      })
      setLibrary(saved)
      return saved
    } finally {
      setBusy(false)
    }
  }
  return { library, error, busy, save, reload: () => setEpoch((n) => n + 1) }
}

function Text({
  label,
  value,
  onChange,
  max = 120,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  max?: number
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input value={value} maxLength={max} required onChange={(e) => onChange(e.target.value)} />
    </label>
  )
}
function Num({
  label,
  value,
  onChange,
  min = 0,
  max = 5000,
  step = 'any',
}: {
  label: string
  value: number
  onChange: (v: number) => void
  min?: number
  max?: number
  step?: string
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        type="number"
        required
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(e.target.valueAsNumber || 0)}
      />
    </label>
  )
}
function Select({
  label,
  value,
  onChange,
  children,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  children: ReactNode
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)}>
        {children}
      </select>
    </label>
  )
}
function Checks({
  title,
  rows,
  selected,
  onChange,
}: {
  title: string
  rows: { id: string; name: string }[]
  selected: string[]
  onChange: (v: string[]) => void
}) {
  return (
    <fieldset className="print-checks">
      <legend>{title}</legend>
      {rows.map((row) => (
        <label className="checkbox-label" key={row.id}>
          <input
            type="checkbox"
            checked={selected.includes(row.id)}
            onChange={(e) =>
              onChange(
                e.target.checked ? [...selected, row.id] : selected.filter((id) => id !== row.id),
              )
            }
          />
          <span>{row.name}</span>
        </label>
      ))}
    </fieldset>
  )
}
const guideNames = {
  pizza: 'Pizza — coupe et sécurité',
  taco: 'Taco — plis et panneaux',
  burrito: 'Burrito — ourlets et œillets',
  sushi: 'Sushi — découpe et rainage',
  perforation: 'Perforations — parties détachables',
}

function PerforationPositions({
  positions,
  onChange,
}: {
  positions: number[]
  onChange: (v: number[]) => void
}) {
  const [text, setText] = useState(positions.join(', '))
  useEffect(() => {
    if (JSON.stringify(text.split(',').map(Number)) !== JSON.stringify(positions))
      setText(positions.join(', '))
  }, [positions])
  return (
    <label className="field">
      Positions en mm, séparées par des virgules
      <input
        required
        pattern={'\\s*[0-9]+([.][0-9]+)?(\\s*,\\s*[0-9]+([.][0-9]+)?)*\\s*'}
        value={text}
        onChange={(e) => {
          const value = e.target.value
          setText(value)
          if (e.target.validity.valid) onChange(value.split(',').map(Number))
        }}
      />
    </label>
  )
}

function TicketEditor({ value, onChange }: { value: Tickets; onChange: (v: Tickets) => void }) {
  const update = (patch: Partial<Tickets>) => onChange({ ...value, ...patch })
  const serial = (index: number) =>
    `${value.prefix}${String(value.start + index).padStart(value.digits, '0')}${value.suffix}`
  return (
    <div className="print-ticket">
      <h4>Numérotation des billets et des souches</h4>
      <div className="tool-fields">
        <Num
          label="Premier numéro"
          value={value.start}
          max={999999999}
          step="1"
          onChange={(start) => update({ start })}
        />
        <Num
          label="Quantité de billets (100 maximum)"
          value={value.count}
          min={1}
          max={100}
          step="1"
          onChange={(count) => update({ count })}
        />
        <Num
          label="Nombre de chiffres"
          value={value.digits}
          min={1}
          max={12}
          step="1"
          onChange={(digits) => update({ digits })}
        />
        <label className="field">
          Préfixe
          <input
            value={value.prefix}
            maxLength={30}
            onChange={(e) => update({ prefix: e.target.value })}
          />
        </label>
        <label className="field">
          Suffixe
          <input
            value={value.suffix}
            maxLength={30}
            onChange={(e) => update({ suffix: e.target.value })}
          />
        </label>
        <Select
          label="Assemblage"
          value={value.binding}
          onChange={(binding) => update({ binding: binding as Tickets['binding'] })}
        >
          <option value="loose">Billets séparés</option>
          <option value="stapled">Carnets agrafés</option>
          <option value="glued">Carnets encollés</option>
        </Select>
        {value.binding !== 'loose' && (
          <Num
            label="Billets par carnet"
            value={value.per_book}
            min={1}
            max={100}
            step="1"
            onChange={(per_book) => update({ per_book })}
          />
        )}
      </div>
      <p className="privacy-note">
        De {serial(0)} à {serial(Math.max(0, value.count - 1))}. Même numéro aux différentes
        positions ; un décalage permet une séquence distincte. Le BAT montre le premier et le
        dernier billet.
      </p>
      {value.placements.map((p, i) => (
        <fieldset className="print-block" key={i}>
          <legend>Position du numéro {i + 1}</legend>
          <div className="tool-fields">
            {(
              [
                ['x', 'Position X (mm)'],
                ['y', 'Position Y (mm)'],
                ['size', 'Taille (pt)'],
                ['offset', 'Décalage de séquence'],
                ['face', 'Face (1 = recto, 2 = verso)'],
              ] as const
            ).map(([key, label]) => (
              <Num
                key={key}
                label={label}
                value={p[key]}
                max={
                  key === 'face' ? 2 : key === 'size' ? 100 : key === 'offset' ? 999999999 : 5000
                }
                min={key === 'face' ? 1 : key === 'size' ? 4 : 0}
                onChange={(v) =>
                  update({
                    placements: value.placements.map((p, n) => (n === i ? { ...p, [key]: v } : p)),
                  })
                }
              />
            ))}
          </div>
          <Button
            variant="outline"
            className="print-action-button print-action-button-remove"
            type="button"
            disabled={value.placements.length === 1}
            onClick={() => update({ placements: value.placements.filter((_, n) => n !== i) })}
          >
            <Trash2 size={18} aria-hidden="true" /> Retirer cette position
          </Button>
        </fieldset>
      ))}
      <Button
        variant="outline"
        className="print-action-button"
        type="button"
        disabled={value.placements.length >= 20}
        onClick={() =>
          update({
            placements: [...value.placements, { x: 5, y: 20, size: 10, offset: 0, face: 1 }],
          })
        }
      >
        <Plus size={18} aria-hidden="true" /> Ajouter une position de numéro
      </Button>
      <div className="tool-fields">
        <Select
          label="Code associé au numéro"
          value={value.code}
          onChange={(code) => update({ code: code as Tickets['code'] })}
        >
          <option value="none">Sans code</option>
          <option value="qr">QR code</option>
          <option value="code128">Code 128</option>
        </Select>
        {value.code !== 'none' && (
          <>
            <Text
              label="Contenu du code ({n} = numéro)"
              value={value.payload}
              max={300}
              onChange={(payload) => update({ payload })}
            />
            <Num
              label="Code X (mm)"
              value={value.code_x}
              onChange={(code_x) => update({ code_x })}
            />
            <Num
              label="Code Y (mm)"
              value={value.code_y}
              onChange={(code_y) => update({ code_y })}
            />
          </>
        )}
      </div>
      <p className="field-hint">
        Positions depuis le coin supérieur gauche du format fini. Les perforations se règlent dans
        les tracés. La série PDF conserve les visuels vectoriels et les fonds perdus.
      </p>
    </div>
  )
}

function ComponentDimensions({
  component: c,
  onChange,
}: {
  component: Component
  onChange: (patch: Partial<Component>) => void
}) {
  const pizza = c.pizza_template ? c.guides.find((g) => g.tool === 'pizza')?.settings : undefined
  const circle = pizza?.shape === 'circle'
  return (
    <>
      {(['width', 'height'] as const)
        .filter((axis) => !(circle && axis === 'height'))
        .map((axis) => {
          const label =
            axis === 'width'
              ? circle
                ? 'Diamètre fini (mm)'
                : 'Largeur finie (mm)'
              : 'Hauteur finie (mm)'
          const bounded = pizza?.[`${axis}_mode`] === 'bounded'
          return pizza && !bounded ? (
            <p className="field-hint" key={axis}>
              {label} : {c[axis]} · Fixé par le gabarit Pizza
            </p>
          ) : (
            <Num
              key={axis}
              label={label}
              value={c[axis]}
              min={bounded ? Math.max(6, Number(pizza?.[`${axis}_min`])) : 6}
              max={bounded ? Number(pizza?.[`${axis}_max`]) : 5000}
              onChange={(value) =>
                onChange(circle ? { width: value, height: value } : { [axis]: value })
              }
            />
          )
        })}
      {pizza ? (
        <p className="field-hint">Fond perdu : {c.bleed} mm · Fixé par le gabarit Pizza</p>
      ) : (
        <Num
          label="Fond perdu attendu (mm)"
          value={c.bleed}
          max={30}
          onChange={(bleed) => onChange({ bleed })}
        />
      )}
    </>
  )
}

export function VariantEditor({
  variant,
  materials,
  finishes,
  tools,
  onChange,
  choosePizza = false,
}: {
  variant: Variant
  materials: Material[]
  finishes: Finish[]
  tools: Tool[]
  onChange: (v: Variant) => void
  choosePizza?: boolean
}) {
  const pizzaTemplates = usePizzaTemplates(choosePizza)
  function update(index: number, patch: Partial<Component>) {
    onChange({
      ...variant,
      components: variant.components.map((c, i) => (i === index ? { ...c, ...patch } : c)),
    })
  }
  return (
    <>
      <Text
        label="Nom de la déclinaison"
        value={variant.name}
        onChange={(name) => onChange({ ...variant, name })}
      />
      <Checks
        title="Options et finitions sélectionnées"
        rows={finishes}
        selected={variant.finish_ids}
        onChange={(finish_ids) => onChange({ ...variant, finish_ids })}
      />
      {variant.components.map((c, index) => (
        <fieldset className="print-block" key={c.id}>
          <legend>
            Composant {index + 1} — {c.name}
          </legend>
          <div className="tool-fields">
            <Text
              label="Nom du composant"
              value={c.name}
              onChange={(name) => update(index, { name })}
            />
            <Select
              label="Support matière"
              value={c.material_id}
              onChange={(material_id) => update(index, { material_id })}
            >
              <option value="">À confirmer</option>
              {materials.map((m) => (
                <option value={m.id} key={m.id}>
                  {m.name}
                </option>
              ))}
            </Select>
            {!choosePizza && (
              <ComponentDimensions component={c} onChange={(patch) => update(index, patch)} />
            )}
          </div>
          {choosePizza && (
            <PizzaTemplatePicker
              component={c}
              source={pizzaTemplates}
              onChange={(patch) => update(index, patch)}
            />
          )}
          <Num
            label="Pagination par multiple de"
            value={c.page_multiple || 1}
            min={1}
            max={32}
            step="1"
            onChange={(page_multiple) => update(index, { page_multiple })}
          />
          <h4>Fichiers PDF attendus</h4>
          <p className="field-hint">
            Un emplacement par fichier, avec pagination exacte. Pour fournir recto et verso
            ensemble, créez un emplacement de deux pages. Une finition avec masque ajoute
            automatiquement un PDF par composant.
          </p>
          {c.slots.map((s, slotIndex) => (
            <div className="print-slot" key={s.id}>
              <Text
                label={`Emplacement ${slotIndex + 1}`}
                value={s.name}
                onChange={(name) =>
                  update(index, {
                    slots: c.slots.map((s, i) => (i === slotIndex ? { ...s, name } : s)),
                  })
                }
              />
              <Num
                label="Pages attendues"
                value={s.pages}
                min={1}
                max={200}
                step="1"
                onChange={(pages) =>
                  update(index, {
                    slots: c.slots.map((s, i) => (i === slotIndex ? { ...s, pages } : s)),
                  })
                }
              />
              <Select
                label="Rôle"
                value={s.role}
                onChange={(role) =>
                  update(index, {
                    slots: c.slots.map((s, i) =>
                      i === slotIndex ? { ...s, role: role as Slot['role'] } : s,
                    ),
                  })
                }
              >
                <option value="visual">Visuel</option>
                <option value="mask">Masque technique</option>
              </Select>
              <Button
                variant="outline"
                className="print-action-button print-action-button-remove"
                type="button"
                disabled={c.slots.length <= 1}
                aria-label={`Retirer l’emplacement ${slotIndex + 1}`}
                onClick={() => update(index, { slots: c.slots.filter((_, i) => i !== slotIndex) })}
              >
                <Trash2 size={18} aria-hidden="true" /> Retirer
              </Button>
            </div>
          ))}
          <Button
            variant="outline"
            className="print-action-button"
            type="button"
            disabled={c.slots.length >= 30}
            onClick={() =>
              update(index, {
                slots: [...c.slots, { id: newId(), name: 'Verso', pages: 1, role: 'visual' }],
              })
            }
          >
            <Plus size={18} aria-hidden="true" />
            Ajouter un emplacement
          </Button>
          <h4>Gabarits et tracés</h4>
          {c.guides.map((g, gi) => (
            <fieldset className="print-block print-guide" key={g.tool}>
              <legend>{guideNames[g.tool]}</legend>
              {g.tool === 'perforation' ? (
                <>
                  <Select
                    label="Sens des perforations"
                    value={String(g.settings.axis || 'vertical')}
                    onChange={(axis) =>
                      update(index, {
                        guides: c.guides.map((g, i) =>
                          i === gi ? { ...g, settings: { ...g.settings, axis } } : g,
                        ),
                      })
                    }
                  >
                    <option value="vertical">Vertical</option>
                    <option value="horizontal">Horizontal</option>
                  </Select>
                  <PerforationPositions
                    positions={Array.isArray(g.settings.positions) ? g.settings.positions : [30]}
                    onChange={(positions) =>
                      update(index, {
                        guides: c.guides.map((g, i) =>
                          i === gi ? { ...g, settings: { ...g.settings, positions } } : g,
                        ),
                      })
                    }
                  />
                </>
              ) : g.tool === 'pizza' && c.pizza_template ? (
                <p className="field-hint">Gabarit Pizza : {c.pizza_template.name}</p>
              ) : (
                <div className="tool-fields">
                  {tools
                    .find((t) => t.id === g.tool)
                    ?.fields.filter(
                      (f) =>
                        !['width', 'height', 'bleed'].includes(f.key) &&
                        (g.tool !== 'taco' || visibleTacoField(f.key, g.settings)) &&
                        !(g.tool === 'pizza' && /^(width|height)_/.test(f.key)),
                    )
                    .map((f) => {
                      const value =
                        g.settings[f.key] ??
                        (g.tool === 'pizza' && f.key.startsWith('safety_')
                          ? g.settings.safety
                          : undefined) ??
                        f.default
                      const change = (value: string | number) =>
                        update(index, {
                          guides: c.guides.map((g, i) =>
                            i === gi ? { ...g, settings: { ...g.settings, [f.key]: value } } : g,
                          ),
                        })
                      return f.type === 'select' ? (
                        <Select key={f.key} label={f.label} value={String(value)} onChange={change}>
                          {f.options?.map((o) => (
                            <option key={o.value} value={o.value}>
                              {o.label}
                            </option>
                          ))}
                        </Select>
                      ) : f.type === 'number' ? (
                        <Num
                          key={f.key}
                          label={`${f.label}${f.unit ? ` (${f.unit})` : ''}`}
                          value={Number(value)}
                          min={f.min ?? 0}
                          max={f.max ?? 5000}
                          onChange={change}
                        />
                      ) : (
                        <Text key={f.key} label={f.label} value={String(value)} onChange={change} />
                      )
                    })}
                </div>
              )}
              <Button
                variant="outline"
                className="print-action-button print-action-button-remove"
                type="button"
                disabled={g.tool === 'pizza' && !!c.pizza_template}
                onClick={() => update(index, { guides: c.guides.filter((_, i) => i !== gi) })}
              >
                <Trash2 size={18} aria-hidden="true" /> Retirer ce tracé
              </Button>
            </fieldset>
          ))}
          <Select
            label="Ajouter un tracé"
            value=""
            onChange={(tool) => {
              if (tool)
                update(index, {
                  guides: [
                    ...c.guides,
                    {
                      tool: tool as Guide['tool'],
                      settings:
                        tool === 'perforation'
                          ? { axis: 'vertical', positions: [Math.min(30, c.width / 3)] }
                          : {},
                    },
                  ],
                })
            }}
          >
            <option value="">Choisir un outil…</option>
            {Object.entries(guideNames)
              .filter(
                ([id]) =>
                  !(choosePizza && id === 'pizza') &&
                  !c.guides.some((g) => g.tool === id) &&
                  !(id === 'pizza' && c.guides.some((g) => g.tool === 'sushi')) &&
                  !(id === 'sushi' && c.guides.some((g) => g.tool === 'pizza')),
              )
              .map(([id, name]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
          </Select>
          <p className="field-hint">
            Les tracés partagent les dimensions du composant. Pizza et Sushi sont deux références de
            découpe alternatives. Les tracés sont téléchargeables séparément à l’échelle 1:1.
          </p>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={!!c.tickets}
              onChange={(e) =>
                update(index, { tickets: e.target.checked ? newTickets(c.height) : null })
              }
            />
            <span>Billets ou coupons numérotés</span>
          </label>
          {c.tickets && (
            <TicketEditor value={c.tickets} onChange={(tickets) => update(index, { tickets })} />
          )}
          <Button
            variant="outline"
            className="print-action-button print-action-button-remove"
            type="button"
            disabled={variant.components.length <= 1}
            onClick={() =>
              onChange({ ...variant, components: variant.components.filter((_, i) => i !== index) })
            }
          >
            <Trash2 size={18} aria-hidden="true" />
            Retirer ce composant
          </Button>
        </fieldset>
      ))}
      <Button
        variant="outline"
        className="print-action-button"
        type="button"
        disabled={variant.components.length >= 12}
        onClick={() =>
          onChange({ ...variant, components: [...variant.components, newComponent()] })
        }
      >
        <Plus size={18} aria-hidden="true" />
        Ajouter un composant
      </Button>
    </>
  )
}

export type FileRequirement = { label: string; hint?: string }

export function snapshotFiles(snapshot: Snapshot): FileRequirement[] {
  return snapshot.variant.components.flatMap((c) => {
    const visuals = c.slots.filter((s) => s.role === 'visual')
    const pages = visuals.reduce((sum, s) => sum + s.pages, 0)
    const scope =
      visuals.length <= 4
        ? visuals.map((s) => s.name).join(', ')
        : `${visuals.length} fichiers visuels du composant « ${c.name} »`
    const mask = (name: string): FileRequirement => ({
      label: `${c.name} — Masque de finition : ${name}`,
      hint: `Pour : ${scope}. ${pages} page${pages > 1 ? 's' : ''}, dans l’ordre des visuels.`,
    })
    return [
      ...c.slots.map((s) =>
        s.role === 'mask'
          ? {
              ...mask(s.name),
              hint: `Pour les visuels du composant « ${c.name} ». ${s.pages} page${s.pages > 1 ? 's' : ''} attendue${s.pages > 1 ? 's' : ''}.`,
            }
          : { label: `${c.name} — ${s.name}` },
      ),
      ...snapshot.finishes
        .filter((f) => f.mask && snapshot.variant.finish_ids.includes(f.id))
        .map((f) => mask(f.name)),
    ]
  })
}

export function snapshotLabels(snapshot: Snapshot): string[] {
  return snapshotFiles(snapshot).map((file) => file.label)
}
export function makeSnapshot(product: Product, variant: Variant, catalog: PrintCatalog): Snapshot {
  return clone({
    schema_version: 1,
    product_name: product.name,
    category_name:
      catalog.categories.find((c) => c.id === product.category_id)?.name || 'Mode libre',
    variant,
    materials: catalog.materials.filter((m) => product.material_ids.includes(m.id)),
    finishes: catalog.finishes.filter((f) => product.finish_ids.includes(f.id)),
  })
}

export function PrintCatalogPage({ tools }: { tools: Tool[] }) {
  const { user, loading } = useAccount()
  return (
    <CatalogManager
      key={user?.id || 'guest'}
      tools={tools}
      signedIn={!!user}
      accountLoading={loading}
    />
  )
}
function CatalogManager({
  tools,
  signedIn,
  accountLoading,
}: {
  tools: Tool[]
  signedIn: boolean
  accountLoading: boolean
}) {
  const { open } = useAccount()
  const source = usePrintCatalog()
  const [draft, setDraft] = useState<PrintCatalog | null>(null)
  const [selectedId, setSelectedId] = useState('')
  const [expandedMaterialId, setExpandedMaterialId] = useState('')
  const [expandedFinishId, setExpandedFinishId] = useState('')
  const [variantIndex, setVariantIndex] = useState(0)
  const [tab, setTab] = useState('products')
  const [category, setCategory] = useState('')
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  useEffect(() => {
    if (source.library) {
      setDraft(clone(source.library.catalog))
      setSelectedId(source.library.catalog.products[0]?.id || '')
    }
  }, [source.library])
  const product = draft?.products.find((p) => p.id === selectedId)
  const variant = product?.variants[variantIndex] || product?.variants[0]
  const dirty = !!draft && JSON.stringify(draft) !== JSON.stringify(source.library?.catalog)
  function updateProduct(patch: Partial<Product>) {
    if (draft && product) {
      setDraft({
        ...draft,
        products: draft.products.map((p) => (p.id === product.id ? { ...p, ...patch } : p)),
      })
      setNotice('')
    }
  }
  async function save(e: React.FormEvent) {
    e.preventDefault()
    if (!draft) return
    setError('')
    setNotice('')
    try {
      await source.save(draft)
      setNotice('Catalogue enregistré dans votre compte.')
    } catch (e) {
      setError((e as Error).message)
    }
  }
  return (
    <main className="studio-main print-catalog">
      <div className="catalog-intro">
        <div>
          <h1>
            Produits d’impression<span>.</span>
          </h1>
          <p className="catalog-description">
            Les matières, les fichiers et les tracés de vos prochains BAT.
          </p>
        </div>
        <a href="/?tool=burger">Créer un BAT →</a>
      </div>
      {(error || source.error) && (
        <p className="alert error" role="alert">
          {error || source.error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {!draft || accountLoading ? (
        <p role="status">
          Chargement du catalogue…{' '}
          {source.error && (
            <Button variant="outline" className="print-action-button" onClick={source.reload}>
              <RotateCw size={18} aria-hidden="true" /> Réessayer
            </Button>
          )}
        </p>
      ) : (
        <>
          <div className="print-savebar">
            <p>
              {signedIn
                ? dirty
                  ? 'Modifications non enregistrées'
                  : `Catalogue personnel · version ${source.library?.revision || 0}`
                : 'Gamme de départ. Connectez-vous pour personnaliser et enregistrer votre catalogue.'}
            </p>
            {!signedIn && <Button onClick={open}>Se connecter</Button>}
          </div>
          <div className="print-library-toolbar">
            <nav className="catalog-tabs" aria-label="Bibliothèques d’impression">
              {[
                ['products', 'Produits'],
                ['categories', 'Catégories'],
                ['materials', 'Supports matières'],
                ['finishes', 'Façonnages et finitions'],
              ].map(([id, name]) => (
                <button
                  key={id}
                  className={tab === id ? 'selected' : ''}
                  onClick={() => setTab(id)}
                >
                  {name}
                </button>
              ))}
            </nav>
            <Button
              variant="outline"
              className="print-action-button"
              type="button"
              disabled={source.busy}
              onClick={() => {
                source.reload()
                setError('')
                setNotice('')
              }}
            >
              <RotateCw size={18} aria-hidden="true" /> Recharger le catalogue
            </Button>
          </div>
          <form onSubmit={save}>
            <fieldset disabled={source.busy}>
              {tab === 'products' ? (
                <div className="print-layout">
                  <aside className="print-list">
                    <label className="field">
                      Rechercher un produit
                      <input
                        type="search"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                      />
                    </label>
                    <Select label="Filtrer par catégorie" value={category} onChange={setCategory}>
                      <option value="">Toutes les catégories</option>
                      {draft.categories.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </Select>
                    {draft.products
                      .filter(
                        (p) =>
                          (!category ||
                            p.category_id === category ||
                            draft.categories.find((c) => c.id === p.category_id)?.parent_id ===
                              category) &&
                          p.name.toLocaleLowerCase('fr').includes(search.toLocaleLowerCase('fr')),
                      )
                      .map((p) => (
                        <button
                          type="button"
                          key={p.id}
                          className={p.id === selectedId ? 'selected' : ''}
                          onClick={() => {
                            setSelectedId(p.id)
                            setVariantIndex(0)
                          }}
                        >
                          <strong>{p.name}</strong>
                          <small>{p.variants.length} déclinaison(s)</small>
                        </button>
                      ))}
                    <Button
                      variant="outline"
                      className="print-action-button"
                      type="button"
                      disabled={!draft.categories.length}
                      onClick={() => {
                        const p: Product = {
                          id: newId(),
                          name: 'Nouveau produit',
                          category_id: draft.categories[0].id,
                          description: '',
                          material_ids: draft.materials.map((m) => m.id),
                          finish_ids: [],
                          variants: [newVariant()],
                        }
                        setDraft({ ...draft, products: [...draft.products, p] })
                        setSelectedId(p.id)
                        setVariantIndex(0)
                      }}
                    >
                      <Plus size={18} aria-hidden="true" /> Ajouter un produit
                    </Button>
                  </aside>
                  <section className="print-edit">
                    {product && variant ? (
                      <>
                        <div className="tool-fields">
                          <Text
                            label="Nom du produit"
                            value={product.name}
                            onChange={(name) => updateProduct({ name })}
                          />
                          <Select
                            label="Catégorie du produit"
                            value={product.category_id}
                            onChange={(category_id) => updateProduct({ category_id })}
                          >
                            {draft.categories.map((c) => (
                              <option key={c.id} value={c.id}>
                                {c.name}
                              </option>
                            ))}
                          </Select>
                        </div>
                        <label className="field tool-field">
                          <span>Description</span>
                          <textarea
                            rows={4}
                            value={product.description}
                            maxLength={1000}
                            onChange={(e) => updateProduct({ description: e.target.value })}
                          />
                        </label>
                        <Checks
                          title="Supports autorisés"
                          rows={draft.materials}
                          selected={product.material_ids}
                          onChange={(material_ids) => updateProduct({ material_ids })}
                        />
                        <Checks
                          title="Façonnages et finitions disponibles"
                          rows={draft.finishes}
                          selected={product.finish_ids}
                          onChange={(finish_ids) => updateProduct({ finish_ids })}
                        />
                        <Select
                          label="Déclinaison à modifier"
                          value={variant.id}
                          onChange={(id) =>
                            setVariantIndex(product.variants.findIndex((v) => v.id === id))
                          }
                        >
                          {product.variants.map((v) => (
                            <option key={v.id} value={v.id}>
                              {v.name}
                            </option>
                          ))}
                        </Select>
                        <div className="print-actions">
                          <Button
                            variant="outline"
                            className="print-action-button"
                            type="button"
                            disabled={product.variants.length >= 30}
                            onClick={() => {
                              updateProduct({
                                variants: [
                                  ...product.variants,
                                  {
                                    ...clone(variant),
                                    id: newId(),
                                    name: `${variant.name} — copie`,
                                  },
                                ],
                              })
                              setVariantIndex(product.variants.length)
                            }}
                          >
                            <Copy size={18} aria-hidden="true" />
                            Dupliquer la déclinaison
                          </Button>
                          <Button
                            variant="outline"
                            className="print-action-button print-action-button-remove"
                            type="button"
                            disabled={product.variants.length <= 1}
                            onClick={() => {
                              updateProduct({
                                variants: product.variants.filter((v) => v.id !== variant.id),
                              })
                              setVariantIndex(0)
                            }}
                          >
                            <Trash2 size={18} aria-hidden="true" />
                            Retirer la déclinaison
                          </Button>
                        </div>
                        <VariantEditor
                          choosePizza
                          variant={variant}
                          materials={draft.materials.filter((m) =>
                            product.material_ids.includes(m.id),
                          )}
                          finishes={draft.finishes.filter((f) => product.finish_ids.includes(f.id))}
                          tools={tools}
                          onChange={(next) =>
                            updateProduct({
                              variants: product.variants.map((v) =>
                                v.id === variant.id ? next : v,
                              ),
                            })
                          }
                        />
                        <div className="print-actions">
                          <Button
                            variant="outline"
                            className="print-action-button"
                            type="button"
                            onClick={() => {
                              const p = {
                                ...clone(product),
                                id: newId(),
                                name: `${product.name} — copie`,
                              }
                              setDraft({ ...draft, products: [...draft.products, p] })
                              setSelectedId(p.id)
                              setVariantIndex(0)
                            }}
                          >
                            <Copy size={18} aria-hidden="true" /> Dupliquer le produit
                          </Button>
                          <Button
                            variant="outline"
                            className="print-action-button print-action-button-remove"
                            type="button"
                            onClick={() => {
                              setDraft({
                                ...draft,
                                products: draft.products.filter((p) => p.id !== product.id),
                              })
                              setSelectedId('')
                            }}
                          >
                            <Trash2 size={18} aria-hidden="true" /> Retirer le produit
                          </Button>
                        </div>
                      </>
                    ) : (
                      <p>Sélectionnez un produit ou créez-en un.</p>
                    )}
                  </section>
                </div>
              ) : tab === 'categories' ? (
                <section className="print-edit">
                  <h2>Catégories et sous-catégories</h2>
                  {draft.categories.map((c, i) => (
                    <div className="print-slot" key={c.id}>
                      <Text
                        label="Nom de la catégorie"
                        value={c.name}
                        onChange={(name) =>
                          setDraft({
                            ...draft,
                            categories: draft.categories.map((c, n) =>
                              n === i ? { ...c, name } : c,
                            ),
                          })
                        }
                      />
                      <Select
                        label="Catégorie parente"
                        value={c.parent_id || ''}
                        onChange={(parent_id) =>
                          setDraft({
                            ...draft,
                            categories: draft.categories.map((c, n) =>
                              n === i ? { ...c, parent_id: parent_id || null } : c,
                            ),
                          })
                        }
                      >
                        <option value="">À la racine</option>
                        {draft.categories
                          .filter((row) => row.id !== c.id)
                          .map((row) => (
                            <option key={row.id} value={row.id}>
                              {row.name}
                            </option>
                          ))}
                      </Select>
                      <Button
                        variant="outline"
                        className="print-action-button print-action-button-remove"
                        type="button"
                        disabled={
                          draft.products.some((p) => p.category_id === c.id) ||
                          draft.categories.some((row) => row.parent_id === c.id)
                        }
                        onClick={() =>
                          setDraft({
                            ...draft,
                            categories: draft.categories.filter((_, n) => n !== i),
                          })
                        }
                      >
                        <Trash2 size={18} aria-hidden="true" /> Retirer
                      </Button>
                    </div>
                  ))}
                  <Button
                    variant="outline"
                    className="print-action-button"
                    type="button"
                    onClick={() =>
                      setDraft({
                        ...draft,
                        categories: [
                          ...draft.categories,
                          { id: newId(), name: 'Nouvelle catégorie', parent_id: null },
                        ],
                      })
                    }
                  >
                    <Plus size={18} aria-hidden="true" />
                    Ajouter une catégorie
                  </Button>
                </section>
              ) : tab === 'materials' ? (
                <section className="print-edit">
                  <h2>Bibliothèque des supports matières</h2>
                  <Accordion
                    type="single"
                    collapsible
                    value={expandedMaterialId}
                    onValueChange={setExpandedMaterialId}
                  >
                    {draft.materials.map((m, i) => (
                      <AccordionItem key={m.id} value={m.id}>
                        <AccordionTrigger>{m.name}</AccordionTrigger>
                        <AccordionContent>
                          <div className="tool-fields">
                            <Text
                              label="Nom du support"
                              value={m.name}
                              onChange={(name) =>
                                setDraft({
                                  ...draft,
                                  materials: draft.materials.map((m, n) =>
                                    n === i ? { ...m, name } : m,
                                  ),
                                })
                              }
                            />
                            <Text
                              label="Famille de matière"
                              value={m.family}
                              onChange={(family) =>
                                setDraft({
                                  ...draft,
                                  materials: draft.materials.map((m, n) =>
                                    n === i ? { ...m, family } : m,
                                  ),
                                })
                              }
                            />
                            <Num
                              label="Grammage (g/m², 0 si non renseigné)"
                              value={m.gsm || 0}
                              max={3000}
                              onChange={(gsm) =>
                                setDraft({
                                  ...draft,
                                  materials: draft.materials.map((m, n) =>
                                    n === i ? { ...m, gsm: gsm || null } : m,
                                  ),
                                })
                              }
                            />
                            <Num
                              label="Épaisseur (mm, 0 si non renseignée)"
                              value={m.thickness || 0}
                              max={100}
                              onChange={(thickness) =>
                                setDraft({
                                  ...draft,
                                  materials: draft.materials.map((m, n) =>
                                    n === i ? { ...m, thickness: thickness || null } : m,
                                  ),
                                })
                              }
                            />
                          </div>
                          <Button
                            variant="outline"
                            className="print-action-button print-action-button-remove"
                            type="button"
                            disabled={
                              draft.products.some((p) => p.material_ids.includes(m.id)) ||
                              draft.finishes.some((f) => f.material_ids.includes(m.id))
                            }
                            onClick={() =>
                              setDraft({
                                ...draft,
                                materials: draft.materials.filter((_, n) => n !== i),
                              })
                            }
                          >
                            <Trash2 size={18} aria-hidden="true" /> Retirer le support
                          </Button>
                        </AccordionContent>
                      </AccordionItem>
                    ))}
                  </Accordion>
                  <Button
                    variant="outline"
                    className="print-action-button"
                    type="button"
                    onClick={() => {
                      const material: Material = {
                        id: newId(),
                        name: 'Nouveau support',
                        family: 'Papier',
                        gsm: null,
                        thickness: null,
                        description: '',
                      }
                      setDraft({ ...draft, materials: [...draft.materials, material] })
                      setExpandedMaterialId(material.id)
                    }}
                  >
                    <Plus size={18} aria-hidden="true" />
                    Ajouter un support
                  </Button>
                </section>
              ) : (
                <section className="print-edit">
                  <h2>Façonnages et finitions</h2>
                  <Accordion
                    type="single"
                    collapsible
                    value={expandedFinishId}
                    onValueChange={setExpandedFinishId}
                  >
                    {draft.finishes.map((f, i) => (
                      <AccordionItem key={f.id} value={f.id}>
                        <AccordionTrigger>{f.name}</AccordionTrigger>
                        <AccordionContent>
                          <Text
                            label="Nom de la finition"
                            value={f.name}
                            onChange={(name) =>
                              setDraft({
                                ...draft,
                                finishes: draft.finishes.map((f, n) =>
                                  n === i ? { ...f, name } : f,
                                ),
                              })
                            }
                          />
                          <label className="checkbox-label">
                            <input
                              type="checkbox"
                              checked={f.mask}
                              onChange={(e) =>
                                setDraft({
                                  ...draft,
                                  finishes: draft.finishes.map((f, n) =>
                                    n === i ? { ...f, mask: e.target.checked } : f,
                                  ),
                                })
                              }
                            />
                            <span>Demander un PDF de masque séparé</span>
                          </label>
                          <FinishAppearanceEditor
                            finish={f}
                            onChange={(appearance) =>
                              setDraft({
                                ...draft,
                                finishes: draft.finishes.map((row, n) =>
                                  n === i ? { ...row, appearance } : row,
                                ),
                              })
                            }
                          />
                          <Checks
                            title="Supports compatibles (aucun = tous)"
                            rows={draft.materials}
                            selected={f.material_ids}
                            onChange={(material_ids) =>
                              setDraft({
                                ...draft,
                                finishes: draft.finishes.map((f, n) =>
                                  n === i ? { ...f, material_ids } : f,
                                ),
                              })
                            }
                          />
                          <Checks
                            title="Finitions incompatibles"
                            rows={draft.finishes.filter((row) => row.id !== f.id)}
                            selected={f.excludes}
                            onChange={(excludes) =>
                              setDraft({
                                ...draft,
                                finishes: draft.finishes.map((f, n) =>
                                  n === i ? { ...f, excludes } : f,
                                ),
                              })
                            }
                          />
                          <Button
                            variant="outline"
                            className="print-action-button print-action-button-remove"
                            type="button"
                            disabled={
                              draft.products.some((p) => p.finish_ids.includes(f.id)) ||
                              draft.finishes.some((row) => row.excludes.includes(f.id))
                            }
                            onClick={() =>
                              setDraft({
                                ...draft,
                                finishes: draft.finishes.filter((_, n) => n !== i),
                              })
                            }
                          >
                            <Trash2 size={18} aria-hidden="true" /> Retirer la finition
                          </Button>
                        </AccordionContent>
                      </AccordionItem>
                    ))}
                  </Accordion>
                  <Button
                    variant="outline"
                    className="print-action-button"
                    type="button"
                    onClick={() => {
                      const finish: Finish = {
                        id: newId(),
                        name: 'Nouvelle finition',
                        mask: false,
                        material_ids: [],
                        excludes: [],
                      }
                      setDraft({ ...draft, finishes: [...draft.finishes, finish] })
                      setExpandedFinishId(finish.id)
                    }}
                  >
                    <Plus size={18} aria-hidden="true" /> Ajouter une finition
                  </Button>
                </section>
              )}
            </fieldset>
            <div className="print-savebar">
              <p>
                {dirty
                  ? 'Enregistrez pour rendre ces choix disponibles dans le BAT.'
                  : 'Les BAT existants conservent leurs spécifications.'}
              </p>
              <Button type="submit" disabled={!signedIn || source.busy || !dirty}>
                {source.busy ? 'Enregistrement…' : 'Enregistrer le catalogue'}
              </Button>
            </div>
          </form>
        </>
      )}
    </main>
  )
}

export function ProductSelector({
  sourceMode,
  snapshot,
  tools,
  onChange,
  catalogOnly = false,
}: {
  sourceMode: 'classic' | 'catalog' | 'free'
  snapshot: Snapshot | null
  tools: Tool[]
  onChange: (v: Snapshot | null, mode?: 'legacy' | 'catalog' | 'free') => void
  catalogOnly?: boolean
}) {
  const { user } = useAccount()
  return (
    <PersonalProductSelector
      key={user?.id || 'guest'}
      sourceMode={sourceMode}
      snapshot={snapshot}
      tools={tools}
      onChange={onChange}
      catalogOnly={catalogOnly}
    />
  )
}
function PersonalProductSelector({
  sourceMode,
  snapshot,
  tools,
  onChange,
  catalogOnly,
}: {
  sourceMode: 'classic' | 'catalog' | 'free'
  snapshot: Snapshot | null
  tools: Tool[]
  onChange: (v: Snapshot | null, mode?: 'legacy' | 'catalog' | 'free') => void
  catalogOnly: boolean
}) {
  const { user, open } = useAccount()
  const source = usePrintCatalog()
  const mode = sourceMode === 'classic' ? 'legacy' : sourceMode
  const [categoryId, setCategoryId] = useState('')
  const [productId, setProductId] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [customize, setCustomize] = useState(false)
  const catalog = source.library?.catalog
  useEffect(() => {
    if (!catalog) return
    if (!snapshot && mode === 'free') {
      onChange(
        {
          schema_version: 1,
          product_name: 'Produit sur mesure',
          category_name: 'Mode libre',
          variant: newVariant(),
          materials: clone(catalog.materials),
          finishes: clone(catalog.finishes),
        },
        'free',
      )
    } else if (!snapshot && mode === 'catalog' && !categoryId && catalog.products[0]) {
      const first = catalog.products[0]
      setProductId(first.id)
      onChange(makeSnapshot(first, first.variants[0], catalog), 'catalog')
    } else if (snapshot && !productId && mode === 'catalog') {
      const match = catalog.products.find(
        (p) =>
          p.name === snapshot.product_name && p.variants.some((v) => v.id === snapshot.variant.id),
      )
      if (match) setProductId(match.id)
    }
  }, [catalog, snapshot, mode, categoryId, productId, onChange])

  useEffect(() => {
    if (mode === 'catalog' && snapshot && catalog) {
      const match = catalog.products.find((p) =>
        p.variants.some((v) => v.id === snapshot.variant.id),
      )
      setProductId(match?.id || '')
    }
  }, [catalog, mode, snapshot?.variant.id])
  const product = catalog?.products.find((p) => p.id === productId)
  const categoryProducts =
    catalog?.products.filter(
      (p) =>
        !categoryId ||
        p.category_id === categoryId ||
        catalog.categories.find((c) => c.id === p.category_id)?.parent_id === categoryId,
    ) || []
  function selectProduct(id: string) {
    const p = catalog?.products.find((p) => p.id === id)
    setProductId(id)
    setCustomize(false)
    if (p && catalog) onChange(makeSnapshot(p, p.variants[0], catalog), 'catalog')
  }
  async function saveProduct() {
    if (!snapshot || !catalog) return
    if (!user) {
      open()
      return
    }
    setError('')
    setNotice('')
    const category = catalog.categories.find((c) => c.id === categoryId) || catalog.categories[0]
    if (!category) {
      setError('Créez une catégorie dans le catalogue avant d’enregistrer.')
      return
    }
    const p: Product = {
      id: newId(),
      name: snapshot.product_name,
      category_id: category.id,
      description: '',
      material_ids: snapshot.materials.map((m) => m.id),
      finish_ids: snapshot.finishes.map((f) => f.id),
      variants: [clone(snapshot.variant)],
    }
    try {
      await source.save({ ...catalog, products: [...catalog.products, p] })
      setProductId(p.id)
      setCategoryId(category.id)
      onChange(snapshot, 'catalog')
      setNotice('Produit enregistré dans votre catalogue.')
    } catch (e) {
      setError((e as Error).message)
    }
  }
  return (
    <section className="tool-settings-section print-selector">
      <h2>Produit d’impression</h2>
      {!catalogOnly && (
        <Select
          label="Mode du BAT"
          value={snapshot ? (mode === 'legacy' ? 'catalog' : mode) : mode}
          onChange={(mode) => {
            setError('')
            setNotice('')
            if (mode === 'legacy') onChange(null, 'legacy')
            else if (mode === 'free' && catalog)
              onChange(
                {
                  schema_version: 1,
                  product_name: 'Produit sur mesure',
                  category_name: 'Mode libre',
                  variant: newVariant(),
                  materials: clone(catalog.materials),
                  finishes: clone(catalog.finishes),
                },
                'free',
              )
            else if (mode === 'catalog' && catalog?.products[0])
              selectProduct(catalog.products[0].id)
            else onChange(null, mode as 'catalog' | 'free')
          }}
        >
          <option value="legacy">Composition classique</option>
          <option value="catalog">Depuis le catalogue</option>
          <option value="free">Mode libre configurable</option>
        </Select>
      )}
      {(source.error || error) && (
        <p className="alert error" role="alert">
          {source.error || error}
          <Button
            variant="outline"
            className="print-action-button"
            type="button"
            onClick={source.reload}
          >
            <RotateCw size={18} aria-hidden="true" /> Recharger le catalogue
          </Button>
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {mode !== 'legacy' && !catalog && <p role="status">Chargement des produits…</p>}
      {mode === 'catalog' && catalog && (
        <>
          <Select
            label="Catégorie de produit"
            value={categoryId}
            onChange={(id) => {
              setCategoryId(id)
              const next = catalog.products.find(
                (p) =>
                  p.category_id === id ||
                  catalog.categories.find((c) => c.id === p.category_id)?.parent_id === id,
              )
              if (!id && catalog.products[0]) selectProduct(catalog.products[0].id)
              else if (next) selectProduct(next.id)
              else {
                setProductId('')
                onChange(null)
              }
            }}
          >
            <option value="">Toutes les catégories</option>
            {catalog.categories.map((c) => (
              <option value={c.id} key={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
          <Select label="Produit" value={productId} onChange={selectProduct}>
            <option value="">Choisir un produit…</option>
            {categoryProducts.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </Select>
          {product && (
            <Select
              label="Déclinaison du produit"
              value={snapshot?.variant.id || ''}
              onChange={(id) => {
                const v = product.variants.find((v) => v.id === id)
                if (v) onChange(makeSnapshot(product, v, catalog))
              }}
            >
              {product.variants.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </Select>
          )}
          {!categoryProducts.length && <p>Aucun produit dans cette catégorie.</p>}
        </>
      )}
      {snapshot && mode !== 'legacy' && (
        <>
          <p className="privacy-note">
            <strong>
              {snapshot.product_name} — {snapshot.variant.name}
            </strong>
            <br />
            {snapshot.variant.components.map((c) => (
              <span key={c.id}>
                {c.name} — format fini : {c.width.toLocaleString('fr-FR')} ×{' '}
                {c.height.toLocaleString('fr-FR')} mm. Fond perdu :{' '}
                {c.bleed.toLocaleString('fr-FR')} mm sur chaque côté.{' '}
                <strong>
                  Fichier attendu : {(c.width + 2 * c.bleed).toLocaleString('fr-FR')} ×{' '}
                  {(c.height + 2 * c.bleed).toLocaleString('fr-FR')} mm.
                </strong>
                <br />
              </span>
            ))}
          </p>
          {mode === 'catalog' &&
            !customize &&
            snapshot.variant.components.map(
              (c, index) =>
                c.pizza_template && (
                  <div key={c.id} className="print-block">
                    <h4>
                      {c.name} — {c.pizza_template.name}
                    </h4>
                    <div className="tool-fields">
                      <ComponentDimensions
                        component={c}
                        onChange={(patch) =>
                          onChange({
                            ...snapshot,
                            variant: {
                              ...snapshot.variant,
                              components: snapshot.variant.components.map((item, i) =>
                                i === index ? { ...item, ...patch } : item,
                              ),
                            },
                          })
                        }
                      />
                    </div>
                  </div>
                ),
            )}
          {mode === 'catalog' && (
            <Checks
              title={catalogOnly ? 'Finitions de fabrication' : 'Options du BAT'}
              rows={snapshot.finishes}
              selected={snapshot.variant.finish_ids}
              onChange={(finish_ids) =>
                onChange({ ...snapshot, variant: { ...snapshot.variant, finish_ids } })
              }
            />
          )}
          {mode === 'catalog' && !catalogOnly && (
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={customize}
                onChange={(e) => setCustomize(e.target.checked)}
              />
              <span>Adapter les spécifications pour ce BAT</span>
            </label>
          )}
          {(mode === 'free' || customize) && (
            <>
              <Text
                label="Nom du produit pour ce BAT"
                value={snapshot.product_name}
                onChange={(product_name) => onChange({ ...snapshot, product_name })}
              />
              <VariantEditor
                variant={snapshot.variant}
                materials={snapshot.materials}
                finishes={snapshot.finishes}
                tools={tools}
                onChange={(variant) => onChange({ ...snapshot, variant })}
              />
              <Button
                variant="outline"
                className="print-action-button"
                type="button"
                disabled={source.busy}
                onClick={() => void saveProduct()}
              >
                <Save size={18} aria-hidden="true" /> Enregistrer comme nouveau produit
              </Button>
            </>
          )}
          {!catalogOnly && snapshot.variant.finish_ids.length > 0 && (
            <section aria-label="Apparence des finitions sur le BAT">
              <h3>Apparence des finitions sur le BAT</h3>
              <p className="field-hint">
                Ouvrez une finition pour choisir une zone ou un tracé, sa couleur et ses effets. Ces
                réglages s’appliquent à ce BAT.
              </p>
              <Accordion type="multiple">
                {snapshot.finishes
                  .filter((finish) => snapshot.variant.finish_ids.includes(finish.id))
                  .map((finish) => (
                    <AccordionItem key={finish.id} value={finish.id}>
                      <AccordionTrigger>
                        {finish.name} —{' '}
                        {finish.appearance?.mode === 'area'
                          ? 'Zone'
                          : finish.appearance?.mode === 'path'
                            ? 'Tracé'
                            : 'Aucun effet'}
                      </AccordionTrigger>
                      <AccordionContent>
                        <FinishAppearanceEditor
                          finish={finish}
                          onChange={(appearance) =>
                            onChange({
                              ...snapshot,
                              finishes: snapshot.finishes.map((row) =>
                                row.id === finish.id ? { ...row, appearance } : row,
                              ),
                            })
                          }
                        />
                      </AccordionContent>
                    </AccordionItem>
                  ))}
              </Accordion>
            </section>
          )}
          <p className="field-hint">
            {catalogOnly
              ? 'Le produit, ses composants, ses supports et les finitions choisies seront figés dans la fiche de fabrication et ses réglages.'
              : 'PDF uniquement. Les formats finis, les fonds perdus et les pages sont contrôlés. La configuration sera figée dans le BAT et ses réglages.'}
          </p>
          {!catalogOnly && (
            <ol className="field-hint">
              {snapshotLabels(snapshot).map((label, i) => (
                <li key={i}>{label}</li>
              ))}
            </ol>
          )}
        </>
      )}
      <a href="/?view=products">Gérer les produits, matières et finitions →</a>
    </section>
  )
}

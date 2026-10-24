import { useEffect, useId, useRef, useState } from 'react'
import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  FileCheck2,
  FileText,
  LayoutGrid,
  LoaderCircle,
  Search,
  SlidersHorizontal,
  Sparkles,
  Play,
  WandSparkles,
  Trash2,
  Upload,
  X,
} from 'lucide-react'
import App from './App'
import { PrintCatalogPage, ProductSelector, type Snapshot } from './PrintCatalog'
import { HeaderActions } from './HeaderActions'
import { Configurations } from './Configurations'
import {
  BurgerEditor,
  burgerDefaults,
  burgerFiles,
  burgerLabels,
  type BurgerOptions,
} from './BurgerEditor'
import { request } from './api'
import { Button } from './components/ui/button'
import { PdfFaceSwitch, PdfPreview } from './PdfPreview'
import { visibleTacoField } from './taco'
import { LivePreview, useLivePreview } from './LivePreview'
import {
  FortunePreview,
  FortuneSettings,
  FortuneTemplate,
  FortuneImposition,
  newNumbering,
  type Numbering,
} from './FortuneEditor'
import type { components } from '../../../packages/api-client/schema'
import { pizzaErrors, pizzaValue, visiblePizzaField } from './pizza'
import { PizzaSettings } from './PizzaSettings'
import { PizzaHighlight, pizzaFocusLabel } from './PizzaHighlight'
import { ToolSettings } from './ToolSettings'
import { ClubEstimate } from './ClubEstimate'
import { SettingsSection } from './SettingsSection'
import './studio.css'

type Tool = components['schemas']['ToolDefinition']
type ToolField = components['schemas']['ToolField']
type Result = components['schemas']['ToolResult']
type Values = Record<string, string | number>
const foodIds = [
  'burger',
  'chili-dog',
  'donut',
  'tiramisu',
  'taco',
  'pizza',
  'burrito',
  'club-sandwich',
  'fortune-cookie',
  'poke',
  'sushi',
  'kebab',
  'layer-cake',
  'bento',
]
const flavours = [
  'pink',
  'orange',
  'purple',
  'blue',
  'green',
  'yellow',
  'pink',
  'blue',
  'yellow',
  'purple',
  'green',
  'orange',
  'purple',
  'pink',
]
const accentMap: Record<string, string> = {
  Présenter: 'sage',
  Contrôler: 'peach',
  Préparer: 'yellow',
  Tracer: 'blue',
  Calculer: 'lilac',
  Personnaliser: 'rose',
  Assembler: 'sage',
}
const normalize = (value: string) =>
  value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
const toolUrl = (id: string) => `/?tool=${encodeURIComponent(id)}`
const assetUrl = (id: string, name: string) =>
  `/api/tool-jobs/${id}/files/${encodeURIComponent(name)}`
function ToolIcon({ tool, size = 22 }: { tool: Tool; size?: number }) {
  const index = foodIds.indexOf(tool.id)
  return (
    <span
      className={`tool-icon candy-art ${accentMap[tool.category]}`}
      data-snack={tool.id}
      aria-hidden="true"
    >
      {index >= 0 ? (
        <span
          className="food-sprite"
          style={{
            backgroundPosition: `${5 + (index % 4) * 30}% ${5 + Math.floor(index / 4) * 30}%`,
          }}
        />
      ) : (
        <FileText size={size} />
      )}
    </span>
  )
}
function Header() {
  return (
    <header className="topbar studio-header">
      <a href="/" className="brand" aria-label="Snackpress, tous les outils">
        <span className="brand-symbol">
          <img src="/snackpress.svg" width="32" height="32" alt="" />
        </span>
        snackpress<span className="brand-dot">.</span>
      </a>
      <HeaderActions />
      <span className="header-note">
        <WandSparkles size={17} />
        Les bons outils. La vie plus facile.
      </span>
    </header>
  )
}

export default function Studio() {
  const id = new URLSearchParams(window.location.search).get('tool')
  const [tools, setTools] = useState<Tool[]>([])
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    request<Tool[]>('/api/tools', { signal: controller.signal })
      .then(setTools)
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message)
      })
    return () => controller.abort()
  }, [])
  if (id === 'imposition') return <App />
  const selected = tools.find((t) => t.id === id)
  return (
    <>
      <Header />
      {new URLSearchParams(window.location.search).get('view') === 'products' && tools.length ? (
        <PrintCatalogPage tools={tools} />
      ) : error ? (
        <main className="studio-main">
          <div className="alert error" role="alert">
            {error}
          </div>
          <Button onClick={() => window.location.reload()}>Réessayer</Button>
        </main>
      ) : tools.length === 0 ? (
        <main className="studio-main loading-catalog" role="status">
          <LoaderCircle className="spin" size={22} />
          Chargement de l’atelier…
        </main>
      ) : id && !selected ? (
        <main className="studio-main">
          <h1>Outil introuvable.</h1>
          <a href="/">Revenir à tous les outils</a>
        </main>
      ) : selected ? (
        <ToolWorkspace key={selected.id} tool={selected} tools={tools} />
      ) : (
        <Catalog tools={tools} />
      )}
    </>
  )
}

function Catalog({ tools }: { tools: Tool[] }) {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('Tous')
  const categories = ['Tous', ...new Set(tools.map((t) => t.category))]
  const filtered = tools.filter(
    (t) =>
      (category === 'Tous' || t.category === category) &&
      normalize(`${t.name} ${t.description}`).includes(normalize(query)),
  )
  return (
    <main className="studio-main">
      <section className="catalog-intro">
        <div className="candy-hero-copy">
          <h1>
            Les PDF ?<br />
            <span>Un jeu d’enfant.</span>
          </h1>
          <p className="catalog-description">
            Un zeste de magie, une bonne dose de précision.
            <br />
            Vos {tools.length} outils prépresse, à savourer sans se compliquer la vie.
          </p>
          <a className="button candy-hero-button" href="#tools">
            <Play size={18} fill="currentColor" />À vous de jouer !
          </a>
          <div className="hero-reassurance">
            <Check size={16} />
            Des exemples pour essayer, des réglages pour maîtriser.
          </div>
        </div>
        <div className="candy-hero-art" aria-hidden="true">
          <img
            src="/candy/hero-printshop.webp"
            alt=""
            width="1536"
            height="1024"
            fetchPriority="high"
          />
          <span className="candy-spark spark-one">
            <Sparkles />
          </span>
          <span className="candy-spark spark-two">
            <Sparkles />
          </span>
        </div>
      </section>
      <div className="candy-how" aria-label="Comment utiliser les outils">
        <span>
          <b>1</b>Choisissez votre outil
        </span>
        <ArrowRight size={17} />
        <span>
          <b>2</b>Ajoutez votre touche
        </span>
        <ArrowRight size={17} />
        <span>
          <b>3</b>Récupérez votre fichier
        </span>
      </div>
      <div id="tools" className="catalog-section-title">
        <h2>
          À chaque envie, son outil<span> !</span>
        </h2>
        <span>{tools.length} recettes pour vos PDF</span>
      </div>
      <div className="catalog-toolbar">
        <div className="catalog-tabs" role="group" aria-label="Filtrer par usage">
          {categories.map((cat) => (
            <button
              key={cat}
              className={category === cat ? 'selected' : ''}
              aria-pressed={category === cat}
              onClick={() => setCategory(cat)}
            >
              {cat}
            </button>
          ))}
        </div>
        <label className="catalog-search">
          <Search size={16} />
          <input
            type="search"
            placeholder="Trouver un outil…"
            aria-label="Rechercher un outil"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
      </div>
      <div className="catalog-meta">
        <span>
          {filtered.length} outil{filtered.length > 1 ? 's' : ''}
          {category !== 'Tous' ? ` pour ${category.toLowerCase()}` : ' à votre disposition'}
        </span>
        <span>PDF · millimètres · réglages explicites</span>
      </div>
      {filtered.length === 0 ? (
        <div className="catalog-empty">
          <Search size={28} />
          <h2>Aucun outil ne correspond.</h2>
          <p>Essayez « pliage », « couleur », « fusion » ou le nom d’un outil.</p>
          <Button
            variant="outline"
            onClick={() => {
              setQuery('')
              setCategory('Tous')
            }}
          >
            Afficher tous les outils
          </Button>
        </div>
      ) : (
        <div className="tool-grid">
          {filtered.map((tool) => (
            <a
              key={tool.id}
              href={toolUrl(tool.id)}
              className="tool-card"
              data-flavour={flavours[foodIds.indexOf(tool.id)]}
            >
              <div className="tool-card-top">
                <ToolIcon tool={tool} />
                <span className="tool-card-category">{tool.category}</span>
              </div>
              <h2>{tool.name}</h2>
              <p>{tool.description}</p>
              <span className="tool-input-hint">
                {tool.min_files > 0
                  ? tool.min_files === 2
                    ? 'Deux PDF à comparer'
                    : 'À partir de votre fichier'
                  : 'Depuis vos réglages'}
              </span>
              <div className="tool-card-bottom">
                <span>C’est parti !</span>
                <ArrowRight size={18} />
              </div>
            </a>
          ))}
        </div>
      )}
      <div className="catalog-footnote">
        <FileCheck2 size={20} />
        <p>
          <strong>Facile à prendre en main. Précis jusqu’au bout.</strong>
          <span>
            Chaque outil indique ce qu’il produit et ce qui reste à contrôler à l’atelier. Les
            fichiers sont supprimés automatiquement sous 24 heures.
          </span>
        </p>
      </div>
      <footer>
        <span>
          Snackpress est proposé par{' '}
          <a href="https://ikyoh.com" className="footer-credit-link">
            ikyoh
          </a>
        </span>
        <span>Usage local · Épreuve et validation atelier selon le traitement</span>
      </footer>
    </main>
  )
}

function visibleField(tool: string, field: string, values: Values) {
  if (tool === 'pizza') return visiblePizzaField(field, values)
  if (tool === 'club-sandwich') {
    if (['gsm', 'bulk'].includes(field)) return values.mode === 'bulk'
    if (field === 'caliper') return values.mode === 'caliper'
  }
  if (tool === 'bento') {
    if (field === 'pages') return values.operation !== 'merge'
    if (field === 'rotation') return values.operation === 'rotate'
  }
  if (tool === 'taco') return visibleTacoField(field, values)
  if (tool === 'layer-cake' && ['gap', 'flip'].includes(field)) return values.mode === 'repeat'
  return true
}

function Setting({
  field,
  value,
  update,
  disabled,
  displayLabel,
  validationError,
  required = false,
}: {
  field: ToolField
  value: string | number
  update: (value: string | number) => void
  disabled?: boolean
  displayLabel?: string
  validationError?: string
  required?: boolean
}) {
  const id = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  useEffect(() => {
    inputRef.current?.setCustomValidity(validationError ?? '')
  }, [validationError])
  const labelProps = {
    id,
    'aria-labelledby': displayLabel ? undefined : `${id}-label`,
    'aria-label': displayLabel ? field.label : undefined,
    'aria-describedby': `${id}-help${validationError ? ` ${id}-error` : ''}`,
    'aria-invalid': validationError ? true : undefined,
  }
  return (
    <label
      htmlFor={id}
      className={`field tool-field ${field.type === 'textarea' ? 'wide-field' : ''}`}
    >
      <span id={`${id}-label`}>{displayLabel ?? field.label}</span>
      {field.type === 'select' ? (
        <span className="select-wrap">
          <select {...labelProps} value={value} onChange={(e) => update(e.target.value)}>
            {field.options?.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <ChevronDown size={14} />
        </span>
      ) : field.type === 'textarea' ? (
        <textarea {...labelProps} rows={4} value={value} onChange={(e) => update(e.target.value)} />
      ) : field.type === 'number' ? (
        <span className="input-wrap">
          <input
            {...labelProps}
            ref={inputRef}
            required={required}
            type="number"
            min={field.min ?? undefined}
            max={field.max ?? undefined}
            step={Number.isInteger(field.step) ? field.step : 'any'}
            value={value}
            readOnly={disabled}
            onChange={(e) => update(e.target.value === '' ? '' : Number(e.target.value))}
          />
          <span>{field.unit}</span>
        </span>
      ) : (
        <input {...labelProps} type="text" value={value} onChange={(e) => update(e.target.value)} />
      )}
      <small id={`${id}-help`} className={field.help ? 'field-hint' : 'sr-only'}>
        {[field.unit, field.help].filter(Boolean).join(' · ')}
      </small>
      {validationError && (
        <small id={`${id}-error`} className="field-error">
          {validationError}
        </small>
      )}
    </label>
  )
}

function KebabShare({ result }: { result: Result }) {
  const [status, setStatus] = useState('')
  const pdf = result.artifacts?.find((a) => a.media_type === 'application/pdf')
  if (!pdf) return null
  const url = new URL(assetUrl(result.id, pdf.name), window.location.origin).href
  return (
    <section aria-label="Partager le PDF">
      <h2>Partager le PDF</h2>
      <label className="field">
        <span>Lien de partage</span>
        <input type="url" readOnly value={url} onFocus={(e) => e.target.select()} />
      </label>
      <Button
        type="button"
        variant="outline"
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(url)
            setStatus('Lien copié.')
          } catch {
            setStatus('Sélectionnez le lien ci-dessus pour le copier manuellement.')
          }
        }}
      >
        Copier le lien du PDF
      </Button>
      <p className="field-hint">
        Toute personne disposant du lien peut télécharger ce PDF sans compte. Le lien expire 24 h
        après la génération, ou dès la suppression du travail.
      </p>
      <p role="status">{status}</p>
    </section>
  )
}

function ToolWorkspace({ tool, tools }: { tool: Tool; tools: Tool[] }) {
  const [values, setValues] = useState<Values>(() =>
    Object.fromEntries(tool.fields.map((f) => [f.key, f.default])),
  )
  const [pizzaSections, setPizzaSections] = useState(['format'])
  const [pizzaFocus, setPizzaFocus] = useState('')
  const pizzaValidation = tool.id === 'pizza' ? pizzaErrors(tool.fields, values) : {}
  const [mobileView, setMobileView] = useState<'settings' | 'preview'>('settings')
  const [isMobile, setIsMobile] = useState(() => window.matchMedia('(max-width: 760px)').matches)
  const workspaceId = useId()
  useEffect(() => {
    const query = window.matchMedia('(max-width: 760px)')
    const update = () => setIsMobile(query.matches)
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])
  const [burger, setBurger] = useState<BurgerOptions>(burgerDefaults)
  const [kebabProduct, setKebabProduct] = useState<Snapshot | null>(null)
  const [numberings, setNumberings] = useState<Numbering[]>([newNumbering(55)])
  const [fortuneTemplate, setFortuneTemplate] = useState<Values | null>(null)
  const [fortuneLayer, setFortuneLayer] = useState<Values | null>(null)
  const [ticketsPerBook, setTicketsPerBook] = useState<string | number>(25)
  function changeFortuneLayer(next: Values | null) {
    if (next && next.mode !== 'repeat') {
      setError('Choisissez une configuration Layer Cake en poses répétées pour les souches.')
      return
    }
    setFortuneLayer(next)
    setResult(null)
    setError('')
  }
  function changeFortuneTemplate(next: Values | null) {
    if (next) {
      const width = Number(next.width)
      const height = next.shape === 'circle' ? width : Number(next.height)
      const bleed = Number(next.bleed ?? 3)
      if (![width, height].every((size) => Number.isFinite(size) && size >= 40 && size <= 500)) {
        setError('Fortune Cookie accepte un gabarit Pizza de 40 à 500 mm par côté.')
        return
      }
      if (!Number.isFinite(bleed) || bleed < 0 || bleed > 20) {
        setError('Fortune Cookie accepte un fond perdu de 0 à 20 mm sur chaque côté.')
        return
      }
      next = { ...next, width, height, bleed }
      setValues((old) => ({ ...old, width, height, bleed }))
    }
    setFortuneTemplate(next)
    setResult(null)
    setError('')
  }
  function changeNumberings(next: Numbering[]) {
    setNumberings(next)
    setResult(null)
    setError('')
  }
  const [files, setFiles] = useState<File[]>([])
  const [result, setResult] = useState<Result | null>(null)
  const [activeArtifact, setActiveArtifact] = useState('')
  const [page, setPage] = useState(1)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [drag, setDrag] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const formRef = useRef<HTMLFormElement>(null)
  const previewable =
    result?.artifacts?.filter(
      (a) =>
        ['application/pdf', 'image/png'].includes(a.media_type) &&
        (tool.id !== 'fortune-cookie' || a.name === 'serie.pdf'),
    ) || []
  const selected = previewable.find((a) => a.name === activeArtifact) || previewable[0]
  const totalPages = selected?.pages || 1
  const burgerInputs = burgerFiles(burger)
  const burgerRoles = burgerInputs.map((file) => file.label)
  const maxFiles = tool.id === 'burger' ? burgerRoles.length : tool.max_files
  const nextBurgerFile = burgerInputs[Math.min(files.length, maxFiles - 1)]
  const ready =
    tool.id === 'burger'
      ? files.length === maxFiles &&
        (burger.product_snapshot
          ? maxFiles > 0
          : burger.source_mode === 'classic' && burger.expected_files > 0)
      : tool.id === 'kebab'
        ? !!kebabProduct
        : files.length >= tool.min_files && files.length <= tool.max_files
  const settings =
    tool.id === 'fortune-cookie'
      ? {
          ...values,
          numberings,
          pizza_template: fortuneTemplate,
          layer_template: fortuneLayer,
          tickets_per_book: fortuneLayer ? ticketsPerBook : 25,
        }
      : tool.id === 'burger'
        ? { ...values, ...burger }
        : tool.id === 'kebab'
          ? { ...values, product_snapshot: kebabProduct }
          : values
  function changeBurger(next: BurgerOptions) {
    // Keep only the populated prefix whose files retain the same production roles.
    if (
      JSON.stringify(burgerRoles) !== JSON.stringify(burgerLabels(next)) ||
      JSON.stringify(
        burger.product_snapshot?.variant.components.map((c) => ({ id: c.id, slots: c.slots })),
      ) !==
        JSON.stringify(
          next.product_snapshot?.variant.components.map((c) => ({ id: c.id, slots: c.slots })),
        )
    ) {
      const retained: File[] = []
      for (const role of burgerLabels(next)) {
        const file = files[burgerRoles.indexOf(role)]
        if (!file) break
        retained.push(file)
      }
      setFiles(retained)
    }
    setBurger(next)
    setResult(null)
    setError('')
  }
  const livePreview = useLivePreview({
    toolId: tool.id,
    files,
    settings,
    available: ready,
    paused: busy || !!result,
    // Preview validation must not fire invalid events that reveal panels or move focus.
    valid: () =>
      Object.keys(pizzaValidation).length === 0 && (formRef.current?.matches(':valid') ?? false),
  })
  function changePizza(patch: Values) {
    setValues((old) => ({ ...old, ...patch }))
    setResult(null)
    setError('')
  }
  function change(key: string, value: string | number) {
    setValues((old) => {
      const next = { ...old, [key]: value }
      if (
        tool.id === 'sushi' &&
        ((key === 'shape' && value === 'circle') || (key === 'width' && old.shape === 'circle'))
      )
        next.height = next.width
      if (tool.id === 'layer-cake' && key === 'mode' && value === 'booklet') {
        next.sheet_width = 420
        next.sheet_height = 297
      }
      return next
    })
    setResult(null)
    setError('')
  }
  function addFiles(incoming: File[]) {
    const next = maxFiles === 1 ? incoming.slice(0, 1) : [...files, ...incoming]
    if (next.length > maxFiles) {
      setError(`Cet outil accepte au maximum ${maxFiles} fichier(s).`)
      return
    }
    if (
      next.some((f) => f.size > 25 * 1024 * 1024) ||
      next.reduce((n, f) => n + f.size, 0) > 50 * 1024 * 1024
    ) {
      setError('Limite : 25 Mo par fichier et 50 Mo au total.')
      return
    }
    setFiles(next)
    setResult(null)
    setError('')
  }
  async function example() {
    setError('')
    setBusy(true)
    try {
      if (tool.id === 'burger') {
        const data = new FormData()
        data.append('settings', JSON.stringify(settings))
        if (burger.template_tool === 'pdf') {
          const template = files[burgerRoles.length - 1]
          if (!template)
            throw new Error('Importez le gabarit PDF avant de charger un exemple à son format.')
          data.append('files', template)
        }
        const generated = await request<Result>('/api/tools/burger/example', {
          method: 'POST',
          body: data,
        })
        try {
          const demo = await Promise.all(
            generated.artifacts.map(async (artifact) => {
              const response = await fetch(
                `/api/tool-jobs/${generated.id}/files/${encodeURIComponent(artifact.name)}`,
              )
              if (!response.ok) throw new Error('Exemple indisponible. Réessayez.')
              return new File([await response.blob()], artifact.name, { type: artifact.media_type })
            }),
          )
          setFiles(demo)
          setResult(null)
        } finally {
          // The files now live in the browser; release the temporary example job.
          await request(`/api/tool-jobs/${generated.id}`, { method: 'DELETE' }).catch(() => {})
        }
        return
      }
      const name =
        tool.id === 'layer-cake' && values.mode === 'booklet'
          ? 'exemple-livret.pdf'
          : tool.id === 'fortune-cookie'
            ? 'exemple-fond.pdf'
            : 'exemple-carte.pdf'
      const response = await fetch(`/${name}`)
      if (!response.ok) throw new Error('Exemple indisponible.')
      const first = new File([await response.blob()], name, { type: 'application/pdf' })
      const demo = [first]
      if (tool.id === 'tiramisu') {
        const second = await fetch('/exemple-carte-v2.pdf')
        if (!second.ok) throw new Error('Seconde version indisponible.')
        demo.push(
          new File([await second.blob()], 'exemple-carte-v2.pdf', { type: 'application/pdf' }),
        )
      }
      setFiles(demo)
      setResult(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  async function run(e: React.FormEvent) {
    e.preventDefault()
    if (!ready || busy || !formRef.current?.reportValidity()) return
    setError('')
    setBusy(true)
    try {
      const data = new FormData()
      data.append('settings', JSON.stringify(settings))
      files.forEach((f) => data.append('files', f))
      const response = await request<Result>(`/api/tools/${tool.id}/run`, {
        method: 'POST',
        body: data,
      })
      setResult(response)
      setMobileView('preview')
      setActiveArtifact(
        response.artifacts?.find(
          (a) =>
            ['application/pdf', 'image/png'].includes(a.media_type) &&
            (tool.id !== 'fortune-cookie' || a.name === 'serie.pdf'),
        )?.name || '',
      )
      setPage(1)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  async function removeResult() {
    if (!result) return
    setBusy(true)
    try {
      await request(`/api/tool-jobs/${result.id}`, { method: 'DELETE' })
      setResult(null)
      setFiles([])
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  function moveFile(index: number, direction: number) {
    const next = [...files]
    ;[next[index], next[index + direction]] = [next[index + direction], next[index]]
    setFiles(next)
    setResult(null)
  }
  return (
    <main className="studio-main tool-main">
      <div className="tool-breadcrumb">
        <a href="/">
          <ArrowLeft size={15} />
          Tous les outils
        </a>
        <span>/</span>
        <span>{tool.category}</span>
        <label className="tool-jump">
          <span className="sr-only">Changer d’outil</span>
          <select
            aria-label="Changer d’outil"
            value={tool.id}
            onChange={(e) => {
              window.location.href = toolUrl(e.target.value)
            }}
          >
            {tools.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
          <ChevronDown size={14} />
        </label>
      </div>
      <div className="tool-title">
        <ToolIcon tool={tool} size={27} />
        <div>
          <span className="tool-category-label">{tool.category}</span>
          <h1>
            {tool.name}
            <span>.</span>
          </h1>
          <p>{tool.description}</p>
        </div>
      </div>
      <div className="tool-limit">
        <FileCheck2 size={17} />
        <span>{tool.limit}</span>
      </div>
      {error && (
        <div className="alert error" role="alert">
          <span>{error}</span>
          <button onClick={() => setError('')} aria-label="Fermer l’erreur">
            <X size={16} />
          </button>
        </div>
      )}
      {
        <div className="workspace-view-tabs" role="tablist" aria-label="Vue de l’atelier">
          {(['settings', 'preview'] as const).map((view) => (
            <button
              key={view}
              type="button"
              role="tab"
              id={`${workspaceId}-${view}-tab`}
              aria-controls={`${workspaceId}-${view}`}
              aria-selected={mobileView === view}
              tabIndex={mobileView === view ? 0 : -1}
              onClick={() => setMobileView(view)}
              onKeyDown={(event) => {
                if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
                  event.preventDefault()
                  const next =
                    event.key === 'Home'
                      ? 'settings'
                      : event.key === 'End'
                        ? 'preview'
                        : view === 'settings'
                          ? 'preview'
                          : 'settings'
                  setMobileView(next)
                  document.getElementById(`${workspaceId}-${next}-tab`)?.focus()
                }
              }}
            >
              {view === 'settings' ? 'Réglages' : 'Aperçu'}
            </button>
          ))}
        </div>
      }
      <div className="tool-workspace compact-workspace">
        <form
          className="tool-controls"
          onSubmit={run}
          ref={formRef}
          id={`${workspaceId}-settings`}
          role={isMobile ? 'tabpanel' : undefined}
          aria-labelledby={isMobile ? `${workspaceId}-settings-tab` : undefined}
          hidden={isMobile && mobileView !== 'settings'}
          onInvalidCapture={(event) => {
            const input = event.target as HTMLInputElement
            if (tool.id === 'pizza') {
              // Reveal only the first invalid field on submission, without jumping between panels.
              const first = formRef.current?.querySelector(':invalid:not(fieldset)')
              if (first && first !== input) {
                event.preventDefault()
                return
              }
            }
            const section = input.closest<HTMLElement>('[data-pizza-section]')?.dataset.pizzaSection
            let reveal = isMobile && mobileView !== 'settings'
            for (
              let element: HTMLElement | null = input.parentElement;
              element && element !== formRef.current;
              element = element.parentElement
            ) {
              if (element instanceof HTMLDetailsElement && !element.open) {
                element.open = true
                reveal = true
              }
            }
            if (section && !pizzaSections.includes(section)) {
              setPizzaSections((old) => (old.includes(section) ? old : [...old, section]))
              reveal = true
            }
            if (reveal) {
              event.preventDefault()
              setMobileView('settings')
              setError(input.validationMessage)
              requestAnimationFrame(() => {
                input.focus()
                input.scrollIntoView({ block: 'nearest' })
              })
            }
          }}
        >
          <div className="panel-heading">
            <span>Votre préparation</span>
            <SlidersHorizontal size={15} />
          </div>
          <fieldset disabled={busy}>
            <div className="tool-controls-layout">
              <div className="tool-controls-scroll">
                {tool.id === 'burger' && (
                  <BurgerEditor
                    options={burger}
                    tools={tools}
                    onChange={changeBurger}
                    renderField={(field, value, update) => (
                      <Setting field={field} value={value} update={update} />
                    )}
                  />
                )}
                {tool.id === 'kebab' && (
                  <ProductSelector
                    sourceMode="catalog"
                    catalogOnly
                    snapshot={kebabProduct}
                    tools={tools}
                    onChange={(snapshot) => {
                      setKebabProduct(snapshot)
                      setResult(null)
                      setError('')
                    }}
                  />
                )}
                {tool.max_files > 0 && (
                  <section className="tool-upload-section">
                    <h2>
                      <span className="section-number">01</span>
                      {tool.min_files === 2
                        ? 'Les deux versions'
                        : tool.min_files === 0
                          ? 'Fond PDF facultatif'
                          : 'Vos fichiers'}
                    </h2>
                    <input
                      type="file"
                      ref={fileRef}
                      accept={tool.accept}
                      multiple={maxFiles > 1}
                      className="sr-only"
                      aria-label="Choisir les fichiers"
                      onChange={(e) => {
                        addFiles(Array.from(e.target.files || []))
                        e.target.value = ''
                      }}
                    />
                    {files.map((file, i) => (
                      <div className="tool-file" key={`${i}-${file.name}`}>
                        <FileText size={19} />
                        <div>
                          <small>
                            {tool.id === 'tiramisu'
                              ? i === 0
                                ? 'Version A'
                                : 'Version B'
                              : tool.id === 'burger'
                                ? burgerRoles[i]
                                : `Fichier ${i + 1}`}
                          </small>
                          <strong title={file.name}>{file.name}</strong>
                          <small>{(file.size / 1024 / 1024).toFixed(2)} Mo</small>
                        </div>
                        <div className="file-actions">
                          {['bento', 'burger'].includes(tool.id) && (
                            <>
                              <button
                                type="button"
                                aria-label={`Monter le fichier ${i + 1}`}
                                disabled={i === 0}
                                onClick={() => moveFile(i, -1)}
                              >
                                <ChevronUp size={13} />
                              </button>
                              <button
                                type="button"
                                aria-label={`Descendre le fichier ${i + 1}`}
                                disabled={i === files.length - 1}
                                onClick={() => moveFile(i, 1)}
                              >
                                <ChevronDown size={13} />
                              </button>
                            </>
                          )}
                          <button
                            type="button"
                            aria-label={`Retirer le fichier ${i + 1}`}
                            onClick={() => {
                              setFiles(
                                tool.id === 'burger'
                                  ? files.slice(0, i)
                                  : files.filter((_, n) => n !== i),
                              )
                              setResult(null)
                            }}
                          >
                            <X size={15} />
                          </button>
                        </div>
                      </div>
                    ))}
                    {(files.length < maxFiles || maxFiles === 1) && (
                      <button
                        type="button"
                        className={`tool-uploader ${drag ? 'dragging' : ''}`}
                        onClick={() => fileRef.current?.click()}
                        onDragOver={(e) => {
                          e.preventDefault()
                          setDrag(true)
                        }}
                        onDragLeave={() => setDrag(false)}
                        onDrop={(e) => {
                          e.preventDefault()
                          setDrag(false)
                          addFiles(Array.from(e.dataTransfer.files))
                        }}
                      >
                        <Upload size={20} />
                        <strong>
                          {tool.id === 'burger' && nextBurgerFile
                            ? `${files.length && maxFiles === 1 ? 'Remplacer' : 'Déposer'} : ${nextBurgerFile.label}`
                            : files.length
                              ? maxFiles === 1
                                ? 'Remplacer le fichier'
                                : 'Ajouter un fichier'
                              : 'Déposer votre fichier ici'}
                        </strong>
                        {tool.id === 'burger' && nextBurgerFile?.hint && (
                          <span>{nextBurgerFile.hint}</span>
                        )}
                        <span>
                          {tool.accept === '.pdf' ? 'PDF' : 'PDF, PNG ou JPEG'} · 25 Mo par fichier
                        </span>
                      </button>
                    )}
                    <p className="privacy-note">
                      L’import autorise le traitement sur le serveur pour l’aperçu et le fichier
                      final. Conservation maximale : 24 h.
                    </p>
                    {(tool.id !== 'burger' || burger.source_mode === 'classic') && (
                      <button
                        type="button"
                        className="example-button"
                        disabled={busy}
                        onClick={() => void example()}
                      >
                        Charger un exemple <ArrowRight size={13} />
                      </button>
                    )}
                  </section>
                )}
                <Configurations
                  compact
                  toolId={tool.id}
                  settings={settings}
                  onLoad={(saved) => {
                    const { numberings: savedNumberings, ...fields } = saved
                    if (tool.id === 'burger') {
                      const options = Object.fromEntries(
                        Object.entries(burgerDefaults).map(([key, fallback]) => [
                          key,
                          fields[key] ?? fallback,
                        ]),
                      ) as BurgerOptions
                      changeBurger(options)
                      setValues(
                        Object.fromEntries(
                          tool.fields.map((f) => [f.key, fields[f.key] ?? f.default]),
                        ) as Values,
                      )
                    } else if (tool.id === 'kebab') {
                      setKebabProduct((fields.product_snapshot as Snapshot | null) ?? null)
                      setValues(
                        Object.fromEntries(
                          tool.fields.map((f) => [f.key, fields[f.key] ?? f.default]),
                        ) as Values,
                      )
                    } else if (tool.id === 'fortune-cookie') {
                      const savedTemplate = (fields.pizza_template as Values | null) ?? null
                      const template: Values | null = savedTemplate
                        ? {
                            ...savedTemplate,
                            height:
                              savedTemplate.shape === 'circle'
                                ? savedTemplate.width
                                : savedTemplate.height,
                            bleed: savedTemplate.bleed ?? 3,
                          }
                        : null
                      setFortuneTemplate(template)
                      setFortuneLayer((fields.layer_template as Values | null) ?? null)
                      setTicketsPerBook((fields.tickets_per_book as number) ?? 25)
                      setValues(
                        Object.fromEntries(
                          tool.fields.map((f) => [
                            f.key,
                            (template && ['width', 'height', 'bleed'].includes(f.key)
                              ? (template[f.key] ?? f.default)
                              : fields[f.key]) ?? f.default,
                          ]),
                        ) as Values,
                      )
                    } else setValues(fields as Values)
                    if (tool.id === 'fortune-cookie')
                      setNumberings(
                        (savedNumberings as Numbering[] | null) || [
                          newNumbering(Number(fields.height)),
                        ],
                      )
                    setResult(null)
                    setError('')
                  }}
                />
                {tool.id === 'pizza' && (
                  <PizzaSettings
                    fields={tool.fields}
                    values={values}
                    sections={pizzaSections}
                    onSectionsChange={setPizzaSections}
                    onChange={changePizza}
                    onFocusField={setPizzaFocus}
                    errors={pizzaValidation}
                    renderField={(field, options) => (
                      <Setting
                        field={field}
                        displayLabel={options.displayLabel}
                        value={options.value ?? pizzaValue(field, values)}
                        update={options.update ?? ((value) => change(field.key, value))}
                        validationError={options.error}
                        required
                      />
                    )}
                  />
                )}
                {tool.id === 'fortune-cookie' && (
                  <FortuneTemplate
                    template={fortuneTemplate}
                    defaults={{
                      ...Object.fromEntries(
                        tools
                          .find((t) => t.id === 'pizza')
                          ?.fields.map((f) => [f.key, f.default]) ?? [],
                      ),
                      width: values.width,
                      height: values.height,
                      bleed: values.bleed,
                    }}
                    onChange={changeFortuneTemplate}
                  >
                    <div className="tool-fields grouped-tool-fields">
                      {tool.fields
                        .filter((field) => ['width', 'height', 'bleed'].includes(field.key))
                        .map((field) => (
                          <Setting
                            key={field.key}
                            field={field}
                            value={values[field.key] ?? field.default}
                            update={(value) => change(field.key, value)}
                          />
                        ))}
                    </div>
                  </FortuneTemplate>
                )}
                {tool.id !== 'pizza' && tool.fields.length > 0 && (
                  <ToolSettings
                    toolId={tool.id}
                    fields={tool.fields.filter(
                      (field) =>
                        visibleField(tool.id, field.key, values) &&
                        !(
                          tool.id === 'fortune-cookie' &&
                          ['width', 'height', 'bleed'].includes(field.key)
                        ) &&
                        !(
                          tool.id === 'burger' &&
                          burger.source_mode !== 'classic' &&
                          field.key === 'paper'
                        ),
                    )}
                    values={values}
                    renderField={(field) => (
                      <Setting
                        field={field}
                        value={values[field.key] ?? field.default}
                        update={(value) => change(field.key, value)}
                        disabled={
                          tool.id === 'sushi' && values.shape === 'circle' && field.key === 'height'
                        }
                      />
                    )}
                  />
                )}
                {tool.id === 'fortune-cookie' && (
                  <SettingsSection
                    title="Positions des numéros"
                    summary={`${numberings.length} position(s)`}
                  >
                    <FortuneSettings
                      items={numberings}
                      width={Number(values.width)}
                      height={Number(values.height)}
                      onChange={changeNumberings}
                    />
                  </SettingsSection>
                )}
                {tool.id === 'fortune-cookie' && (
                  <FortuneImposition
                    template={fortuneLayer}
                    defaults={Object.fromEntries(
                      tools
                        .find((t) => t.id === 'layer-cake')
                        ?.fields.map((f) => [f.key, f.default]) ?? [],
                    )}
                    perBook={ticketsPerBook}
                    onChange={changeFortuneLayer}
                    onPerBookChange={(value) => {
                      setTicketsPerBook(value)
                      setResult(null)
                      setError('')
                    }}
                  />
                )}
                {tool.id === 'layer-cake' && (
                  <a className="advanced-workshop" href={toolUrl('imposition')}>
                    <LayoutGrid size={17} />
                    <span>
                      Atelier de répétition détaillé
                      <small>Aperçu interactif, grille, repères et modèles</small>
                    </span>
                    <ArrowRight size={15} />
                  </a>
                )}
              </div>
              <div className="tool-run">
                {tool.id === 'club-sandwich' && (
                  <ClubEstimate fields={tool.fields} values={values} />
                )}
                <Button type="submit" disabled={busy || !ready}>
                  {busy ? <LoaderCircle size={16} className="spin" /> : <ArrowRight size={16} />}
                  {busy ? 'Traitement en cours…' : 'Générer le fichier final'}
                </Button>
                <p>
                  {tool.id === 'kebab' && !ready
                    ? 'Choisissez un produit d’impression pour préparer la fiche.'
                    : tool.min_files > 0 && !ready
                      ? tool.id === 'burger'
                        ? `${files.length} / ${maxFiles} fichier(s) importé(s). Complétez les emplacements attendus.`
                        : `Importez ${tool.min_files === 2 ? 'les deux fichiers' : 'votre fichier'} pour commencer.`
                      : tool.id === 'club-sandwich'
                        ? 'Le PDF reprend cette estimation.'
                        : 'L’aperçu est automatique. Générez ensuite le fichier complet.'}
                </p>
              </div>
            </div>
          </fieldset>
        </form>
        <section
          className="tool-result"
          aria-label="Résultat du traitement"
          aria-busy={busy}
          id={`${workspaceId}-preview`}
          role={isMobile ? 'tabpanel' : undefined}
          aria-labelledby={isMobile ? `${workspaceId}-preview-tab` : undefined}
          hidden={isMobile && mobileView !== 'preview'}
        >
          <div className="tool-result-header">
            <span>{result ? 'Votre résultat' : 'L’aperçu'}</span>
            {result && (
              <button className="text-button" disabled={busy} onClick={() => void removeResult()}>
                <Trash2 size={14} />
                Supprimer ce travail
              </button>
            )}
          </div>
          {!result ? (
            <>
              {tool.id === 'fortune-cookie' && (
                <details className="live-placement" open>
                  <summary>Placement des numérotations</summary>
                  <FortunePreview
                    items={numberings}
                    width={Number(values.width) || 85}
                    height={Number(values.height) || 55}
                    bleed={Number(values.bleed) || 0}
                    serial={
                      String(values.prefix) +
                      String(values.start).padStart(Number(values.digits), '0')
                    }
                    file={files[0]}
                    disabled={busy}
                    onChange={changeNumberings}
                  />
                </details>
              )}
              <LivePreview
                state={livePreview}
                scrollable={false}
                pdfOverlay={
                  tool.id === 'pizza' && pizzaFocus ? (
                    <PizzaHighlight values={values} field={pizzaFocus} />
                  ) : undefined
                }
                overlayLabel={pizzaFocusLabel(pizzaFocus, values)}
                overlayArtifact="gabarit.pdf"
                faceArtifact={tool.id === 'taco' ? 'plan-pliage.pdf' : undefined}
              />
            </>
          ) : (
            <>
              <div className="tool-success" role="status">
                <Check size={18} />
                <span>{result.summary}</span>
              </div>
              {result.metrics && Object.keys(result.metrics).length > 0 && (
                <div className="tool-metrics">
                  {Object.entries(result.metrics).map(([key, value]) => (
                    <div key={key}>
                      <span>{key}</span>
                      <strong>
                        {typeof value === 'number'
                          ? value.toLocaleString('fr-FR', { maximumFractionDigits: 3 })
                          : value}
                      </strong>
                    </div>
                  ))}
                </div>
              )}
              {previewable.length > 0 && (
                <>
                  {(previewable.length > 1 || totalPages > 1) && (
                    <div className="artifact-toolbar">
                      {previewable.length > 1 && (
                        <label>
                          <span className="sr-only">Document à prévisualiser</span>
                          <select
                            aria-label="Document à prévisualiser"
                            value={activeArtifact}
                            onChange={(e) => {
                              setActiveArtifact(e.target.value)
                              setPage(1)
                            }}
                          >
                            {previewable.map((a) => (
                              <option key={a.name} value={a.name}>
                                {a.label}
                              </option>
                            ))}
                          </select>
                        </label>
                      )}
                      {tool.id === 'taco' &&
                      selected?.name === 'plan-pliage.pdf' &&
                      totalPages === 2 ? (
                        <PdfFaceSwitch page={page} onChange={setPage} />
                      ) : (
                        totalPages > 1 && (
                          <div className="page-navigation">
                            <button
                              aria-label="Page précédente"
                              onClick={() => setPage((n) => n - 1)}
                              disabled={page <= 1}
                            >
                              <ChevronLeft size={16} />
                            </button>
                            <span>
                              {page} / {totalPages}
                            </span>
                            <button
                              aria-label="Page suivante"
                              onClick={() => setPage((n) => n + 1)}
                              disabled={page >= totalPages}
                            >
                              <ChevronRight size={16} />
                            </button>
                          </div>
                        )
                      )}
                    </div>
                  )}
                  <div className="artifact-stage">
                    {selected?.media_type === 'application/pdf' ? (
                      <PdfPreview
                        url={assetUrl(result.id, selected.name)}
                        page={page}
                        scrollable={false}
                      />
                    ) : selected?.media_type === 'image/png' ? (
                      <img src={assetUrl(result.id, selected.name)} alt={selected.label} />
                    ) : null}
                  </div>
                </>
              )}
              <div className="artifact-downloads">
                {tool.id === 'kebab' && <KebabShare result={result} />}
                <h2>
                  <ArrowDownToLine size={16} />
                  Vos fichiers
                </h2>
                {result.artifacts?.map((a) => (
                  <a key={a.name} href={assetUrl(result.id, a.name)} download>
                    <span>
                      <FileText size={16} />
                      <strong>{a.label}</strong>
                    </span>
                    <small>
                      {a.media_type === 'application/pdf'
                        ? `${a.pages} page${a.pages && a.pages > 1 ? 's' : ''} · PDF`
                        : a.media_type === 'image/png'
                          ? 'PNG'
                          : 'JSON'}
                    </small>
                    <ArrowDownToLine size={15} />
                  </a>
                ))}
              </div>
              <div className="result-warnings">
                <h2>
                  <FileCheck2 size={16} />À contrôler avant utilisation
                </h2>
                <ul>
                  {result.warnings?.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              </div>
            </>
          )}
        </section>
      </div>
      <footer>
        <span>
          Snackpress est proposé par{' '}
          <a href="https://ikyoh.com" className="footer-credit-link">
            ikyoh
          </a>
        </span>
        <span>Fichiers privés · Conservation maximale de 24 h</span>
      </footer>
    </main>
  )
}

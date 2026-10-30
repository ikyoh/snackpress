import { useRef, useState, type FormEvent } from 'react'
import {
  ArrowDownToLine,
  ArrowLeft,
  FileCheck2,
  LoaderCircle,
  RotateCcw,
  Upload,
  X,
} from 'lucide-react'
import { request } from './api'
import { Button } from './components/ui/button'
import { LivePreview, useLivePreview } from './LivePreview'
import { PdfPreview } from './PdfPreview'
import { Configurations } from './Configurations'
import type { components } from '../../../packages/api-client/schema'
import './biscuit.css'

type Result = components['schemas']['ToolResult']
type Values = Record<string, string | number>
const defaults: Values = {
  source: 'shape',
  shape: 'rectangle',
  width: 85,
  height: 55,
  radius: 5,
  offset: 3,
  smoothing: 0.15,
  join: 'round',
  holes: 'fill',
  selection: 'all',
  threshold: 20,
  min_area: 0.2,
}
const format = (value: string | number) =>
  typeof value === 'number' ? value.toLocaleString('fr-FR', { maximumFractionDigits: 3 }) : value

export function BiscuitWorkspace() {
  const [values, setValues] = useState<Values>(defaults)
  const [files, setFiles] = useState<File[]>([])
  const [result, setResult] = useState<Result | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [mobileView, setMobileView] = useState('settings')
  const form = useRef<HTMLFormElement>(null)
  const input = useRef<HTMLInputElement>(null)
  const ready = values.source === 'shape' || files.length === 1
  const preview = useLivePreview({
    toolId: 'biscuit',
    files,
    settings: values,
    available: ready,
    paused: busy || !!result,
    valid: () => !!form.current?.checkValidity(),
  })
  function update(patch: Values) {
    setValues((old) => ({ ...old, ...patch }))
    setResult(null)
    setError('')
  }
  function changeSource(source: string) {
    update({ source })
    setFiles([])
  }
  function importFile(file?: File) {
    if (!file || busy) return
    if (file.size > 25 * 1024 * 1024) {
      setError('Le fichier dépasse 25 Mo. Réduisez sa taille puis réessayez.')
      return
    }
    const svg = /\.svg$/i.test(file.name)
    if (!/\.(png|jpe?g|svg)$/i.test(file.name)) {
      setError('Importez une image PNG, JPEG ou un tracé SVG.')
      return
    }
    update({ source: svg ? 'svg' : 'image' })
    setFiles([file])
  }
  async function generate(event: FormEvent) {
    event.preventDefault()
    if (!ready || busy) return
    setBusy(true)
    setError('')
    try {
      const data = new FormData()
      data.append('settings', JSON.stringify(values))
      files.forEach((file) => data.append('files', file))
      setResult(await request<Result>('/api/tools/biscuit/run', { method: 'POST', body: data }))
      setMobileView('preview')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  function number(key: string, label: string, min: number, max: number, step = 0.1, unit = 'mm') {
    return (
      <label className="field">
        <span>{label}</span>
        <span className="input-wrap">
          <input
            type="number"
            aria-label={label}
            required
            value={values[key]}
            min={min}
            max={max}
            step={step}
            onChange={(e) => update({ [key]: e.target.value === '' ? '' : Number(e.target.value) })}
          />
          <span>{unit}</span>
        </span>
      </label>
    )
  }
  function select(key: string, label: string, options: [string, string][]) {
    return (
      <label className="field">
        <span>{label}</span>
        <select value={values[key]} onChange={(e) => update({ [key]: e.target.value })}>
          {options.map(([value, text]) => (
            <option key={value} value={value}>
              {text}
            </option>
          ))}
        </select>
      </label>
    )
  }
  const artifactUrl = (name: string) =>
    `/api/tool-jobs/${result!.id}/files/${encodeURIComponent(name)}`
  return (
    <main className="studio-main biscuit-workspace">
      <a href="/" className="back-link">
        <ArrowLeft size={16} /> Tous les outils
      </a>
      <div className="tool-title">
        <span className="tool-icon candy-art" aria-hidden="true">
          <img
            className="food-illustration"
            src="/candy/biscuit.webp"
            width="110"
            height="110"
            alt=""
          />
        </span>
        <div>
          <h1>
            Biscuit<span>.</span>
          </h1>
          <p>Votre image, la bonne forme, le bon contour.</p>
        </div>
      </div>
      <div className="tool-limit">
        <FileCheck2 size={18} />
        <span>
          Créez une forme ou récupérez un contour, puis ajustez sa découpe en millimètres.
        </span>
      </div>
      {error && (
        <div className="alert error" role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => setError('')} aria-label="Fermer l’erreur">
            <X size={18} />
          </button>
        </div>
      )}
      <div className="workspace-view-tabs biscuit-tabs" role="tablist" aria-label="Vue de Biscuit">
        {(['settings', 'preview'] as const).map((view) => (
          <button
            type="button"
            role="tab"
            key={view}
            id={`biscuit-${view}-tab`}
            aria-selected={mobileView === view}
            aria-controls={`biscuit-${view}`}
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
                document.getElementById(`biscuit-${next}-tab`)?.focus()
              }
            }}
          >
            {view === 'settings' ? 'Réglages' : 'Aperçu'}
          </button>
        ))}
      </div>
      <div className="biscuit-layout" data-view={mobileView}>
        <form
          id="biscuit-settings"
          ref={form}
          className="settings-panel biscuit-settings"
          onSubmit={(e) => void generate(e)}
          onInvalidCapture={() => setMobileView('settings')}
        >
          <div className="panel-heading">Votre forme de découpe</div>
          <fieldset disabled={busy}>
            <section className="setting-section">
              <h2>Le point de départ</h2>
              <div className="biscuit-source" role="group" aria-label="Source du tracé">
                {(
                  [
                    ['shape', 'Forme'],
                    ['image', 'Image'],
                    ['svg', 'Tracé SVG'],
                  ] as const
                ).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={values.source === value}
                    onClick={() => changeSource(value)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {values.source !== 'shape' && (
                <>
                  <input
                    ref={input}
                    type="file"
                    className="sr-only"
                    accept=".png,.jpg,.jpeg,.svg"
                    aria-label="Importer une image ou un SVG"
                    onChange={(e) => {
                      importFile(e.target.files?.[0])
                      e.target.value = ''
                    }}
                  />
                  <button
                    type="button"
                    className={`dropzone ${dragging ? 'dragging' : ''}`}
                    onClick={() => input.current?.click()}
                    onDragOver={(e) => {
                      e.preventDefault()
                      setDragging(true)
                    }}
                    onDragLeave={() => setDragging(false)}
                    onDrop={(e) => {
                      e.preventDefault()
                      setDragging(false)
                      importFile(e.dataTransfer.files[0])
                    }}
                  >
                    <Upload size={24} />
                    <strong>{files[0]?.name || 'Déposez votre fichier ici'}</strong>
                    <span>
                      {files.length ? 'Choisir un autre fichier' : 'ou parcourir les fichiers'}
                    </span>
                    <small>PNG, JPEG, SVG · 25 Mo maximum</small>
                  </button>
                  <p className="field-hint">
                    {values.source === 'image'
                      ? 'Fond blanc ou transparent : le contour suit les pixels visibles. Pour une photo sur fond complexe, détourez le sujet avant l’import.'
                      : 'Chemins fermés, rectangles, cercles, ellipses et polygones. Convertissez les textes et appliquez les masques avant l’import.'}
                  </p>
                  <p className="field-hint">
                    Traitement sur le serveur Snackpress. Fichiers supprimés sous 24 h.
                  </p>
                </>
              )}
              {values.source === 'shape' &&
                select('shape', 'Forme de départ', [
                  ['rectangle', 'Rectangle / coins arrondis'],
                  ['circle', 'Cercle'],
                  ['ellipse', 'Ellipse'],
                ])}
              <div className="field-row">
                {number(
                  'width',
                  values.source === 'shape' && values.shape === 'circle'
                    ? 'Diamètre source'
                    : 'Largeur source',
                  1,
                  2000,
                )}
                {values.source === 'shape' &&
                  values.shape !== 'circle' &&
                  number('height', 'Hauteur source', 1, 2000)}
              </div>
              {values.source !== 'shape' && (
                <p className="field-hint">
                  {values.source === 'svg'
                    ? 'La forme SVG est recalibrée à cette largeur, hauteur proportionnelle.'
                    : 'Largeur de l’image complète, hauteur proportionnelle.'}
                </p>
              )}
              {values.source === 'shape' &&
                values.shape === 'rectangle' &&
                number(
                  'radius',
                  'Rayon des coins',
                  0,
                  Math.min(Number(values.width), Number(values.height)) / 2,
                )}
            </section>
            <section className="setting-section">
              <h2>Le décalage du tracé</h2>
              <p className="field-hint">Positif : vers l’extérieur. Négatif : vers l’intérieur.</p>
              {number('offset', 'Décalage', -100, 100, 0.1)}
              <input
                className="biscuit-slider"
                type="range"
                min="-20"
                max="20"
                step="0.1"
                aria-label="Ajuster le décalage"
                value={Math.max(-20, Math.min(20, Number(values.offset)))}
                onChange={(e) => update({ offset: Number(e.target.value) })}
              />
              <div className="biscuit-offset-presets">
                {[-3, 0, 3, 5].map((n) => (
                  <button
                    type="button"
                    key={n}
                    aria-pressed={values.offset === n}
                    onClick={() => update({ offset: n })}
                  >
                    {n > 0 ? '+' : ''}
                    {n} mm
                  </button>
                ))}
              </div>
              {select('join', 'Traitement des angles', [
                ['round', 'Arrondis'],
                ['mitre', 'Droits'],
                ['bevel', 'Biseautés'],
              ])}
            </section>
            <details className="setting-section biscuit-details">
              <summary>Affiner le contour</summary>
              {number('smoothing', 'Simplification du tracé', 0, 5, 0.05)}
              <p className="field-hint">
                Tolérance géométrique en mm. Une petite valeur conserve davantage de détails.
              </p>
              {select('holes', 'Ouvertures intérieures', [
                ['fill', 'Combler les trous'],
                ['keep', 'Conserver les trous'],
              ])}
              {select('selection', 'Formes à récupérer', [
                ['all', 'Toutes les formes'],
                ['largest', 'La plus grande uniquement'],
              ])}
              {number('min_area', 'Surface minimale', 0, 100, 0.1, 'mm²')}
              {values.source === 'image' && (
                <>
                  {number('threshold', 'Seuil de détection', 0, 254, 1, '/ 255')}
                  <p className="field-hint">
                    Augmentez pour ignorer les pixels peu opaques ou proches du blanc.
                  </p>
                </>
              )}
            </details>
            <section className="setting-section">
              <Configurations
                toolId="biscuit"
                settings={values}
                onLoad={(saved) => {
                  if (saved.source !== values.source) setFiles([])
                  update(saved as Values)
                }}
              />
            </section>
            <div className="biscuit-generate">
              <Button type="submit" disabled={!ready || busy}>
                {busy ? <LoaderCircle size={18} className="spin" /> : <ArrowDownToLine size={18} />}
                {busy ? 'Création du tracé…' : 'Générer les fichiers de découpe'}
              </Button>
            </div>
          </fieldset>
        </form>
        <section id="biscuit-preview" className="biscuit-preview" aria-label="Aperçu du tracé">
          <div className="biscuit-legend">
            <span>
              <i className="source" />
              Contour source
            </span>
            <span>
              <i className="cut" />
              Tracé de découpe
            </span>
          </div>
          {result ? (
            <>
              <div className="panel-heading">
                <span>Vos fichiers sont prêts</span>
                <button type="button" className="text-button" onClick={() => setResult(null)}>
                  <RotateCcw size={15} /> Revenir à l’aperçu
                </button>
              </div>
              <PdfPreview url={artifactUrl('apercu.pdf')} page={1} />
              <div className="biscuit-results">
                <dl>
                  {Object.entries(result.metrics).map(([label, value]) => (
                    <div key={label}>
                      <dt>{label}</dt>
                      <dd>{format(value)}</dd>
                    </div>
                  ))}
                </dl>
                <div className="biscuit-downloads">
                  {result.artifacts.map((item) => (
                    <a
                      className="artifact-link"
                      key={item.name}
                      href={artifactUrl(item.name)}
                      download
                    >
                      <ArrowDownToLine size={18} />
                      {item.label}
                    </a>
                  ))}
                </div>
                <ul>
                  {result.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </div>
            </>
          ) : ready ? (
            <>
              <LivePreview state={preview} />
              {preview.preview && (
                <div className="biscuit-results">
                  <dl>
                    {Object.entries(preview.preview.metrics).map(([label, value]) => (
                      <div key={label}>
                        <dt>{label}</dt>
                        <dd>{format(value)}</dd>
                      </div>
                    ))}
                  </dl>
                  <ul>
                    {preview.preview.warnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          ) : (
            <div className="biscuit-empty">
              <img
                src="/candy/biscuit.webp"
                width="220"
                height="220"
                alt="Biscuit fleuri et emporte-pièce"
              />
              <h2>Chaque découpe commence par une forme.</h2>
              <p>Importez votre fichier pour voir apparaître son contour.</p>
            </div>
          )}
          <p className="biscuit-export-note">
            SVG en millimètres · PDF vectoriel en ton direct CutContour · Tracés fermés
          </p>
        </section>
      </div>
    </main>
  )
}

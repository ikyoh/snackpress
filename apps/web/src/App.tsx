import { useEffect, useRef, useState } from 'react'
import {
  ArrowDownToLine,
  ArrowRight,
  Check,
  ChevronDown,
  FileText,
  FlipHorizontal2,
  HelpCircle,
  LayoutGrid,
  LoaderCircle,
  Plus,
  RotateCw,
  ScanLine,
  Trash2,
  Upload,
  X,
} from 'lucide-react'
import { Button } from './components/ui/button'
import { defaults, post, request } from './api'
import type { Job, Plan, Settings } from './api'
import { PdfPreview, useArtwork } from './PdfPreview'
import { HeaderActions } from './HeaderActions'
import { Configurations } from './Configurations'
import { LivePreview, useLivePreview } from './LivePreview'

const previewFiles: File[] = []
const format = (n: number) => n.toLocaleString('fr-FR', { maximumFractionDigits: 2 })
const sheets: Record<string, [number, number]> = {
  A4: [210, 297],
  A3: [297, 420],
  SRA3: [320, 450],
}

function Field({
  label,
  value,
  onChange,
  min = 0,
  max = 1200,
  unit = 'mm',
  step = 0.5,
  readOnly = false,
}: {
  label: string
  value: number
  onChange: (n: number) => void
  min?: number
  max?: number
  unit?: string
  step?: number
  readOnly?: boolean
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <span className="input-wrap">
        <input
          type="number"
          readOnly={readOnly}
          min={min}
          max={max}
          step={step}
          value={readOnly ? Number(value.toFixed(2)) : value}
          onChange={(e) => onChange(Number(e.target.value))}
        />
        <span>{unit}</span>
      </span>
    </label>
  )
}

export default function App() {
  const [settings, setSettings] = useState<Settings>(defaults)
  const [job, setJob] = useState<Job | null>(null)
  const [plan, setPlan] = useState<Plan | null>(null)
  const [error, setError] = useState('')
  const [planError, setPlanError] = useState('')
  const [loading, setLoading] = useState(false)
  const [planning, setPlanning] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [exported, setExported] = useState<Plan | null>(null)
  const [face, setFace] = useState<'front' | 'back'>('front')
  const [view, setView] = useState<'plan' | 'pdf'>('pdf')
  const [notice, setNotice] = useState('')
  const [help, setHelp] = useState(false)
  const [dragging, setDragging] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const helpRef = useRef<HTMLDialogElement>(null)
  const { images, error: artworkError } = useArtwork(job)
  const duplex = job?.document.pages.length === 2
  const pending = loading || exporting
  const livePreview = useLivePreview({
    toolId: 'imposition',
    files: previewFiles,
    settings,
    available: !!job,
    sourceJobId: job?.id || '',
    paused: pending || !!exported,
  })
  const update = (patch: Partial<Settings>) => {
    setSettings((s) => ({ ...s, ...patch }))
    setExported(null)
  }

  useEffect(() => {
    if (!job) return
    const controller = new AbortController()
    setPlanning(true)
    setPlan(null)
    setPlanError('')
    const timer = setTimeout(() => {
      void request<Plan>(`/api/jobs/${job.id}/plan`, post(settings, controller.signal))
        .then(setPlan)
        .catch((e) => {
          if (!controller.signal.aborted) setPlanError(e.message)
        })
        .finally(() => {
          if (!controller.signal.aborted) setPlanning(false)
        })
    }, 200)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [job, settings])
  useEffect(() => {
    if (help) helpRef.current?.showModal()
    else helpRef.current?.close()
  }, [help])

  async function upload(file: File) {
    if (pending) return
    setError('')
    setNotice('')
    if (file.size > 25 * 1024 * 1024) {
      setError('Le PDF dépasse 25 Mo. Réduisez sa taille puis réessayez.')
      return
    }
    setLoading(true)
    try {
      const data = new FormData()
      data.append('file', file)
      const result = await request<Job>('/api/jobs', { method: 'POST', body: data })
      const p = result.document.pages[0]
      setJob(result)
      setFace('front')
      setView('pdf')
      setExported(null)
      setSettings((s) => ({
        ...s,
        trim_width: p.width,
        trim_height: p.height,
        bleed: 0,
        confirm_trim: p.has_trim,
      }))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Import impossible. Réessayez.')
    } finally {
      setLoading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }
  async function example() {
    setError('')
    try {
      const response = await fetch('/exemple-carte.pdf')
      if (!response.ok) throw new Error('Exemple indisponible.')
      await upload(
        new File([await response.blob()], 'Exemple — Studio Papier.pdf', {
          type: 'application/pdf',
        }),
      )
    } catch (e) {
      setError((e as Error).message)
    }
  }
  async function generate() {
    if (!job || !plan || planning || pending) return
    setExporting(true)
    setError('')
    setNotice('')
    try {
      const result = await request<Plan>(`/api/jobs/${job.id}/export`, post(settings))
      setExported(result)
      setView('pdf')
      setNotice('Le PDF est prêt. Contrôlez les deux faces avant de le télécharger.')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setExporting(false)
    }
  }
  async function remove() {
    if (!job || pending) return
    try {
      await request(`/api/jobs/${job.id}`, { method: 'DELETE' })
      setJob(null)
      setPlan(null)
      setExported(null)
      setView('pdf')
      setNotice('Le fichier et ses exports ont été supprimés.')
      setError('')
    } catch (e) {
      setError((e as Error).message)
    }
  }
  const selectedSheet =
    Object.keys(sheets).find(
      (k) => sheets[k][0] === settings.sheet_width && sheets[k][1] === settings.sheet_height,
    ) || 'custom'
  const displayPlan = plan && !planning ? plan : null
  const warnings = [...(job?.document.warnings || []), ...(displayPlan?.warnings || [])]
  return (
    <>
      <header className="topbar">
        <a href="/" className="brand" aria-label="Snackpress, accueil">
          <span className="brand-symbol">
            <img src="/snackpress.svg" width="32" height="32" alt="" />
          </span>
          snackpress<span className="brand-dot">.</span>
        </a>
        <HeaderActions />
        <button className="help-button" aria-label="Mode d’emploi" onClick={() => setHelp(true)}>
          <HelpCircle size={17} />
          <span>Mode d’emploi</span>
        </button>
      </header>
      <main>
        <div className="page-heading">
          <div>
            <h1>
              Vos PDF, prêts pour la presse<span>.</span>
            </h1>
            <p className="subtitle">Une feuille. Toutes vos poses. Au millimètre près.</p>
          </div>
          <div className="workspace-tag">
            <span className="status-dot" />
            Imposition répétitive
          </div>
        </div>
        {(error || planError || artworkError) && (
          <div className="alert error" role="alert">
            <HelpCircle size={18} />
            <span>{error || planError || artworkError}</span>
            <button
              aria-label="Fermer le message"
              onClick={() => {
                setError('')
                setPlanError('')
              }}
            >
              <X size={17} />
            </button>
          </div>
        )}
        {notice && (
          <div className="alert notice" role="status">
            <Check size={17} />
            <span>{notice}</span>
            <button aria-label="Fermer la notification" onClick={() => setNotice('')}>
              <X size={17} />
            </button>
          </div>
        )}
        <div className="workspace">
          <aside className="settings-panel" aria-label="Réglages d’imposition">
            <div className="panel-heading">
              <span>Les réglages</span>
              <span className="small-muted">01 — 04</span>
            </div>
            <fieldset disabled={pending} className="settings-fields">
              <section className="setting-section">
                <h2>
                  <span className="section-number">01</span>Votre document
                </h2>
                <input
                  ref={fileRef}
                  type="file"
                  accept="application/pdf,.pdf"
                  className="sr-only"
                  aria-label="Importer un PDF"
                  onChange={(e) => {
                    const f = e.target.files?.[0]
                    if (f) void upload(f)
                  }}
                />
                {job ? (
                  <div className="file-box">
                    <FileText size={26} />
                    <div>
                      <strong title={job.name}>{job.name}</strong>
                      <small>
                        {job.document.pages.length} page
                        {duplex ? 's · Recto verso' : ' · Recto seul'}
                      </small>
                    </div>
                    <button
                      className="icon-button"
                      onClick={() => void remove()}
                      aria-label="Supprimer le document"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ) : (
                  <button
                    className={`dropzone ${dragging ? 'dragging' : ''}`}
                    onClick={() => fileRef.current?.click()}
                    onDragOver={(e) => {
                      e.preventDefault()
                      setDragging(true)
                    }}
                    onDragLeave={() => setDragging(false)}
                    onDrop={(e) => {
                      e.preventDefault()
                      setDragging(false)
                      if (e.dataTransfer.files[0]) void upload(e.dataTransfer.files[0])
                    }}
                  >
                    <span className="upload-icon">
                      {loading ? <LoaderCircle className="spin" size={22} /> : <Upload size={22} />}
                    </span>
                    <strong>{loading ? 'Analyse du document…' : 'Déposez votre PDF ici'}</strong>
                    <span>
                      ou <u>parcourir les fichiers</u>
                    </span>
                    <small>1 ou 2 pages · 25 Mo maximum</small>
                  </button>
                )}
                {job && (
                  <button className="text-button" onClick={() => fileRef.current?.click()}>
                    <Plus size={14} />
                    Changer de PDF
                  </button>
                )}
                <p className="privacy-note">
                  L’import autorise le traitement par le serveur local. Suppression automatique sous
                  24 h.
                </p>
                {!job && (
                  <button
                    className="example-button"
                    onClick={() => void example()}
                    disabled={loading}
                  >
                    Essayer avec une carte exemple <ArrowRight size={14} />
                  </button>
                )}
              </section>
              <section className="setting-section">
                <h2>
                  <span className="section-number">02</span>La feuille d’impression
                </h2>
                <label className="field">
                  <span>Format de feuille</span>
                  <span className="select-wrap">
                    <select
                      value={selectedSheet}
                      onChange={(e) => {
                        const size = sheets[e.target.value]
                        if (size) update({ sheet_width: size[0], sheet_height: size[1] })
                        else update({ sheet_width: settings.sheet_width + 0.1 })
                      }}
                    >
                      <option value="SRA3">SRA3 · 320 × 450 mm</option>
                      <option value="A3">A3 · 297 × 420 mm</option>
                      <option value="A4">A4 · 210 × 297 mm</option>
                      <option value="custom">Personnalisé</option>
                    </select>
                    <ChevronDown size={15} />
                  </span>
                </label>
                <div className="field-row">
                  <Field
                    label="Largeur"
                    value={settings.sheet_width}
                    min={1}
                    onChange={(n) => update({ sheet_width: n })}
                  />
                  <Field
                    label="Hauteur"
                    value={settings.sheet_height}
                    min={1}
                    onChange={(n) => update({ sheet_height: n })}
                  />
                </div>
                <div className="orientation-row">
                  <button
                    className="text-button"
                    onClick={() =>
                      update({
                        sheet_width: settings.sheet_height,
                        sheet_height: settings.sheet_width,
                      })
                    }
                  >
                    <RotateCw size={14} />
                    Pivoter la feuille
                  </button>
                  <span className="small-muted">
                    {settings.sheet_height >= settings.sheet_width ? 'Portrait' : 'Paysage'}
                  </span>
                </div>
                <Field
                  label="Marges machine, sur les 4 côtés"
                  value={settings.margin}
                  max={100}
                  onChange={(n) => update({ margin: n })}
                />
              </section>
              <section className="setting-section">
                <h2>
                  <span className="section-number">03</span>Le placement
                </h2>
                <div className="field-row">
                  <Field
                    label="Largeur finie"
                    readOnly
                    value={settings.trim_width}
                    onChange={() => {}}
                    min={0.1}
                  />
                  <Field
                    label="Hauteur finie"
                    readOnly
                    value={settings.trim_height}
                    onChange={() => {}}
                    min={0.1}
                  />
                </div>
                <p className="field-hint">Format lu dans le PDF. Export sans redimensionnement.</p>
                {job && !job.document.pages.every((p) => p.has_trim) && (
                  <label className="checkbox-label trim-confirm">
                    <input
                      type="checkbox"
                      checked={settings.confirm_trim}
                      onChange={(e) => update({ confirm_trim: e.target.checked })}
                    />
                    <span>Je confirme que le format proposé correspond au format fini.</span>
                  </label>
                )}
                <div className="field-row">
                  <Field
                    label="Fond perdu"
                    value={settings.bleed}
                    max={20}
                    onChange={(n) => update({ bleed: n })}
                  />
                  <Field
                    label="Espacement"
                    value={settings.gap}
                    max={100}
                    onChange={(n) => update({ gap: n })}
                  />
                </div>
                {job && (
                  <p className="field-hint">
                    Fond perdu disponible :{' '}
                    {format(Math.min(...job.document.pages.map((p) => p.available_bleed)))} mm.
                    Présence du contenu à vérifier.
                  </p>
                )}
                <label className="field">
                  <span>Orientation des poses</span>
                  <span className="select-wrap">
                    <select
                      value={settings.rotation}
                      onChange={(e) => update({ rotation: e.target.value as Settings['rotation'] })}
                    >
                      <option value="auto">Automatique · meilleur rendement</option>
                      <option value="0">Sans rotation · 0°</option>
                      <option value="90">Quart de tour · 90°</option>
                    </select>
                    <ChevronDown size={15} />
                  </span>
                </label>
                <details className="manual-grid">
                  <summary>
                    Grille manuelle <Plus size={13} />
                  </summary>
                  <div className="field-row">
                    <Field
                      label="Colonnes (0 = auto)"
                      value={settings.columns || 0}
                      max={100}
                      step={1}
                      unit=""
                      onChange={(n) => update({ columns: n || null })}
                    />
                    <Field
                      label="Lignes (0 = auto)"
                      value={settings.rows || 0}
                      max={100}
                      step={1}
                      unit=""
                      onChange={(n) => update({ rows: n || null })}
                    />
                  </div>
                </details>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={settings.crop_marks}
                    onChange={(e) => update({ crop_marks: e.target.checked })}
                  />
                  <span>Ajouter les repères de coupe</span>
                  <ScanLine size={16} />
                </label>
              </section>
              <section className="setting-section">
                <h2>
                  <span className="section-number">04</span>Le tirage
                </h2>
                <Field
                  label="Quantité souhaitée"
                  value={settings.quantity}
                  min={1}
                  max={1000000}
                  step={1}
                  unit="ex."
                  onChange={(n) => update({ quantity: n })}
                />
                {duplex && (
                  <label className="field">
                    <span>Retournement recto verso</span>
                    <span className="select-wrap">
                      <select
                        value={settings.flip}
                        onChange={(e) => update({ flip: e.target.value as Settings['flip'] })}
                      >
                        <option value="long">Sur le bord long</option>
                        <option value="short">Sur le bord court</option>
                      </select>
                      <ChevronDown size={15} />
                    </span>
                  </label>
                )}
              </section>
              <Configurations
                toolId="imposition"
                settings={{ ...settings }}
                onLoad={(saved) =>
                  update({
                    ...(saved as Settings),
                    ...(job
                      ? { trim_width: settings.trim_width, trim_height: settings.trim_height }
                      : {}),
                    confirm_trim: false,
                  })
                }
              />
            </fieldset>
          </aside>
          <section className="preview-panel" aria-label="Aperçu de l’imposition">
            <div className="preview-toolbar">
              <div className="face-tabs" role="tablist" aria-label="Face affichée">
                <button
                  role="tab"
                  aria-selected={face === 'front'}
                  className={face === 'front' ? 'selected' : ''}
                  onClick={() => setFace('front')}
                >
                  Recto
                </button>
                <button
                  role="tab"
                  aria-selected={face === 'back'}
                  className={face === 'back' ? 'selected' : ''}
                  disabled={!duplex}
                  onClick={() => setFace('back')}
                >
                  Verso
                </button>
              </div>
              <div className="view-switch">
                <button
                  className={view === 'plan' ? 'selected' : ''}
                  onClick={() => setView('plan')}
                >
                  <LayoutGrid size={14} />
                  Plan
                </button>
                <button
                  disabled={!job}
                  className={view === 'pdf' ? 'selected' : ''}
                  onClick={() => setView('pdf')}
                >
                  <FileText size={14} />
                  {exported ? 'PDF généré' : 'Aperçu PDF'}
                </button>
              </div>
            </div>
            <div className="preview-caption">
              <span>
                <span className="sheet-dot" />
                {selectedSheet === 'custom' ? 'Feuille personnalisée' : selectedSheet}{' '}
                <span className="caption-dimensions">
                  {format(settings.sheet_width)} × {format(settings.sheet_height)} mm
                </span>
              </span>
              <span>
                {planning
                  ? 'Calcul en cours…'
                  : displayPlan
                    ? `${displayPlan.columns} colonnes × ${displayPlan.rows} lignes`
                    : 'Aucun document importé'}
              </span>
            </div>
            <div className={`preview-stage ${!job ? 'empty-stage' : ''}`}>
              {!job ? (
                <div className="empty-preview">
                  <div className="empty-sheet">
                    <div className="empty-sheet-grid">
                      {Array.from({ length: 6 }, (_, i) => (
                        <div key={i}>
                          <span />
                          <span />
                        </div>
                      ))}
                    </div>
                    <span className="empty-sheet-label">VOTRE PROCHAINE PLANCHE</span>
                  </div>
                  <h2>Tout commence par votre PDF.</h2>
                  <p>
                    Importez votre document pour trouver
                    <br />
                    sa place sur la feuille.
                  </p>
                  <Button
                    variant="outline"
                    onClick={() => fileRef.current?.click()}
                    disabled={loading}
                  >
                    <Upload size={15} />
                    Importer un PDF
                  </Button>
                </div>
              ) : view === 'pdf' && !exported ? (
                <LivePreview
                  state={livePreview}
                  pageNumber={face === 'front' ? 1 : 2}
                  onPageChange={(page) => setFace(page === 1 ? 'front' : 'back')}
                />
              ) : view === 'pdf' && exported ? (
                <div className="sheet-holder">
                  <PdfPreview
                    url={`/api/jobs/${job.id}/output?v=${encodeURIComponent(JSON.stringify(exported.settings))}`}
                    page={face === 'front' ? 1 : 2}
                  />
                </div>
              ) : displayPlan ? (
                <div className="sheet-holder">
                  <div className="dimension-top">{format(settings.sheet_width)} mm</div>
                  <svg
                    className="sheet-svg"
                    viewBox={`-1 -1 ${settings.sheet_width + 2} ${settings.sheet_height + 2}`}
                    role="img"
                    aria-label={`${face === 'front' ? 'Recto' : 'Verso'} : ${displayPlan.poses} poses, rotation ${displayPlan.rotation} degrés`}
                  >
                    <rect
                      width={settings.sheet_width}
                      height={settings.sheet_height}
                      fill="white"
                    />
                    <rect
                      x={settings.margin}
                      y={settings.margin}
                      width={Math.max(0, settings.sheet_width - 2 * settings.margin)}
                      height={Math.max(0, settings.sheet_height - 2 * settings.margin)}
                      fill="none"
                      stroke="#b5c5bd"
                      strokeWidth=".4"
                      strokeDasharray="2 2"
                    />
                    {displayPlan[face].map((p, i) => (
                      <g
                        key={i}
                        transform={`translate(${p.x} ${settings.sheet_height - p.y - p.height})`}
                      >
                        <rect
                          x={-settings.bleed}
                          y={-settings.bleed}
                          width={p.width + 2 * settings.bleed}
                          height={p.height + 2 * settings.bleed}
                          fill="#f1dcd1"
                        />
                        {images[face === 'front' ? 0 : 1] ? (
                          <image
                            href={images[face === 'front' ? 0 : 1]}
                            width={settings.trim_width}
                            height={settings.trim_height}
                            transform={
                              p.rotation === 90 ? `translate(0 ${p.height}) rotate(-90)` : undefined
                            }
                            preserveAspectRatio="none"
                          />
                        ) : (
                          <rect width={p.width} height={p.height} fill="#e2eae4" />
                        )}
                        <rect
                          width={p.width}
                          height={p.height}
                          fill="none"
                          stroke="#1d5144"
                          strokeWidth=".25"
                        />
                      </g>
                    ))}
                    {displayPlan.marks.map((m, i) => (
                      <line
                        key={i}
                        x1={m.x1}
                        y1={settings.sheet_height - m.y1}
                        x2={m.x2}
                        y2={settings.sheet_height - m.y2}
                        stroke="#333"
                        strokeWidth=".15"
                      />
                    ))}
                  </svg>
                  <div className="dimension-side">{format(settings.sheet_height)} mm</div>
                </div>
              ) : (
                <div className="calculation-state">
                  {planning ? (
                    <>
                      <LoaderCircle size={24} className="spin" />
                      <p>Calcul de votre planche…</p>
                    </>
                  ) : (
                    <>
                      <LayoutGrid size={26} />
                      <p>Ajustez les réglages pour afficher la planche.</p>
                    </>
                  )}
                </div>
              )}
            </div>
            <div className="preview-legend">
              <span>
                <i className="legend-printable" />
                Zone imprimable
              </span>
              <span>
                <i className="legend-trim" />
                Format fini
              </span>
              <span>
                <i className="legend-bleed" />
                Fond perdu
              </span>
              <span className="preview-scale">Aperçu ajusté à l’écran</span>
            </div>
            <div className="results">
              <div>
                <span>POSES PAR FEUILLE</span>
                <strong>
                  {displayPlan?.poses ?? '—'}
                  <small>{displayPlan ? `${displayPlan.rotation}°` : ''}</small>
                </strong>
              </div>
              <div>
                <span>FEUILLES À IMPRIMER</span>
                <strong>
                  {displayPlan ? format(displayPlan.sheets) : '—'}
                  <small>{duplex ? 'recto verso' : 'recto seul'}</small>
                </strong>
              </div>
              <div>
                <span>EXEMPLAIRES PRODUITS</span>
                <strong>
                  {displayPlan ? format(displayPlan.produced) : '—'}
                  <small>
                    {displayPlan
                      ? `+ ${format(displayPlan.produced - settings.quantity)} de marge`
                      : ''}
                  </small>
                </strong>
              </div>
            </div>
            {duplex && displayPlan && (
              <div className="flip-note">
                <FlipHorizontal2 size={21} />
                <p>
                  <strong>
                    Retournement sur le bord {settings.flip === 'long' ? 'long' : 'court'}
                  </strong>
                  <span>
                    Le verso est replacé en miroir sur cet axe. Vérifiez la correspondance sur une
                    épreuve à 100 %.
                  </span>
                </p>
              </div>
            )}
            <div className="export-bar">
              <div>
                <strong>
                  {exported ? 'Votre planche est prête.' : 'Prêt pour le prochain tirage ?'}
                </strong>
                <p>
                  {exported
                    ? `Imprimer la ${duplex ? 'paire recto verso' : 'feuille type'} ${exported.sheets} fois à 100 %.`
                    : 'Générez la feuille type, puis contrôlez le PDF.'}
                </p>
              </div>
              {exported && job ? (
                <div className="download-actions">
                  <a className="settings-link" href={`/api/jobs/${job.id}/settings`} download>
                    Fiche de réglages
                  </a>
                  <Button asChild>
                    <a href={`/api/jobs/${job.id}/output`} download>
                      <ArrowDownToLine size={17} />
                      Télécharger le PDF
                    </a>
                  </Button>
                </div>
              ) : (
                <Button
                  onClick={() => void generate()}
                  disabled={!displayPlan || planning || pending || !settings.confirm_trim}
                >
                  {exporting ? (
                    <LoaderCircle className="spin" size={17} />
                  ) : (
                    <ArrowRight size={17} />
                  )}
                  {exporting ? 'Génération…' : 'Générer le PDF'}
                </Button>
              )}
            </div>
          </section>
        </div>
        {warnings.length > 0 && (
          <details className="warnings">
            <summary>
              <HelpCircle size={15} />
              Points de contrôle avant impression <ChevronDown size={14} />
            </summary>
            <ul>
              {[...new Set(warnings)].map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </details>
        )}
        <footer>
          <span>
            Snackpress est proposé par{' '}
            <a href="https://ikyoh.com" className="footer-credit-link">
              ikyoh
            </a>
          </span>
          <span>Prototype · Validation sur presse requise · Sans certification PDF/X</span>
        </footer>
      </main>
      <dialog
        ref={helpRef}
        onCancel={() => setHelp(false)}
        onClose={() => setHelp(false)}
        className="help-dialog"
      >
        <div className="dialog-title">
          <h2>Une planche en quelques gestes.</h2>
          <button
            className="icon-button"
            onClick={() => setHelp(false)}
            aria-label="Fermer le mode d’emploi"
          >
            <X size={20} />
          </button>
        </div>
        <ol>
          <li>Importez un PDF d’une page ou de deux pages : recto, puis verso.</li>
          <li>Confirmez le format fini. Réglez la feuille, les marges machine et l’espacement.</li>
          <li>
            Contrôlez les poses et le retournement. Générez le PDF pour inspecter le résultat réel.
          </li>
          <li>
            Téléchargez la feuille type et sa fiche. Imprimez le nombre de répétitions indiqué à 100
            %.
          </li>
        </ol>
        <p>
          Limites du prototype : 25 Mo, 2 000 poses, pages sans annotations, signatures, rotation
          PDF ou unités spéciales. Le fond perdu provient du fichier source. La rotation des poses
          reste disponible.
        </p>
        <p>
          Les fichiers sont conservés sur le serveur local pendant 24 h au maximum. Le bouton
          corbeille supprime immédiatement le travail.
        </p>
        <Button onClick={() => setHelp(false)}>
          C’est parti <ArrowRight size={16} />
        </Button>
      </dialog>
    </>
  )
}

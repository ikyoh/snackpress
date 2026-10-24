import { useEffect, useRef, useState, type ReactNode } from 'react'
import { getDocument } from 'pdfjs-dist'
import { Plus, Trash2 } from 'lucide-react'
import { Button } from './components/ui/button'
import { Configurations } from './Configurations'
import { SettingsSection } from './SettingsSection'
import type { PizzaValues } from './pizza'

export type Numbering = {
  x: number
  y: number
  color: string
  size: number
  font: string
  rotation: number
}
export const newNumbering = (height: number): Numbering => ({
  x: 6,
  y: Math.max(0, height - 6),
  color: '#183d36',
  size: 8,
  font: 'SnackBold',
  rotation: 0,
})
const fonts = [
  ['SnackBold', 'Vera gras', 'FortuneVeraBold'],
  ['Snack', 'Vera', 'FortuneVera'],
  ['Helvetica', 'Helvetica', 'Arial, sans-serif'],
  ['Times-Roman', 'Times', 'Times New Roman, serif'],
  ['Courier', 'Courier', 'Courier New, monospace'],
]

export function FortuneTemplate({
  template,
  defaults,
  onChange,
  children,
}: {
  template: PizzaValues | null
  defaults: PizzaValues
  onChange: (template: PizzaValues | null) => void
  children: ReactNode
}) {
  return (
    <SettingsSection
      title="Format"
      defaultOpen
      summary={
        template ? `Gabarit Pizza · ${template.width} × ${template.height} mm` : 'Format du support'
      }
    >
      <label className="field">
        <span>Source du format</span>
        <select
          value={template ? 'pizza' : 'support'}
          onChange={(e) => onChange(e.target.value === 'pizza' ? defaults : null)}
        >
          <option value="support">Format du support</option>
          <option value="pizza">Gabarit Pizza</option>
        </select>
      </label>
      {template ? (
        <>
          <p className="field-hint">
            Chargez une configuration Pizza enregistrée. Son format fini et son fond perdu
            définissent le format des billets. Les repères sont visibles dans l’aperçu PDF et
            absents du PDF final téléchargé.
          </p>
          <Configurations
            compact
            autoLoadDefault={false}
            toolId="pizza"
            settings={template}
            onLoad={(settings) => onChange(settings as PizzaValues)}
          />
          <p className="field-hint">
            Format fini : {template.width} × {template.height} mm · Fond perdu : {template.bleed} mm
            par côté.
          </p>
        </>
      ) : (
        children
      )}
    </SettingsSection>
  )
}

export function FortuneImposition({
  template,
  defaults,
  perBook,
  onChange,
  onPerBookChange,
}: {
  template: PizzaValues | null
  defaults: PizzaValues
  perBook: string | number
  onChange: (template: PizzaValues | null) => void
  onPerBookChange: (value: string | number) => void
}) {
  return (
    <SettingsSection
      title="Imposition en souches"
      summary={
        template
          ? `${perBook} billets par souche · ${template.sheet_width} × ${template.sheet_height} mm`
          : 'Sans imposition'
      }
    >
      <label className="checkbox-label">
        <input
          type="checkbox"
          checked={!!template}
          onChange={(e) => onChange(e.target.checked ? defaults : null)}
        />
        <span>Imposer avec un gabarit Layer Cake</span>
      </label>
      <p className="field-hint">
        Chargez une configuration Layer Cake en poses répétées. Les numéros sont répartis pour
        obtenir des souches consécutives après empilage et coupe de toutes les feuilles ensemble. Le
        nombre total de billets vient des réglages Fortune Cookie.
      </p>
      {template && (
        <>
          <label className="field">
            <span>Billets par souche</span>
            <input
              type="number"
              min={1}
              max={100}
              step={1}
              required
              value={perBook}
              onChange={(e) => onPerBookChange(e.target.value === '' ? '' : Number(e.target.value))}
            />
          </label>
          <Configurations
            compact
            autoLoadDefault={false}
            toolId="layer-cake"
            settings={template}
            onLoad={(settings) => onChange(settings as PizzaValues)}
          />
          <p className="field-hint">
            Exemple : 25 billets par souche et 4 poses donnent 1, 26, 51 et 76 sur la première
            feuille, pour 100 billets. Ramassez les piles découpées de gauche à droite puis de haut
            en bas. La dernière souche peut être incomplète ; les poses inutilisées restent
            blanches.
          </p>
        </>
      )}
    </SettingsSection>
  )
}

export function FortuneSettings({
  items,
  height,
  width,
  onChange,
}: {
  items: Numbering[]
  height: number
  width: number
  onChange: (items: Numbering[]) => void
}) {
  const update = (index: number, patch: Partial<Numbering>) =>
    onChange(items.map((item, i) => (i === index ? { ...item, ...patch } : item)))
  return (
    <section className="fortune-settings">
      <h2>
        Vos numérotations <span>({items.length})</span>
      </h2>
      <p>La même séquence à plusieurs endroits, avec un style pour chaque numérotation.</p>
      {items.map((item, i) => (
        <fieldset className="fortune-numbering" key={i}>
          <legend>Numérotation {i + 1}</legend>
          <div className="tool-fields">
            {(
              [
                ['x', 'Position X', 'mm', 0, width],
                ['y', 'Position Y', 'mm', 0, height],
                ['size', 'Taille', 'pt', 1, 300],
                ['rotation', 'Rotation', '°', -360, 360],
              ] as const
            ).map(([key, label, unit, min, max]) => (
              <label className="field" key={key}>
                <span>
                  {label} ({unit})
                </span>
                <input
                  type="number"
                  min={min}
                  max={max}
                  step="any"
                  required
                  value={item[key]}
                  onChange={(e) => {
                    if (e.target.value !== '') update(i, { [key]: Number(e.target.value) })
                  }}
                />
              </label>
            ))}
            <label className="field">
              <span>Police</span>
              <select value={item.font} onChange={(e) => update(i, { font: e.target.value })}>
                {fonts.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Couleur</span>
              <input
                type="color"
                value={item.color}
                onChange={(e) => update(i, { color: e.target.value })}
              />
            </label>
          </div>
          <button
            type="button"
            className="text-button"
            onClick={() => onChange(items.filter((_, n) => n !== i))}
          >
            <Trash2 size={14} /> Supprimer la numérotation {i + 1}
          </button>
        </fieldset>
      ))}
      <Button type="button" onClick={() => onChange([...items, newNumbering(height)])}>
        <Plus size={16} /> Ajouter une numérotation
      </Button>
    </section>
  )
}

export function FortunePreview({
  items,
  width,
  height,
  bleed,
  serial,
  file,
  disabled,
  onChange,
}: {
  items: Numbering[]
  width: number
  height: number
  bleed: number
  serial: string
  file?: File
  disabled: boolean
  onChange: (items: Numbering[]) => void
}) {
  const [background, setBackground] = useState('')
  const [error, setError] = useState('')
  const svg = useRef<SVGSVGElement>(null)
  const moving = useRef<{ index: number; dx: number; dy: number } | null>(null)
  useEffect(() => {
    setBackground('')
    setError('')
    if (!file) return
    let disposed = false
    let task: ReturnType<typeof getDocument> | undefined
    void (async () => {
      try {
        const data = await file.arrayBuffer()
        if (disposed) return
        task = getDocument({ data })
        const pdf = await task.promise
        const page = await pdf.getPage(1)
        const viewport = page.getViewport({ scale: 2 })
        const canvas = document.createElement('canvas')
        canvas.width = viewport.width
        canvas.height = viewport.height
        await page.render({ canvas, viewport }).promise
        const matches = (w: number, h: number) =>
          Math.abs((viewport.width * 25.4) / 144 - w) <= 0.1 &&
          Math.abs((viewport.height * 25.4) / 144 - h) <= 0.1
        let artwork = canvas
        if (bleed > 0 && matches(width + 2 * bleed, height + 2 * bleed)) {
          artwork = document.createElement('canvas')
          const inset = (bleed * 144) / 25.4
          artwork.width = Math.round((width * 144) / 25.4)
          artwork.height = Math.round((height * 144) / 25.4)
          artwork
            .getContext('2d')!
            .drawImage(
              canvas,
              inset,
              inset,
              (width * 144) / 25.4,
              (height * 144) / 25.4,
              0,
              0,
              artwork.width,
              artwork.height,
            )
        } else if (!matches(width, height)) {
          throw new Error('Unsupported artwork frame')
        }
        if (!disposed) setBackground(artwork.toDataURL())
      } catch {
        if (!disposed)
          setError(
            'Le cadrage du fond ne peut pas être affiché ici. Contrôlez le fond dans l’aperçu PDF.',
          )
      }
    })()
    return () => {
      disposed = true
      void task?.destroy()
    }
  }, [file, width, height, bleed])
  const point = (e: React.PointerEvent) => {
    const rect = svg.current!.getBoundingClientRect()
    return {
      x: ((e.clientX - rect.left) / rect.width) * width,
      y: ((e.clientY - rect.top) / rect.height) * height,
    }
  }
  return (
    <div className="fortune-preview">
      <h2>Placez vos numérotations</h2>
      <p>
        Glissez un numéro pour le déplacer. X et Y repèrent le début de sa ligne de base depuis le
        coin supérieur gauche.
      </p>
      {error && <p role="alert">{error}</p>}
      <svg
        ref={svg}
        viewBox={`0 0 ${width} ${height}`}
        className="fortune-sheet"
        aria-label="Placement des numérotations sur le support"
        onPointerMove={(e) => {
          if (!moving.current || disabled) return
          const { index, dx, dy } = moving.current
          const p = point(e)
          onChange(
            items.map((item, i) =>
              i === index
                ? {
                    ...item,
                    x: Math.round(Math.max(0, Math.min(width, p.x - dx)) * 10) / 10,
                    y: Math.round(Math.max(0, Math.min(height, p.y - dy)) * 10) / 10,
                  }
                : item,
            ),
          )
        }}
        onPointerUp={() => {
          moving.current = null
        }}
        onPointerCancel={() => {
          moving.current = null
        }}
      >
        <rect width={width} height={height} fill="white" />
        {background && (
          <image href={background} width={width} height={height} preserveAspectRatio="none" />
        )}
        {items.map((item, i) => (
          <text
            key={i}
            x={item.x}
            y={item.y}
            transform={`rotate(${item.rotation} ${item.x} ${item.y})`}
            fontFamily={fonts.find(([value]) => value === item.font)?.[2]}
            fontSize={(item.size * 25.4) / 72}
            fill={item.color}
            className="fortune-draggable"
            aria-label={`Déplacer la numérotation ${i + 1}`}
            onPointerDown={(e) => {
              if (disabled) return
              e.preventDefault()
              const p = point(e)
              moving.current = { index: i, dx: p.x - item.x, dy: p.y - item.y }
              svg.current!.setPointerCapture(e.pointerId)
            }}
          >
            {serial}
          </text>
        ))}
      </svg>
      <p>
        {width} × {height} mm finis · Premier exemplaire · Le fond perdu de {bleed} mm est visible
        dans l’aperçu PDF. Les coordonnées des numéros restent relatives au format fini.
      </p>
    </div>
  )
}

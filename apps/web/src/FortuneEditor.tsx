import { useEffect, useRef, useState } from 'react'
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
}: {
  template: PizzaValues | null
  defaults: PizzaValues
  onChange: (template: PizzaValues | null) => void
}) {
  return (
    <SettingsSection
      title="Gabarit Pizza"
      summary={
        template ? `${template.width} × ${template.height} mm · Aperçu uniquement` : 'Sans gabarit'
      }
    >
      <label className="checkbox-label">
        <input
          type="checkbox"
          checked={!!template}
          onChange={(e) => onChange(e.target.checked ? defaults : null)}
        />
        <span>Afficher un gabarit Pizza dans l’aperçu PDF</span>
      </label>
      <p className="field-hint">
        Chargez une configuration Pizza enregistrée. Le support reprend son format fini. Les repères
        sont absents du PDF final téléchargé.
      </p>
      {template && (
        <Configurations
          compact
          autoLoadDefault={false}
          toolId="pizza"
          settings={template}
          onLoad={(settings) => onChange(settings as PizzaValues)}
        />
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
        obtenir des souches consécutives après coupe de chaque pile de feuilles. Le nombre total de
        billets vient des réglages Fortune Cookie.
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
            feuille. La dernière souche peut être incomplète ; les poses inutilisées restent
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
  serial,
  file,
  disabled,
  onChange,
}: {
  items: Numbering[]
  width: number
  height: number
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
        if (!disposed) setBackground(canvas.toDataURL())
      } catch {
        if (!disposed)
          setError('Le fond ne peut pas être affiché. Vérifiez le fichier PDF importé.')
      }
    })()
    return () => {
      disposed = true
      void task?.destroy()
    }
  }, [file])
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
        {width} × {height} mm · Premier exemplaire · Les codes sont visibles dans le PDF généré. Les
        éléments hors du support seront coupés.
      </p>
    </div>
  )
}

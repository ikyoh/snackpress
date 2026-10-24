import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from 'react'
import { getDocument } from 'pdfjs-dist'
import { Plus, Trash2 } from 'lucide-react'
import { Button } from './components/ui/button'
import { Configurations } from './Configurations'
import { SettingsSection } from './SettingsSection'
import type { PizzaValues } from './pizza'

import {
  barcodeError,
  barcodeCaption,
  barcodeCaptionHeight,
  newRepiquage,
  parseCsv,
  repiquageValue,
  type CsvData,
  type Repiquage,
} from './fortuneData'

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
            définissent le format des billets. Les repères sont visibles dans l’aperçu de placement.
            L’aperçu PDF montre le format fini, sans repères ni fonds perdus.
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

export function FortuneData({
  data,
  onChange,
}: {
  data: CsvData | null
  onChange: (data: CsvData | null) => void
}) {
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const version = useRef(0)
  useEffect(
    () => () => {
      version.current++
    },
    [],
  )
  return (
    <SettingsSection
      title="Données CSV"
      summary={
        data ? `${data.rows.length} lignes · ${data.columns.length} colonnes` : 'Aucun CSV chargé'
      }
    >
      <p className="field-hint">
        La première ligne contient les noms des colonnes. Une ligne de données correspond à un
        billet. Virgule, point-virgule ou tabulation ; 1 000 lignes maximum. Les zéros initiaux sont
        conservés.
      </p>
      <label className="field">
        <span>Importer un CSV</span>
        <input
          type="file"
          accept=".csv,text/csv,text/tab-separated-values,.tsv"
          disabled={loading}
          onChange={async (e) => {
            const file = e.currentTarget.files?.[0]
            e.currentTarget.value = ''
            if (!file) return
            const current = ++version.current
            setError('')
            setLoading(true)
            try {
              if (file.size > 1024 * 1024) throw new Error('Le fichier CSV est limité à 1 Mo.')
              const parsed = parseCsv(await file.arrayBuffer())
              if (current === version.current) onChange(parsed)
            } catch (error) {
              if (current === version.current) setError((error as Error).message)
            } finally {
              if (current === version.current) setLoading(false)
            }
          }}
        />
      </label>
      {loading && <p role="status">Lecture du CSV…</p>}
      {error && <p role="alert">{error}</p>}
      {data && (
        <>
          <p>
            {data.rows.length} lignes chargées · {data.columns.join(', ')}
          </p>
          <p className="field-hint">
            L’import règle le nombre d’exemplaires sur le nombre de lignes. L’aperçu de placement
            montre la première ligne. Le CSV est conservé avec la configuration enregistrée.
          </p>
          <button
            type="button"
            className="text-button"
            onClick={() => {
              version.current++
              onChange(null)
              setError('')
            }}
          >
            <Trash2 size={14} /> Retirer le CSV
          </button>
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
  data,
  serial,
}: {
  items: Repiquage[]
  height: number
  width: number
  onChange: (items: Repiquage[]) => void
  data: CsvData | null
  serial: string
}) {
  const update = (index: number, patch: Partial<Repiquage>) =>
    onChange(items.map((item, i) => (i === index ? { ...item, ...patch } : item)))
  return (
    <section className="fortune-settings">
      <h2>
        Vos repiquages <span>({items.length})</span>
      </h2>
      <p>
        Chaque repiquage utilise une numérotation ou une colonne CSV, en texte ou en code-barres. X
        et Y ancrent la première ligne de texte ou le bas du code-barres ; l’alignement s’applique
        autour de ce point.
      </p>
      {items.map((item, i) => (
        <fieldset className="fortune-numbering" key={i}>
          <legend>Repiquage {i + 1}</legend>
          <div className="tool-fields">
            <label className="field">
              <span>Source du repiquage</span>
              <select
                value={item.source}
                onChange={(e) =>
                  update(i, {
                    source: e.target.value as Repiquage['source'],
                    column: item.column || data?.columns[0] || '',
                  })
                }
              >
                <option value="sequence">Numérotation</option>
                <option value="csv">Champ CSV</option>
              </select>
            </label>
            {item.source === 'csv' && (
              <label className="field">
                <span>Colonne CSV</span>
                <select
                  required
                  value={item.column}
                  onChange={(e) => update(i, { column: e.target.value })}
                >
                  <option value="">Choisir une colonne</option>
                  {item.column && !data?.columns.includes(item.column) && (
                    <option value="" disabled>
                      Colonne absente : {item.column}
                    </option>
                  )}
                  {data?.columns.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label className="field">
              <span>Rendu du repiquage</span>
              <select
                value={item.rendering}
                onChange={(e) => update(i, { rendering: e.target.value as Repiquage['rendering'] })}
              >
                <option value="text">Texte</option>
                <option value="code128">Code-barres Code 128</option>
                <option value="ean13">Code-barres EAN-13</option>
              </select>
            </label>
            <label className="field">
              <span>Alignement</span>
              <select
                value={item.align}
                onChange={(e) => update(i, { align: e.target.value as Repiquage['align'] })}
              >
                <option value="left">À gauche</option>
                <option value="center">Centré</option>
                <option value="right">À droite</option>
              </select>
            </label>
            {(
              [
                ['x', 'Position X', 'mm', 0, width],
                ['y', 'Position Y', 'mm', 0, height],
                ['size', 'Taille', 'pt', 1, 300],
                ['rotation', 'Rotation', '°', -360, 360],
              ] as const
            )
              .filter(([key]) => key !== 'size' || item.rendering === 'text')
              .map(([key, label, unit, min, max]) => (
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
            {item.rendering === 'text' && (
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
            )}
            {item.rendering !== 'text' && (
              <>
                {(['barcode_width', 'barcode_height'] as const).map((key) => (
                  <label key={key} className="field">
                    <span>
                      {key === 'barcode_width'
                        ? 'Largeur du code-barres'
                        : 'Hauteur du code-barres'}{' '}
                      (mm)
                    </span>
                    <input
                      type="number"
                      required
                      min={0.1}
                      max={500}
                      step="any"
                      value={item[key]}
                      onChange={(e) => {
                        if (e.target.value !== '') update(i, { [key]: Number(e.target.value) })
                      }}
                    />
                  </label>
                ))}
              </>
            )}
            <label className="field">
              <span>Couleur</span>
              <input
                type="color"
                value={item.color}
                onChange={(e) => update(i, { color: e.target.value })}
              />
            </label>
          </div>
          {item.rendering !== 'text' && (
            <p className="field-hint">
              La largeur comprend les marges blanches de lecture. La hauteur règle les barres ; leur
              valeur lisible est ajoutée en dessous. Le fond reste blanc sous les barres, les marges
              et les chiffres.{' '}
              {item.rendering === 'ean13' &&
                '12 chiffres : clé calculée ; 13 chiffres : clé vérifiée.'}
            </p>
          )}
          {barcodeError(repiquageValue(item, serial, data), item.rendering) && (
            <p role="alert">{barcodeError(repiquageValue(item, serial, data), item.rendering)}</p>
          )}
          <button
            type="button"
            className="text-button"
            onClick={() => onChange(items.filter((_, n) => n !== i))}
          >
            <Trash2 size={14} /> Supprimer le repiquage {i + 1}
          </button>
        </fieldset>
      ))}
      <Button type="button" onClick={() => onChange([...items, newRepiquage(height)])}>
        <Plus size={16} /> Ajouter un repiquage
      </Button>
    </section>
  )
}

function FortunePizzaGuides({ template }: { template: PizzaValues }) {
  const id = useId()
  const n = (key: string) =>
    Number(template[key] ?? (key.startsWith('safety_') ? (template.safety ?? 4) : 0))
  const width = n('width')
  const height = template.shape === 'circle' ? width : n('height')
  const contour = (left = 0, right = 0, top = 0, bottom = 0) => {
    const w = width - left - right
    const h = height - top - bottom
    if (template.shape === 'circle' || template.shape === 'ellipse')
      return <ellipse cx={left + w / 2} cy={top + h / 2} rx={w / 2} ry={h / 2} />
    const radius = Math.min(
      Math.max(0, n('corner_radius') - Math.max(left, right, top, bottom)),
      w / 2,
      h / 2,
    )
    return <rect x={left} y={top} width={w} height={h} rx={radius} />
  }
  const [left, right, top, bottom] = ['left', 'right', 'top', 'bottom'].map((side) =>
    n(`unusable_${side}`),
  )
  const bleed = n('bleed')
  return (
    <g data-fortune-pizza-guides="true" pointerEvents="none" fill="none" strokeWidth={0.25}>
      <defs>
        <clipPath id={`${id}-cut`}>{contour()}</clipPath>
        <clipPath id={`${id}-bands`}>
          <path
            clipRule="evenodd"
            d={`M0 0H${width}V${height}H0Z M${left} ${top}H${width - right}V${height - bottom}H${left}Z`}
          />
        </clipPath>
        <pattern id={`${id}-hatch`} width="3" height="3" patternUnits="userSpaceOnUse">
          <path d="M-1 1L1 -1 M0 3L3 0 M2 4L4 2" stroke="#e6b800" strokeWidth={0.18} />
        </pattern>
      </defs>
      <g clipPath={`url(#${id}-cut)`}>
        <g clipPath={`url(#${id}-bands)`}>
          <rect width={width} height={height} fill={`url(#${id}-hatch)`} />
        </g>
        <g stroke="#e6b800" strokeDasharray="2 1" strokeWidth={0.3}>
          {left > 0 && <line x1={left} x2={left} y1={top} y2={height - bottom} />}
          {right > 0 && (
            <line x1={width - right} x2={width - right} y1={top} y2={height - bottom} />
          )}
          {top > 0 && <line x1={left} x2={width - right} y1={top} y2={top} />}
          {bottom > 0 && (
            <line x1={left} x2={width - right} y1={height - bottom} y2={height - bottom} />
          )}
        </g>
        <g stroke="#183d36" strokeDasharray="2 1">
          {contour(n('safety_left'), n('safety_right'), n('safety_top'), n('safety_bottom'))}
        </g>
      </g>
      <g stroke="#f06e50">{contour()}</g>
      {bleed > 0 && (
        <g stroke="#3265c9" strokeDasharray="2 1">
          {contour(-bleed, -bleed, -bleed, -bleed)}
        </g>
      )}
    </g>
  )
}

function FortuneBarcode({ item, value }: { item: Repiquage; value: string }) {
  const ref = useRef<SVGSVGElement>(null)
  const [valid, setValid] = useState(false)
  const label = barcodeCaption(value, item.rendering)
  const captionFontSize = useMemo(() => {
    const context = document.createElement('canvas').getContext('2d')
    const size = (8 * 25.4) / 72
    if (!context || !label) return size
    context.font = '8px Arial'
    const width = (context.measureText(label).width * 25.4) / 72
    return size * Math.min(1, (item.barcode_width - 2) / width)
  }, [label, item.barcode_width])
  useEffect(() => {
    const svg = ref.current
    if (!svg) return
    setValid(false)
    if (barcodeError(value, item.rendering)) {
      svg.replaceChildren()
      return
    }
    let disposed = false
    void import('jsbarcode')
      .then(({ default: JsBarcode }) => {
        if (disposed) return
        try {
          JsBarcode(svg, value, {
            format: item.rendering === 'ean13' ? 'EAN13' : 'CODE128',
            width: 1,
            height: 1,
            displayValue: false,
            flat: true,
            margin: 0,
            marginTop: 0,
            marginBottom: 0,
            marginLeft: 10,
            marginRight: 10,
            background: '#ffffff',
            lineColor: item.color,
          })
          svg.setAttribute(
            'viewBox',
            `0 0 ${parseFloat(svg.getAttribute('width')!)} ${parseFloat(svg.getAttribute('height')!)}`,
          )
          svg.setAttribute('width', String(item.barcode_width))
          svg.setAttribute('height', String(item.barcode_height))
          setValid(true)
        } catch {
          svg.replaceChildren()
        }
      })
      .catch(() => {
        if (!disposed) svg.replaceChildren()
      })
    return () => {
      disposed = true
    }
  }, [item.rendering, item.color, item.barcode_width, item.barcode_height, value])
  const shift = { left: 0, center: -0.5, right: -1 }[item.align] * item.barcode_width
  return (
    <g transform={`translate(${shift} ${-item.barcode_height - barcodeCaptionHeight})`}>
      <rect
        width={item.barcode_width}
        height={item.barcode_height + barcodeCaptionHeight}
        fill="#ffffff"
        pointerEvents="none"
      />
      <svg
        ref={ref}
        preserveAspectRatio="none"
        aria-label={`Code-barres ${item.rendering === 'ean13' ? 'EAN-13' : 'Code 128'}`}
      />
      {valid && (
        <text
          x={item.barcode_width / 2}
          y={item.barcode_height + barcodeCaptionHeight - (8 * 25.4) / 72 / 4}
          textAnchor="middle"
          fontFamily="Arial, sans-serif"
          fontWeight="normal"
          fontSize={captionFontSize}
          fill={item.color}
          pointerEvents="none"
        >
          {label}
        </text>
      )}
      {!valid && barcodeError(value, item.rendering) && (
        <text y={item.barcode_height} fontSize="2.5" fill="#b42318">
          Code-barres invalide
        </text>
      )}
    </g>
  )
}

export function FortunePreview({
  items,
  width,
  height,
  bleed,
  template,
  serial,
  data,
  file,
  disabled,
  onChange,
}: {
  items: Repiquage[]
  width: number
  height: number
  bleed: number
  template: PizzaValues | null
  serial: string
  data: CsvData | null
  file?: File
  disabled: boolean
  onChange: (items: Repiquage[]) => void
}) {
  const trimId = useId()
  const [background, setBackground] = useState<{ url: string; bleed: number } | null>(null)
  const [error, setError] = useState('')
  const svg = useRef<SVGSVGElement>(null)
  const moving = useRef<{ index: number; dx: number; dy: number } | null>(null)
  useEffect(() => {
    setBackground(null)
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
        const hasBleed = bleed > 0 && matches(width + 2 * bleed, height + 2 * bleed)
        if (!hasBleed && !matches(width, height)) {
          throw new Error('Unsupported artwork frame')
        }
        if (!disposed) setBackground({ url: canvas.toDataURL(), bleed: hasBleed ? bleed : 0 })
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
  const guideBleed = template ? bleed : 0
  const point = (e: React.PointerEvent) => {
    const rect = svg.current!.getBoundingClientRect()
    return {
      x: ((e.clientX - rect.left) / rect.width) * (width + 2 * guideBleed) - guideBleed,
      y: ((e.clientY - rect.top) / rect.height) * (height + 2 * guideBleed) - guideBleed,
    }
  }
  return (
    <div className="fortune-preview">
      <h2>Placez vos repiquages</h2>
      <p>
        Glissez un repiquage pour le déplacer. X et Y repèrent son point d’alignement depuis le coin
        supérieur gauche.
      </p>
      {error && <p role="alert">{error}</p>}
      <svg
        ref={svg}
        viewBox={`${-guideBleed} ${-guideBleed} ${width + 2 * guideBleed} ${height + 2 * guideBleed}`}
        className="fortune-sheet"
        aria-label="Placement des repiquages sur le support"
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
        <rect
          x={-guideBleed}
          y={-guideBleed}
          width={width + 2 * guideBleed}
          height={height + 2 * guideBleed}
          fill="white"
        />
        {background && (
          <image
            href={background.url}
            x={-background.bleed}
            y={-background.bleed}
            width={width + 2 * background.bleed}
            height={height + 2 * background.bleed}
            preserveAspectRatio="none"
          />
        )}
        {template && <FortunePizzaGuides template={template} />}
        <defs>
          <clipPath id={trimId}>
            <rect width={width} height={height} />
          </clipPath>
        </defs>
        <g clipPath={`url(#${trimId})`}>
          {items.map((item, i) => (
            <g
              key={i}
              transform={`translate(${item.x} ${item.y}) rotate(${item.rotation})`}
              className="fortune-draggable"
              aria-label={`Déplacer le repiquage ${i + 1}`}
              onPointerDown={(e) => {
                if (disabled) return
                e.preventDefault()
                const p = point(e)
                moving.current = { index: i, dx: p.x - item.x, dy: p.y - item.y }
                svg.current!.setPointerCapture(e.pointerId)
              }}
            >
              {item.rendering === 'text' ? (
                <text
                  fontFamily={fonts.find(([value]) => value === item.font)?.[2]}
                  fontSize={(item.size * 25.4) / 72}
                  fill={item.color}
                  textAnchor={
                    ({ left: 'start', center: 'middle', right: 'end' } as const)[item.align]
                  }
                >
                  {repiquageValue(item, serial, data)
                    .split('\n')
                    .map((line, n) => (
                      <tspan key={n} x="0" dy={n === 0 ? 0 : ((item.size * 25.4) / 72) * 1.2}>
                        {line || '\u00a0'}
                      </tspan>
                    ))}
                </text>
              ) : (
                <FortuneBarcode item={item} value={repiquageValue(item, serial, data)} />
              )}
            </g>
          ))}
        </g>
      </svg>
      <p>
        {width} × {height} mm finis · Premier exemplaire · Les coordonnées des repiquages restent
        relatives au format fini.{' '}
        {template && 'Repères Pizza : coupe, sécurité, zones inexploitables et fond perdu.'}
      </p>
    </div>
  )
}

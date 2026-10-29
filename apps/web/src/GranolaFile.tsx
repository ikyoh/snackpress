import { useEffect, useState } from 'react'
import { getDocument } from 'pdfjs-dist'
import './granola.css'
import type { components } from '../../../packages/api-client/schema'

export type GranolaItem = {
  quantity: number | ''
  page: number | ''
  image_width: number | ''
  shape: 'auto' | 'rectangle'
}
export const granolaDefaults: GranolaItem = { quantity: 1, page: 1, image_width: 85, shape: 'auto' }
const format = (value: number) => value.toLocaleString('fr-FR', { maximumFractionDigits: 2 })

export function GranolaFile({
  file,
  index,
  value,
  outline,
  onChange,
}: {
  file: File
  index: number
  value: GranolaItem
  outline?: components['schemas']['DetectedShape']
  onChange: (value: GranolaItem) => void
}) {
  const isPdf = file.type === 'application/pdf' || /\.pdf$/i.test(file.name)
  const [info, setInfo] = useState<{ width: number; height: number; pages: number } | null>(null)
  const [pageCount, setPageCount] = useState<number | null>(null)
  const [error, setError] = useState('')
  useEffect(() => setPageCount(null), [file])
  useEffect(() => {
    let disposed = false
    let release: (() => void) | undefined
    setInfo(null)
    setError('')
    void (async () => {
      try {
        if (isPdf) {
          const data = await file.arrayBuffer()
          if (disposed) return
          const task = getDocument({ data })
          release = () => {
            void task.destroy().catch(() => {})
          }
          const pdf = await task.promise
          if (!disposed) setPageCount(pdf.numPages)
          const page = await pdf.getPage(Number(value.page) || 1)
          const viewport = page.getViewport({ scale: 1 })
          if (!disposed)
            setInfo({
              width: (viewport.width * 25.4) / 72,
              height: (viewport.height * 25.4) / 72,
              pages: pdf.numPages,
            })
        } else {
          const url = URL.createObjectURL(file)
          const image = new Image()
          release = () => {
            image.onload = null
            image.onerror = null
            URL.revokeObjectURL(url)
          }
          image.onload = () => {
            if (!disposed)
              setInfo({ width: image.naturalWidth, height: image.naturalHeight, pages: 1 })
          }
          image.onerror = () => {
            if (!disposed) setError('Image illisible. Utilisez un PNG ou JPEG valide.')
          }
          image.src = url
        }
      } catch {
        if (!disposed)
          setError('Page PDF illisible. Vérifiez le numéro de page et la protection du fichier.')
      }
    })()
    return () => {
      disposed = true
      release?.()
    }
  }, [file, isPdf, value.page])
  const change = (key: keyof GranolaItem, input: string) =>
    onChange({ ...value, [key]: input === '' ? '' : Number(input) })
  const width = isPdf ? info?.width : Number(value.image_width)
  const height = isPdf ? info?.height : info && width ? (width * info.height) / info.width : null
  const dpi = !isPdf && info && width ? (info.width / width) * 25.4 : null
  return (
    <div className="granola-file-settings">
      <div className="granola-file-fields">
        <label className="field">
          <span>Exemplaires</span>
          <input
            type="number"
            required
            min="1"
            max="2000"
            step="1"
            aria-label={`Exemplaires du fichier ${index + 1}`}
            value={value.quantity}
            onChange={(e) => change('quantity', e.target.value)}
          />
        </label>
        {isPdf ? (
          <label className="field">
            <span>Page à imposer</span>
            <input
              type="number"
              required
              min="1"
              max={pageCount ?? 80}
              disabled={pageCount === null || pageCount === 1}
              title={pageCount === 1 ? 'Ce PDF contient une seule page.' : undefined}
              step="1"
              aria-label={`Page du fichier ${index + 1}`}
              value={value.page}
              onChange={(e) => change('page', e.target.value)}
            />
          </label>
        ) : (
          <label className="field">
            <span>Largeur imprimée</span>
            <span className="input-wrap">
              <input
                type="number"
                required
                min="0.1"
                max="1200"
                step="any"
                aria-label={`Largeur de l’image ${index + 1}`}
                value={value.image_width}
                onChange={(e) => change('image_width', e.target.value)}
              />
              <span>mm</span>
            </span>
          </label>
        )}
        <label className="field granola-shape-choice">
          <span>Contour de la pose</span>
          <select
            aria-label={`Contour du fichier ${index + 1}`}
            value={value.shape ?? 'auto'}
            onChange={(event) =>
              onChange({ ...value, shape: event.target.value as GranolaItem['shape'] })
            }
          >
            <option value="auto">Automatique · d’après le contenu</option>
            <option value="rectangle">Conserver le rectangle du fichier</option>
          </select>
        </label>
      </div>
      {outline && value.shape !== 'rectangle' && (
        <figure className="granola-detected-shape">
          <svg
            viewBox={`0 0 ${outline.width} ${outline.height}`}
            role="img"
            aria-label={`Contour détecté du fichier ${index + 1}`}
          >
            {outline.polygons.map((polygon, i) => (
              <polygon
                key={i}
                points={polygon.map(([x, y]) => `${x},${outline.height - y}`).join(' ')}
                fill="#a44fb4"
                stroke="#593064"
                strokeWidth="1"
                vectorEffect="non-scaling-stroke"
              />
            ))}
          </svg>
          <figcaption>
            <strong>
              {outline.kind === 'triangle'
                ? 'Triangle détecté'
                : outline.kind === 'rectangle'
                  ? 'Rectangle détecté'
                  : 'Contour détecté'}
            </strong>
            <span>
              {format(outline.width)} × {format(outline.height)} mm
            </span>
          </figcaption>
        </figure>
      )}
      {(value.shape ?? 'auto') === 'auto' && (
        <p className="field-hint">
          Le fond blanc ou transparent extérieur est masqué pour imbriquer les formes. Contrôlez le
          contour détecté ; l’export PDF conserve les objets natifs.
        </p>
      )}
      <p className="field-hint" aria-live="polite">
        {error ||
          (info && width && height
            ? `${format(width)} × ${format(height)} mm · ${isPdf ? `taille réelle · ${info.pages} page(s)` : `proportions conservées · ${Math.round(dpi!)} ppp`}`
            : 'Lecture du format…')}
      </p>
      {dpi !== null && dpi < 150 && (
        <p className="field-hint">
          Résolution faible : réduisez la largeur pour une impression plus nette.
        </p>
      )}
    </div>
  )
}

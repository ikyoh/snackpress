import { useEffect, useState } from 'react'
import { Crop, Undo2 } from 'lucide-react'
import { Button } from './components/ui/button'

const format = (value: number) => value.toLocaleString('fr-FR', { maximumFractionDigits: 2 })
export const granolaGeometryMetric = (key: string) =>
  /^(Largeur|Hauteur) (avec|sans) marge \(mm\)$/.test(key)

export function granolaSheetValues(
  values: Record<string, string | number>,
  metrics?: Record<string, string | number>,
) {
  if (!metrics || !['margin', 'poses'].includes(String(values.crop))) return values
  const suffix = values.crop === 'poses' ? 'sans' : 'avec'
  const width = Number(metrics[`Largeur ${suffix} marge (mm)`])
  const height = Number(metrics[`Hauteur ${suffix} marge (mm)`])
  return width > 0 && height > 0 ? { ...values, sheet_width: width, sheet_height: height } : values
}

export function GranolaCrop({
  metrics,
  mode,
  optimization,
  sheetWidth,
  sheetHeight,
  margin,
  pending,
  disabled,
  onChange,
}: {
  metrics: Record<string, string | number>
  mode: string
  optimization: string
  sheetWidth: number
  sheetHeight: number
  margin: number
  pending: boolean
  disabled: boolean
  onChange: (mode: string) => void
}) {
  const [keepMargin, setKeepMargin] = useState(mode !== 'poses')
  useEffect(() => {
    if (mode !== 'none') setKeepMargin(mode === 'margin')
  }, [mode])
  const suffix = keepMargin ? 'avec' : 'sans'
  const width = Number(metrics[`Largeur ${suffix} marge (mm)`])
  const height = Number(metrics[`Hauteur ${suffix} marge (mm)`])
  if (!(width > 0 && height > 0 && sheetWidth > 0 && sheetHeight > 0)) return null
  const saving = Math.max(0, 100 * (1 - (width * height) / (sheetWidth * sheetHeight)))
  const applied = mode !== 'none'
  const alongWidth = optimization !== 'area'
  return (
    <section className="granola-crop" aria-label="Recadrage de la planche" hidden={pending}>
      <h2>
        <Crop size={19} aria-hidden="true" />
        {alongWidth ? 'Optimisé sur la largeur' : 'Format au plus près'}
      </h2>
      <p className="granola-crop-size" aria-live="polite">
        <strong>
          {format(width)} × {format(height)} mm
        </strong>
        <span>
          {format(saving)} % de surface en moins{applied ? ' · recadrage appliqué' : ''}
        </span>
      </p>
      <p>
        {alongWidth
          ? `Largeur conservée : ${format(sheetWidth)} mm. La hauteur est réduite autour des poses, sans changer leur taille.`
          : 'Le plus petit rectangle autour de cette disposition, sans changer la taille des poses.'}
        {Number(metrics.Planches) > 1 && ' Un même format est conservé pour toutes les planches.'}
      </p>
      {applied && (
        <p>
          Format initial : {format(sheetWidth)} × {format(sheetHeight)} mm.
        </p>
      )}
      <label className="granola-crop-margin">
        <input
          type="checkbox"
          checked={keepMargin}
          disabled={disabled}
          onChange={(event) => {
            const keep = event.target.checked
            setKeepMargin(keep)
            if (applied) onChange(keep ? 'margin' : 'poses')
          }}
        />
        <span>Conserver la marge extérieure ({format(margin)} mm)</span>
      </label>
      {applied ? (
        <Button
          type="button"
          variant="outline"
          disabled={disabled}
          onClick={() => onChange('none')}
        >
          <Undo2 size={16} /> Rétablir le format initial
        </Button>
      ) : saving > 0.01 ? (
        <Button
          type="button"
          disabled={disabled}
          onClick={() => onChange(keepMargin ? 'margin' : 'poses')}
        >
          <Crop size={16} /> Appliquer le recadrage
        </Button>
      ) : (
        <p>La disposition utilise déjà tout le format disponible.</p>
      )}
    </section>
  )
}

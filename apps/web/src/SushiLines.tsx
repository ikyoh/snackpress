import { useId } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { Button } from './components/ui/button'

type Line = {
  kind: 'cut' | 'crease'
  axis: 'horizontal' | 'vertical'
  position: number | ''
}

function readLines(value: unknown, legacy: unknown): Line[] {
  let lines = value
  if (typeof lines === 'string') {
    try {
      lines = JSON.parse(lines)
    } catch {
      lines = []
    }
  }
  const previous: Line[] =
    typeof legacy === 'string'
      ? legacy
          .split(',')
          .filter((x) => x.trim())
          .map((x) => ({
            kind: 'crease',
            axis: 'vertical',
            position: Number(x.trim()),
          }))
      : []
  return [...previous, ...(Array.isArray(lines) ? lines : [])]
}

export function SushiLines({
  value,
  legacyCreases,
  width,
  height,
  onChange,
}: {
  value: unknown
  legacyCreases?: unknown
  width: number
  height: number
  onChange: (value: string) => void
}) {
  const id = useId()
  const lines = readLines(value, legacyCreases)
  const update = (next: Line[]) => onChange(JSON.stringify(next))
  function patch(index: number, change: Partial<Line>) {
    update(lines.map((line, i) => (i === index ? { ...line, ...change } : line)))
  }
  return (
    <div className="sushi-lines" role="group" aria-label="Tracés de coupe et de rainage">
      <p className="field-hint" id={`${id}-help`}>
        Positions depuis le bord gauche pour un tracé vertical, depuis le haut pour un horizontal.
        Les tracés traversent le format fini, sans le fond perdu.
      </p>
      {!lines.length && <p className="sushi-lines-empty">Aucun tracé ajouté.</p>}
      {lines.map((line, index) => (
        <fieldset className="sushi-line" key={index} aria-describedby={`${id}-help`}>
          <legend>Tracé {index + 1}</legend>
          <div className="sushi-line-fields">
            <label className="field tool-field">
              <span>Type</span>
              <select
                aria-label={`Type du tracé ${index + 1}`}
                value={line.kind}
                onChange={(e) => patch(index, { kind: e.target.value as Line['kind'] })}
              >
                <option value="crease">Rainage</option>
                <option value="cut">Coupe</option>
              </select>
            </label>
            <label className="field tool-field">
              <span>Orientation</span>
              <select
                aria-label={`Orientation du tracé ${index + 1}`}
                value={line.axis}
                onChange={(e) => patch(index, { axis: e.target.value as Line['axis'] })}
              >
                <option value="vertical">Vertical</option>
                <option value="horizontal">Horizontal</option>
              </select>
            </label>
            <label className="field tool-field sushi-line-position">
              <span>Position depuis {line.axis === 'vertical' ? 'la gauche' : 'le haut'}</span>
              <span className="input-wrap">
                <input
                  aria-label={`Position du tracé ${index + 1}`}
                  type="number"
                  required
                  min={0}
                  max={line.axis === 'vertical' ? width : height}
                  step="any"
                  value={line.position}
                  onChange={(e) =>
                    patch(index, { position: e.target.value === '' ? '' : Number(e.target.value) })
                  }
                />
                <span>mm</span>
              </span>
            </label>
            <Button
              type="button"
              variant="ghost"
              className="sushi-line-remove"
              aria-label={`Supprimer le tracé ${index + 1}`}
              onClick={() => update(lines.filter((_, i) => i !== index))}
            >
              <Trash2 size={18} aria-hidden="true" />
            </Button>
          </div>
        </fieldset>
      ))}
      <Button
        type="button"
        variant="outline"
        onClick={() => update([...lines, { kind: 'crease', axis: 'vertical', position: 0 }])}
      >
        <Plus size={18} aria-hidden="true" /> Ajouter un tracé
      </Button>
    </div>
  )
}

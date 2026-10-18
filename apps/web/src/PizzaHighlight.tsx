import { useId } from 'react'
import type { PizzaValues } from './pizza'

export function pizzaFocusLabel(field: string, values: PizzaValues) {
  const labels: Record<string, string> = {
    shape: 'Forme de coupe',
    width: values.shape === 'circle' ? 'Diamètre fini' : 'Largeur finie',
    height: 'Hauteur finie',
    corner_radius: 'Coins arrondis',
    bleed: 'Fond perdu',
  }
  const [prefix, side] = field.split('_')
  if (prefix === 'safety' || prefix === 'unusable') {
    const sides: Record<string, string> = {
      top: 'haut',
      bottom: 'bas',
      left: 'gauche',
      right: 'droite',
      all: 'tous les côtés',
    }
    return `${prefix === 'safety' ? 'Sécurité' : 'Zone inexploitable'} — ${sides[side]}`
  }
  return (
    labels[field] ??
    (field.startsWith('width_') ? labels.width : field.startsWith('height_') ? labels.height : '')
  )
}

// This reading aid follows the geometry of the PDF. It never enters the exported file.
export function PizzaHighlight({ values, field }: { values: PizzaValues; field: string }) {
  const id = useId()
  const n = (key: string) =>
    Number(values[key] ?? (key.startsWith('safety_') ? (values.safety ?? 4) : 0))
  const width = n('width')
  const height = values.shape === 'circle' ? width : n('height')
  const bleed = n('bleed')
  if (!(width > 0 && height > 0)) return null
  const contour = (left = 0, right = 0, top = 0, bottom = 0) => {
    const x = bleed + left,
      y = bleed + top
    const w = width - left - right,
      h = height - top - bottom
    if (values.shape === 'circle' || values.shape === 'ellipse')
      return <ellipse cx={x + w / 2} cy={y + h / 2} rx={w / 2} ry={h / 2} />
    const radius = Math.min(
      Math.max(0, n('corner_radius') - Math.max(left, right, top, bottom)),
      w / 2,
      h / 2,
    )
    return <rect x={x} y={y} width={w} height={h} rx={radius} />
  }
  const [prefix, side] = field.split('_')
  const isInset = prefix === 'safety' || prefix === 'unusable'
  const insets = isInset
    ? ['left', 'right', 'top', 'bottom'].map((side) => n(`${prefix}_${side}`))
    : [0, 0, 0, 0]
  const [left, right, top, bottom] = insets
  const bands = {
    top: [bleed, bleed, width, top],
    bottom: [bleed, bleed + height - bottom, width, bottom],
    left: [bleed, bleed, left, height],
    right: [bleed + width - right, bleed, right, height],
  }
  return (
    <svg
      className="pizza-highlight"
      viewBox={`0 0 ${width + 2 * bleed} ${height + 2 * bleed}`}
      aria-hidden="true"
      data-pizza-highlight={field}
    >
      <defs>
        <clipPath id={id}>{contour()}</clipPath>
        <mask
          id={`${id}-bleed`}
          maskUnits="userSpaceOnUse"
          x="0"
          y="0"
          width={width + 2 * bleed}
          height={height + 2 * bleed}
        >
          <g fill="white">{contour(-bleed, -bleed, -bleed, -bleed)}</g>
          <g fill="black">{contour()}</g>
        </mask>
      </defs>
      <g className="pizza-highlight-line">
        {field === 'bleed' ? (
          <>
            <rect
              width={width + 2 * bleed}
              height={height + 2 * bleed}
              fill="currentColor"
              stroke="none"
              opacity="0.16"
              mask={`url(#${id}-bleed)`}
            />
            {contour()}
          </>
        ) : isInset ? (
          <>
            <g clipPath={`url(#${id})`} fill="currentColor" fillOpacity="0.16" stroke="none">
              {Object.entries(bands)
                .filter(([key]) => side === 'all' || key === side)
                .map(([key, [x, y, w, h]]) => (
                  <rect key={key} x={x} y={y} width={w} height={h} />
                ))}
            </g>
            <g clipPath={`url(#${id})`}>
              {prefix === 'safety' ? (
                contour(left, right, top, bottom)
              ) : (
                <>
                  {(side === 'all' || side === 'top') && top > 0 && (
                    <line
                      x1={bleed + left}
                      x2={bleed + width - right}
                      y1={bleed + top}
                      y2={bleed + top}
                    />
                  )}
                  {(side === 'all' || side === 'bottom') && bottom > 0 && (
                    <line
                      x1={bleed + left}
                      x2={bleed + width - right}
                      y1={bleed + height - bottom}
                      y2={bleed + height - bottom}
                    />
                  )}
                  {(side === 'all' || side === 'left') && left > 0 && (
                    <line
                      x1={bleed + left}
                      x2={bleed + left}
                      y1={bleed + top}
                      y2={bleed + height - bottom}
                    />
                  )}
                  {(side === 'all' || side === 'right') && right > 0 && (
                    <line
                      x1={bleed + width - right}
                      x2={bleed + width - right}
                      y1={bleed + top}
                      y2={bleed + height - bottom}
                    />
                  )}
                </>
              )}
            </g>
          </>
        ) : (
          contour()
        )}
      </g>
    </svg>
  )
}

import { useEffect, useRef, useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import { FileText, LoaderCircle, Maximize, Minimize, Scan, ZoomIn, ZoomOut } from 'lucide-react'
import type { PDFDocumentProxy, RenderTask } from 'pdfjs-dist'
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import type { Job } from './api'
GlobalWorkerOptions.workerSrc = workerUrl

export function PdfFaceSwitch({
  page,
  onChange,
}: {
  page: number
  onChange: (page: number) => void
}) {
  return (
    <div className="pdf-face-switch" role="group" aria-label="Face du plan de pliage">
      {['Recto', 'Verso'].map((face, index) => (
        <button
          key={face}
          type="button"
          aria-pressed={page === index + 1}
          onClick={() => onChange(index + 1)}
        >
          {face}
        </button>
      ))}
    </div>
  )
}

export function useArtwork(job: Job | null) {
  const [images, setImages] = useState<string[]>([])
  const [error, setError] = useState('')
  useEffect(() => {
    setImages([])
    setError('')
    if (!job) return
    let disposed = false
    const task = getDocument(`/api/jobs/${job.id}/source`)
    void (async () => {
      try {
        const pdf = await task.promise
        const result: string[] = []
        for (let i = 0; i < job.document.pages.length; i++) {
          const page = await pdf.getPage(i + 1)
          const natural = page.getViewport({ scale: 1 })
          const viewport = page.getViewport({
            scale: Math.min(2, 1000 / Math.max(natural.width, natural.height)),
          })
          const canvas = document.createElement('canvas')
          canvas.width = viewport.width
          canvas.height = viewport.height
          await page.render({ canvas, viewport }).promise
          const [x, y, r, t] = job.document.pages[i].trim
          const rect = viewport.convertToViewportRectangle([x, y, r, t])
          const clipped = document.createElement('canvas')
          clipped.width = Math.max(1, Math.round(Math.abs(rect[2] - rect[0])))
          clipped.height = Math.max(1, Math.round(Math.abs(rect[3] - rect[1])))
          clipped
            .getContext('2d')!
            .drawImage(
              canvas,
              Math.min(rect[0], rect[2]),
              Math.min(rect[1], rect[3]),
              clipped.width,
              clipped.height,
              0,
              0,
              clipped.width,
              clipped.height,
            )
          result.push(clipped.toDataURL())
        }
        if (!disposed) setImages(result)
      } catch {
        if (!disposed)
          setError('L’aperçu du fichier source est indisponible. Essayez de réimporter le PDF.')
      }
    })()
    return () => {
      disposed = true
      void task.destroy()
    }
  }, [job])
  return { images, error }
}

export function PdfPreview({
  url,
  page: number,
  retainPrevious = false,
  scrollable = true,
  overlay,
}: {
  url: string
  page: number
  retainPrevious?: boolean
  scrollable?: boolean
  overlay?: ReactNode
}) {
  const viewer = useRef<HTMLDivElement>(null)
  const stage = useRef<HTMLDivElement>(null)
  const ref = useRef<HTMLCanvasElement>(null)
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null)
  const [bounds, setBounds] = useState({ width: 0, height: 0 })
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 })
  const [zoom, setZoom] = useState(1)
  const [ready, setReady] = useState(false)
  const [hasPainted, setHasPainted] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [error, setError] = useState('')
  const [fullscreenError, setFullscreenError] = useState('')

  useEffect(() => {
    const element = stage.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => {
      setBounds({ width: entry.contentRect.width, height: entry.contentRect.height })
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const update = () => setExpanded(document.fullscreenElement === viewer.current)
    document.addEventListener('fullscreenchange', update)
    return () => document.removeEventListener('fullscreenchange', update)
  }, [])

  useEffect(() => {
    setError('')
    setPdf(null)
    setReady(false)
    if (!retainPrevious) {
      setZoom(1)
      setHasPainted(false)
    }
    const task = getDocument(url)
    let disposed = false
    void task.promise
      .then((document) => {
        if (!disposed) setPdf(document)
      })
      .catch(() => {
        if (!disposed)
          setError(
            'Impossible d’afficher le PDF. Téléchargez-le pour l’ouvrir dans votre lecteur PDF.',
          )
      })
    return () => {
      disposed = true
      void task.destroy()
    }
  }, [url, retainPrevious])

  useEffect(() => {
    if (!pdf || !bounds.width || !bounds.height) return
    let disposed = false
    let render: RenderTask | undefined
    setReady(false)
    setError('')
    void (async () => {
      try {
        const page = await pdf.getPage(number)
        if (disposed) return
        const natural = page.getViewport({ scale: 1 })
        const fit = Math.min(
          (bounds.width - 48) / natural.width,
          (bounds.height - 48) / natural.height,
        )
        const scale = Math.max(scrollable || expanded ? 0.05 : 0.0001, fit) * zoom
        // Render offscreen: rapid page changes never paint over the active page.
        const canvas = document.createElement('canvas')
        const density = Math.min(Math.max(window.devicePixelRatio || 1, 2), 3)
        const renderScale = Math.min(
          scale * density,
          Math.sqrt(16_000_000 / (natural.width * natural.height)),
        )
        const viewport = page.getViewport({ scale: renderScale })
        canvas.width = Math.ceil(viewport.width)
        canvas.height = Math.ceil(viewport.height)
        render = page.render({ canvas, viewport })
        await render.promise
        if (disposed || !ref.current) return
        ref.current.width = canvas.width
        ref.current.height = canvas.height
        ref.current.getContext('2d')!.drawImage(canvas, 0, 0)
        ref.current.style.width = `${natural.width * scale}px`
        ref.current.style.height = `${natural.height * scale}px`
        setDimensions({ width: (natural.width * 25.4) / 72, height: (natural.height * 25.4) / 72 })
        setHasPainted(true)
        setReady(true)
      } catch {
        if (!disposed)
          setError(
            'Impossible d’afficher cette page. Téléchargez le PDF pour le contrôler dans votre lecteur.',
          )
      }
    })()
    return () => {
      disposed = true
      render?.cancel()
    }
  }, [pdf, number, bounds, zoom, scrollable, expanded])

  async function toggleFullscreen() {
    setFullscreenError('')
    try {
      if (document.fullscreenElement === viewer.current) await document.exitFullscreen()
      else await viewer.current?.requestFullscreen()
    } catch {
      setFullscreenError('Le plein écran est indisponible dans ce navigateur.')
    }
  }

  useEffect(() => {
    if (!scrollable && !expanded) setZoom(1)
  }, [scrollable, expanded])

  const mm = (value: number) => value.toLocaleString('fr-FR', { maximumFractionDigits: 1 })
  return (
    <div
      className={`pdf-viewer${scrollable ? '' : ' pdf-viewer-fit'}`}
      ref={viewer}
      style={
        {
          '--pdf-page-ratio': dimensions.width ? dimensions.height / dimensions.width : 1.414,
        } as CSSProperties
      }
    >
      <div className="pdf-viewer-toolbar" role="group" aria-label="Affichage du PDF">
        <span className="pdf-viewer-title">
          <FileText size={16} /> Aperçu PDF
        </span>
        <div className="pdf-viewer-actions">
          {(scrollable || expanded) && (
            <>
              <button
                type="button"
                aria-label="Réduire le zoom"
                title="Réduire le zoom"
                disabled={!pdf || zoom <= 0.5}
                onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))}
              >
                <ZoomOut size={17} />
              </button>
              <output className="pdf-zoom" aria-label="Zoom de l’aperçu">
                {Math.round(zoom * 100)} %
              </output>
              <button
                type="button"
                aria-label="Agrandir le zoom"
                title="Agrandir le zoom"
                disabled={!pdf || zoom >= 3}
                onClick={() => setZoom((z) => Math.min(3, z + 0.25))}
              >
                <ZoomIn size={17} />
              </button>
              <span className="pdf-toolbar-separator" />
            </>
          )}
          <button
            type="button"
            aria-label="Ajuster à l’écran"
            title="Ajuster à l’écran"
            disabled={!pdf}
            onClick={() => setZoom(1)}
          >
            <Scan size={17} />
            <span className="pdf-fit-label">Ajuster</span>
          </button>
          <button
            type="button"
            aria-label={expanded ? 'Quitter le plein écran' : 'Afficher en plein écran'}
            title={expanded ? 'Quitter le plein écran' : 'Afficher en plein écran'}
            onClick={() => void toggleFullscreen()}
          >
            {expanded ? <Minimize size={17} /> : <Maximize size={17} />}
          </button>
        </div>
      </div>
      <div
        className="pdf-viewport"
        ref={stage}
        tabIndex={0}
        role="region"
        aria-label={
          scrollable || expanded
            ? 'Document PDF, zone de défilement'
            : 'Document PDF ajusté à l’écran'
        }
        aria-busy={!ready && !error}
      >
        <div className="pdf-paper-space">
          <div className="pdf-paper">
            <canvas
              className="pdf-canvas"
              ref={ref}
              data-ready={ready}
              aria-label={`Aperçu PDF, page ${number}`}
              role="img"
              style={{
                visibility:
                  (ready || (retainPrevious && hasPainted)) && !error ? 'visible' : 'hidden',
              }}
            />
            {ready && !error && overlay && <div className="pdf-overlay">{overlay}</div>}
          </div>
        </div>
        {error ? (
          <div className="pdf-viewer-state pdf-viewer-error" role="alert">
            <FileText size={28} />
            <p>{error}</p>
            <a href={url} download>
              Télécharger le PDF
            </a>
          </div>
        ) : (
          !ready && (
            <div
              className={retainPrevious && hasPainted ? 'pdf-viewer-refresh' : 'pdf-viewer-state'}
              role="status"
            >
              <LoaderCircle size={26} className="spin" />
              <p>Préparation de l’aperçu…</p>
            </div>
          )
        )}
      </div>
      <div className="pdf-viewer-footer">
        <span>
          Page {number}
          {pdf ? ` sur ${pdf.numPages}` : ''}
        </span>
        <span>
          {ready ? `${mm(dimensions.width)} × ${mm(dimensions.height)} mm` : 'Aperçu du document'}
        </span>
      </div>
      {fullscreenError && (
        <p className="pdf-fullscreen-error" role="status">
          {fullscreenError}
        </p>
      )}
    </div>
  )
}

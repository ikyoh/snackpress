import { useEffect, useRef, useState, type ReactNode } from 'react'
import { ChevronLeft, ChevronRight, LoaderCircle } from 'lucide-react'
import { ApiError, post, request } from './api'
import { PdfFaceSwitch, PdfPreview } from './PdfPreview'
import type { components } from '../../../packages/api-client/schema'

type Preview = components['schemas']['PreviewResult']
const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))
async function release(id: string) {
  // A disconnected worker needs a moment to terminate before its input can be deleted.
  for (let attempt = 0; attempt < 6; attempt++) {
    try {
      await request(`/api/tool-previews/${id}`, { method: 'DELETE', keepalive: true })
      return
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 409) return
      await pause(250)
    }
  }
}
export function useLivePreview({
  toolId,
  files,
  settings,
  available,
  paused = false,
  valid,
  sourceJobId = '',
}: {
  toolId: string
  files: File[]
  settings: unknown
  available: boolean
  paused?: boolean
  valid?: () => boolean
  sourceJobId?: string
}) {
  const [session, setSession] = useState('')
  const [preview, setPreview] = useState<Preview | null>(null)
  const [updating, setUpdating] = useState(false)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const [current, setCurrent] = useState('')
  const serialized = JSON.stringify(settings)
  const latest = useRef({ serialized, valid })
  latest.current = { serialized, valid }
  useEffect(() => {
    let disposed = false
    let id = ''
    setSession('')
    setPreview(null)
    setError('')
    setCurrent('')
    setUpdating(available)
    if (!available) return
    const data = new FormData()
    files.forEach((file) => data.append('files', file))
    if (sourceJobId) data.append('source_job_id', sourceJobId)
    // Let an import finish so its returned ID can always be released on unmount.
    void request<{ id: string }>(`/api/tools/${toolId}/previews`, { method: 'POST', body: data })
      .then((value) => {
        id = value.id
        if (disposed) void release(id)
        else setSession(id)
      })
      .catch((e) => {
        if (!disposed) {
          setError(e.message)
          setUpdating(false)
        }
      })
    const leaving = () => {
      if (id) void release(id)
    }
    window.addEventListener('pagehide', leaving)
    return () => {
      disposed = true
      window.removeEventListener('pagehide', leaving)
      if (id) void release(id)
    }
  }, [toolId, files, sourceJobId, available, retry])
  useEffect(() => {
    if (!session || !available || paused) {
      setUpdating(false)
      return
    }
    const controller = new AbortController()
    setUpdating(true)
    setError('')
    const timer = setTimeout(() => {
      if (latest.current.valid && !latest.current.valid()) {
        setError('Corrigez les réglages pour actualiser l’aperçu.')
        setUpdating(false)
        return
      }
      void (async () => {
        try {
          let value: Preview | undefined
          for (let attempt = 0; attempt < 8; attempt++) {
            if (controller.signal.aborted) return
            try {
              value = await request<Preview>(
                `/api/tool-previews/${session}/render`,
                post({ settings: JSON.parse(serialized) }, controller.signal),
              )
              break
            } catch (e) {
              if (e instanceof ApiError && e.status === 409 && attempt < 7) {
                await pause(250)
                continue
              }
              throw e
            }
          }
          if (value && !controller.signal.aborted && latest.current.serialized === serialized) {
            setPreview(value)
            setCurrent(serialized)
          }
        } catch (e) {
          if (!controller.signal.aborted) setError((e as Error).message)
        } finally {
          if (!controller.signal.aborted) setUpdating(false)
        }
      })()
    }, 500)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [session, serialized, available, paused])
  return {
    preview,
    updating,
    error,
    stale: !!preview && current !== serialized,
    retry: () => setRetry((n) => n + 1),
  }
}

export function LivePreview({
  state,
  pageNumber,
  onPageChange,
  scrollable = true,
  pdfOverlay,
  overlayLabel,
  overlayArtifact,
  faceArtifact,
}: {
  state: ReturnType<typeof useLivePreview>
  pageNumber?: number
  onPageChange?: (page: number) => void
  scrollable?: boolean
  pdfOverlay?: ReactNode
  overlayLabel?: string
  overlayArtifact?: string
  faceArtifact?: string
}) {
  const { preview, updating, error, stale } = state
  const [artifactName, setArtifactName] = useState('')
  const [page, setPage] = useState(1)
  const selected = preview?.artifacts.find((a) => a.name === artifactName) || preview?.artifacts[0]
  const showOverlay = !!pdfOverlay && selected?.name === overlayArtifact && !stale && !updating
  const currentPage = Math.min(pageNumber ?? page, selected?.pages || 1)
  const changePage = (next: number) => {
    setPage(next)
    onPageChange?.(next)
  }
  const generation = preview?.generation
  useEffect(() => {
    setPage(1)
  }, [artifactName])
  useEffect(() => {
    // Preserve the selected face while its folding plan is recalculated.
    if (selected?.name !== faceArtifact) setPage(1)
  }, [generation, selected?.name, faceArtifact])
  const url =
    preview && selected
      ? `/api/tool-previews/${preview.id}/${preview.generation}/files/${encodeURIComponent(selected.name)}`
      : ''
  return (
    <div className="live-preview" aria-label="Aperçu automatique" aria-busy={updating}>
      <div className="live-preview-status">
        <span role="status">
          {updating ? (
            <>
              <LoaderCircle size={16} className="spin" />
              Actualisation de l’aperçu…
            </>
          ) : preview ? (
            stale ? (
              'Aperçu précédent — réglages modifiés'
            ) : (
              'Aperçu à jour'
            )
          ) : (
            'Aperçu automatique après import'
          )}
        </span>
        <button type="button" className="text-button" onClick={state.retry} disabled={updating}>
          Actualiser l’aperçu
        </button>
      </div>
      {error && (
        <p className="live-preview-error" role="alert">
          {error} Le fichier final reste accessible avec le bouton de génération.
        </p>
      )}
      {selected && preview ? (
        <>
          <div className="artifact-toolbar">
            <label>
              <span className="sr-only">Document de l’aperçu automatique</span>
              <select
                aria-label="Document de l’aperçu automatique"
                value={selected.name}
                onChange={(e) => setArtifactName(e.target.value)}
              >
                {preview.artifacts.map((a) => (
                  <option key={a.name} value={a.name}>
                    {a.label}
                  </option>
                ))}
              </select>
            </label>
            {selected.name === faceArtifact && selected.pages === 2 ? (
              <PdfFaceSwitch page={currentPage} onChange={changePage} />
            ) : (
              (selected.pages || 1) > 1 && (
                <div className="page-navigation">
                  <button
                    type="button"
                    aria-label="Page précédente de l’aperçu"
                    disabled={currentPage <= 1}
                    onClick={() => changePage(currentPage - 1)}
                  >
                    <ChevronLeft size={16} />
                  </button>
                  <span>
                    {currentPage} / {selected.pages}
                  </span>
                  <button
                    type="button"
                    aria-label="Page suivante de l’aperçu"
                    disabled={currentPage >= (selected.pages || 1)}
                    onClick={() => changePage(currentPage + 1)}
                  >
                    <ChevronRight size={16} />
                  </button>
                </div>
              )
            )}
          </div>
          {showOverlay && overlayLabel && (
            <p className="pdf-overlay-label">Surlignage de lecture : {overlayLabel}</p>
          )}
          <div className="artifact-stage">
            {selected.media_type === 'application/pdf' ? (
              <PdfPreview
                url={url}
                page={currentPage}
                scrollable={scrollable}
                overlay={showOverlay ? pdfOverlay : undefined}
              />
            ) : (
              <img src={url} alt={selected.label} />
            )}
          </div>
          <p className="live-preview-note">{preview.notice}</p>
        </>
      ) : (
        <div className="live-preview-empty">
          <p>
            {updating
              ? 'Préparation du premier aperçu…'
              : 'Ajoutez les fichiers requis et ajustez les réglages. L’aperçu se mettra à jour automatiquement.'}
          </p>
        </div>
      )}
    </div>
  )
}

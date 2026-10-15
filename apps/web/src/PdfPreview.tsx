import { useEffect, useRef, useState } from 'react'
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import type { Job } from './api'
GlobalWorkerOptions.workerSrc = workerUrl

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

export function PdfPreview({ url, page: number }: { url: string; page: number }) {
  const ref = useRef<HTMLCanvasElement>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    setError('')
    setReady(false)
    const task = getDocument(url)
    let disposed = false
    void (async () => {
      try {
        const pdf = await task.promise
        const page = await pdf.getPage(number)
        const natural = page.getViewport({ scale: 1 })
        const viewport = page.getViewport({
          scale: Math.min(1.4, 1500 / Math.max(natural.width, natural.height)),
        })
        if (disposed || !ref.current) return
        ref.current.width = viewport.width
        ref.current.height = viewport.height
        await page.render({ canvas: ref.current, viewport }).promise
        if (!disposed) setReady(true)
      } catch {
        if (!disposed)
          setError(
            'Impossible d’afficher le PDF généré. Vous pouvez le télécharger et le contrôler dans votre lecteur PDF.',
          )
      }
    })()
    return () => {
      disposed = true
      void task.destroy()
    }
  }, [url, number])
  return error ? (
    <p role="alert">{error}</p>
  ) : (
    <div className="pdf-render">
      <canvas
        className="pdf-canvas"
        ref={ref}
        data-ready={ready}
        aria-busy={!ready}
        aria-label={`PDF imposé, page ${number}`}
        style={{ opacity: ready ? 1 : 0 }}
      />
      {!ready && (
        <p className="pdf-loading" role="status">
          Affichage du PDF…
        </p>
      )}
    </div>
  )
}

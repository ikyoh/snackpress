import { describe, expect, it, vi, afterEach } from 'vitest'
import { request } from './api'
afterEach(() => vi.unstubAllGlobals())
describe('erreurs API lisibles', () => {
  it('expose le message métier', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ detail: 'Aucune pose ne tient.' }), { status: 422 }),
        ),
    )
    await expect(request('/test')).rejects.toThrow('Aucune pose ne tient.')
  })
  it('présente les erreurs de validation structurées', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify({ detail: [{ msg: 'Value error, Fonds perdus superposés.' }] }),
            { status: 422 },
          ),
        ),
    )
    await expect(request('/test')).rejects.toThrow('Fonds perdus superposés.')
  })
})

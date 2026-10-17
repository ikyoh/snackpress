import type { components } from '../../../packages/api-client/schema'
export type Settings = components['schemas']['Settings']
export type Plan = components['schemas']['Plan']
export type Job = components['schemas']['JobResponse']
export const defaults: Settings = {
  schema_version: 1,
  sheet_width: 320,
  sheet_height: 450,
  margin: 10,
  trim_width: 85,
  trim_height: 55,
  bleed: 0,
  gap: 6,
  quantity: 250,
  rotation: 'auto',
  columns: null,
  rows: null,
  flip: 'long',
  crop_marks: true,
  confirm_trim: false,
}
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message)
  }
}
export async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (init?.method && !['GET', 'HEAD'].includes(init.method.toUpperCase())) {
    headers.set('X-Snackpress-Request', '1')
  }
  const response = await fetch(url, { ...init, headers, credentials: 'same-origin' })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const detail = body.detail
    if (response.status === 401 && url.startsWith('/api/configurations')) {
      window.dispatchEvent(new Event('snackpress-session-expired'))
    }
    throw new ApiError(
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((item: { msg: string }) => item.msg.replace('Value error, ', '')).join(' ')
          : 'Le service est indisponible. Vérifiez que l’API est démarrée.',
      response.status,
    )
  }
  if (response.status === 204) return undefined as T
  return response.json()
}
export const post = (data: unknown, signal?: AbortSignal): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data),
  signal,
})
export function readProfiles(): Record<string, Settings> {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem('snackpress-profiles') || '{}')
    if (!saved || typeof saved !== 'object' || Array.isArray(saved)) return {}
    return Object.fromEntries(
      Object.entries(saved).filter(
        ([name, settings]) =>
          name.trim() && settings && typeof settings === 'object' && !Array.isArray(settings),
      ),
    ) as Record<string, Settings>
  } catch {
    return {}
  }
}

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
export async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const detail = body.detail
    throw new Error(
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((item: { msg: string }) => item.msg.replace('Value error, ', '')).join(' ')
          : 'Le service est indisponible. Vérifiez que l’API est démarrée.',
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
    return JSON.parse(localStorage.getItem('snackpress-profiles') || '{}')
  } catch {
    return {}
  }
}

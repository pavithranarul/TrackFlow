import type { Page } from './types'

const ACCESS = 'trackflow.access'
const REFRESH = 'trackflow.refresh'

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS)
  },
  get refresh() {
    return localStorage.getItem(REFRESH)
  },
  set(access: string, refresh?: string) {
    localStorage.setItem(ACCESS, access)
    if (refresh) localStorage.setItem(REFRESH, refresh)
  },
  clear() {
    localStorage.removeItem(ACCESS)
    localStorage.removeItem(REFRESH)
  },
}

/** An error carrying the backend's field-level detail, which is always
 *  `{field: [message, ...]}` — see the API's documented error shape. */
export class ApiError extends Error {
  status: number
  fields: Record<string, string[]>

  constructor(status: number, body: unknown) {
    const fields = (
      body && typeof body === 'object' ? (body as Record<string, unknown>) : {}
    ) as Record<string, unknown>

    const normalised: Record<string, string[]> = {}
    for (const [key, value] of Object.entries(fields)) {
      normalised[key] = Array.isArray(value) ? value.map(String) : [String(value)]
    }

    super(ApiError.firstMessage(status, normalised))
    this.status = status
    this.fields = normalised
  }

  private static firstMessage(status: number, fields: Record<string, string[]>) {
    const first = Object.entries(fields)[0]
    if (first) {
      const [key, messages] = first
      return key === 'detail' || key === 'non_field_errors'
        ? messages[0]
        : `${key}: ${messages[0]}`
    }
    if (status === 401) return 'Your session has expired. Please sign in again.'
    if (status === 403) return 'You do not have permission to do that.'
    if (status === 404) return 'Not found.'
    return `Request failed (${status})`
  }
}

let refreshing: Promise<boolean> | null = null

/** Exchange the refresh token for a new pair. Concurrent 401s share one
 *  in-flight refresh rather than each firing their own. */
async function refreshAccessToken(): Promise<boolean> {
  if (!tokens.refresh) return false

  refreshing ??= (async () => {
    try {
      const response = await fetch('/api/auth/refresh/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh: tokens.refresh }),
      })
      if (!response.ok) return false

      const data = await response.json()
      tokens.set(data.access, data.refresh)
      return true
    } catch {
      return false
    } finally {
      refreshing = null
    }
  })()

  return refreshing
}

interface RequestOptions {
  method?: string
  body?: unknown
  /** Skip the auth header and the refresh dance (login, register). */
  anonymous?: boolean
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, anonymous = false } = options

  const send = async () => {
    const headers: Record<string, string> = {}
    if (body !== undefined) headers['Content-Type'] = 'application/json'
    if (!anonymous && tokens.access) {
      headers.Authorization = `Bearer ${tokens.access}`
    }

    return fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  }

  let response = await send()

  // One transparent retry after refreshing an expired access token.
  if (response.status === 401 && !anonymous && tokens.refresh) {
    if (await refreshAccessToken()) {
      response = await send()
    } else {
      tokens.clear()
      window.dispatchEvent(new Event('trackflow:signed-out'))
    }
  }

  if (response.status === 204) return undefined as T

  const payload = await response.json().catch(() => null)

  if (!response.ok) throw new ApiError(response.status, payload)

  return payload as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown, anonymous = false) =>
    request<T>(path, { method: 'POST', body, anonymous }),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: 'PATCH', body }),
  delete: (path: string) => request<void>(path, { method: 'DELETE' }),
}

/** Build a query string, dropping empty values and expanding arrays into
 *  repeated keys (which is how the backend's MultipleChoiceFilter reads them). */
export function qs(params: Record<string, unknown>): string {
  const search = new URLSearchParams()

  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    if (Array.isArray(value)) {
      for (const item of value) if (item !== '') search.append(key, String(item))
    } else {
      search.append(key, String(value))
    }
  }

  const encoded = search.toString()
  return encoded ? `?${encoded}` : ''
}

export type { Page }

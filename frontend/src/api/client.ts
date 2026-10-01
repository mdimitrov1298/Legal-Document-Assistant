import type { ApiErrorCode, ErrorDetails } from '@/api/types'

const DEFAULT_BASE_URL = '/api/v1'

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || DEFAULT_BASE_URL).replace(
  /\/+$/,
  '',
)

export class ApiError extends Error {
  readonly status: number
  readonly code: ApiErrorCode | (string & {})
  readonly requestId: string | null
  readonly details: ErrorDetails

  constructor(init: {
    status: number
    code: ApiError['code']
    message: string
    requestId?: string | null
    details?: ErrorDetails
  }) {
    super(init.message)
    this.name = 'ApiError'
    this.status = init.status
    this.code = init.code
    this.requestId = init.requestId ?? null
    this.details = init.details ?? null
  }
}

type Query = Record<string, string | number | boolean | undefined>

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  query?: Query
  /** Serialised as a JSON body. */
  json?: unknown
  /** Sent as multipart/form-data; the browser sets the boundary header. */
  form?: FormData
  signal?: AbortSignal
}

function buildUrl(path: string, query?: Query): string {
  const url = `${API_BASE_URL}${path}`
  if (!query) return url
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined) params.set(key, String(value))
  }
  const qs = params.toString()
  return qs ? `${url}?${qs}` : url
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function toDetails(value: unknown): ErrorDetails {
  if (value === null || value === undefined) return null
  return isRecord(value) ? value : { value }
}

async function errorFromResponse(res: Response): Promise<ApiError> {
  const headerId = res.headers.get('X-Request-ID')
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    // Non-JSON error body (e.g. a proxy page); fall back to the status line.
  }

  if (isRecord(body) && isRecord(body.error)) {
    const { code, message, details } = body.error
    return new ApiError({
      status: res.status,
      code: typeof code === 'string' ? code : 'http_error',
      message: typeof message === 'string' ? message : res.statusText,
      requestId: typeof body.request_id === 'string' ? body.request_id : headerId,
      details: toDetails(details),
    })
  }

  const detail = isRecord(body) ? body.detail : undefined
  return new ApiError({
    status: res.status,
    code: 'http_error',
    message: typeof detail === 'string' ? detail : res.statusText || `HTTP ${String(res.status)}`,
    requestId: headerId,
    details: detail === undefined || typeof detail === 'string' ? null : toDetails(detail),
  })
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', query, json, form, signal } = options
  const headers: Record<string, string> = { Accept: 'application/json' }
  let body: BodyInit | undefined
  if (form) {
    body = form
  } else if (json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(json)
  }

  let res: Response
  try {
    res = await fetch(buildUrl(path, query), { method, headers, body, signal })
  } catch (err) {
    if (isAbortError(err)) throw err
    throw new ApiError({
      status: 0,
      code: 'network_error',
      message: err instanceof Error ? err.message : 'Network error',
    })
  }

  if (!res.ok) throw await errorFromResponse(res)
  if (res.status === 204 || res.headers.get('Content-Length') === '0') {
    return undefined as T
  }
  return (await res.json()) as T
}

export function isApiError(err: unknown): err is ApiError {
  return err instanceof ApiError
}

/** Normalises anything thrown by the client or by UI code into an ApiError. */
export function toApiError(err: unknown): ApiError {
  if (err instanceof ApiError) return err
  return new ApiError({
    status: 0,
    code: 'http_error',
    message: err instanceof Error ? err.message : String(err),
  })
}

export function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === 'AbortError'
}

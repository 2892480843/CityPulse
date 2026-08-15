export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly requestId?: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

type ErrorPayload = {
  code?: string
  message?: string
  request_id?: string
}

type RequestOptions = {
  method: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  json?: unknown
  form?: FormData
  acceptedErrorStatuses?: readonly number[]
}

export function csrfToken(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)citypulse_csrf=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : null
}

async function parseError(response: Response): Promise<ApiError> {
  const body = (await response.json().catch(() => ({}))) as ErrorPayload
  return new ApiError(
    response.status,
    body.code ?? 'HTTP_ERROR',
    body.message ?? '服务暂时不可用',
    body.request_id,
  )
}

export async function requestJson<T>(
  path: string,
  { method, json, form, acceptedErrorStatuses = [] }: RequestOptions,
): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  let body: BodyInit | undefined
  if (json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(json)
  } else if (form !== undefined) {
    body = form
  }
  if (method !== 'GET') {
    const token = csrfToken()
    if (token) headers['X-CSRF-Token'] = token
  }

  const response = await fetch(path, { method, headers, body, credentials: 'include' })
  if (!response.ok && !acceptedErrorStatuses.includes(response.status)) {
    throw await parseError(response)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export async function getJson<T>(
  path: string,
  acceptedErrorStatuses: readonly number[] = [],
): Promise<T> {
  return requestJson<T>(path, { method: 'GET', acceptedErrorStatuses })
}

export async function postJson<T>(
  path: string,
  json?: unknown,
  acceptedErrorStatuses: readonly number[] = [],
): Promise<T> {
  return requestJson<T>(path, { method: 'POST', json, acceptedErrorStatuses })
}

export async function patchJson<T>(path: string, json?: unknown): Promise<T> {
  return requestJson<T>(path, { method: 'PATCH', json })
}

export async function postForm<T>(
  path: string,
  form: FormData,
  acceptedErrorStatuses: readonly number[] = [],
): Promise<T> {
  return requestJson<T>(path, { method: 'POST', form, acceptedErrorStatuses })
}

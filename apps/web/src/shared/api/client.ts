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

export async function getJson<T>(
  path: string,
  acceptedErrorStatuses: readonly number[] = [],
): Promise<T> {
  const response = await fetch(path, {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!response.ok && !acceptedErrorStatuses.includes(response.status)) {
    const body = (await response.json().catch(() => ({}))) as ErrorPayload
    throw new ApiError(
      response.status,
      body.code ?? 'HTTP_ERROR',
      body.message ?? '服务暂时不可用',
      body.request_id,
    )
  }
  return (await response.json()) as T
}

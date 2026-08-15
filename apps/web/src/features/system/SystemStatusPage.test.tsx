import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { SystemStatusPage } from './SystemStatusPage'
import * as systemApi from './api'

vi.mock('./api')

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <SystemStatusPage />
    </QueryClientProvider>,
  )
}

test('shows API and dependency health with text labels', async () => {
  vi.mocked(systemApi.getLiveness).mockResolvedValue({
    status: 'ok',
    service: 'citypulse-api',
    version: '0.1.0',
  })
  vi.mocked(systemApi.getReadiness).mockResolvedValue({
    status: 'ok',
    version: '0.1.0',
    checks: {
      database: { status: 'ok', latency_ms: 2.1 },
      redis: { status: 'ok', latency_ms: 1.3 },
    },
  })

  renderPage()

  expect(await screen.findByText('API 进程正常')).toBeInTheDocument()
  expect(screen.getByText('PostgreSQL 正常')).toBeInTheDocument()
  expect(screen.getByText('Redis 正常')).toBeInTheDocument()
  expect(screen.getByText('版本 0.1.0')).toBeInTheDocument()
})

test('shows the failed dependency when readiness is degraded', async () => {
  vi.mocked(systemApi.getLiveness).mockResolvedValue({
    status: 'ok',
    service: 'citypulse-api',
    version: '0.1.0',
  })
  vi.mocked(systemApi.getReadiness).mockResolvedValue({
    status: 'degraded',
    version: '0.1.0',
    checks: {
      database: { status: 'ok', latency_ms: 2.1 },
      redis: { status: 'error', latency_ms: 2_000 },
    },
  })

  renderPage()

  expect(await screen.findByText('Redis 异常')).toBeInTheDocument()
  expect(screen.getByText('PostgreSQL 正常')).toBeInTheDocument()
})

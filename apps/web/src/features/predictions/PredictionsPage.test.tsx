import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { PredictionsPage } from './PredictionsPage'
import * as api from './api'
import type { PredictionResults, PredictionRunList } from '../../shared/api/types'

const mocks = vi.hoisted(() => ({
  hasRole: vi.fn(),
}))

vi.mock('../../app/AuthContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../app/AuthContext')>()
  return {
    ...actual,
    useAuth: () => ({
      login: vi.fn(),
      logout: vi.fn(),
      user: {
        id: 'u1',
        username: 'analyst',
        display_name: '分析师',
        is_active: true,
        roles: ['analyst'],
      },
      status: 'authenticated' as const,
      hasRole: mocks.hasRole,
    }),
  }
})

vi.mock('./api')

const RUN: PredictionRunList = {
  items: [
    {
      id: 'run-1',
      window_days: 14,
      status: 'succeeded',
      as_of_date: '2026-08-16',
      city_count: 2,
      scoring_version_id: 'sv-1',
      data_fingerprint: 'abc',
      created_at: '2026-08-16T10:00:00+08:00',
      finished_at: '2026-08-16T10:00:05+08:00',
      error: null,
    },
  ],
  total: 1,
}

const RESULTS: PredictionResults = {
  run: RUN.items[0],
  items: [
    {
      id: 'r-1',
      run_id: 'run-1',
      city_code: '222401',
      city_name: '延吉',
      province: '吉林',
      trend_rank: 1,
      trend_score: 76.7,
      risk_pressure: 28,
      evidence_coverage: 1,
      action_priority: 'high',
      data_stale: false,
      momentum: 1.75,
      accelerating: true,
      factors: { content_growth: 84, novelty: 86 },
      blockers: [],
    },
    {
      id: 'r-2',
      run_id: 'run-1',
      city_code: '370300',
      city_name: '淄博',
      province: '山东',
      trend_rank: 2,
      trend_score: 39.4,
      risk_pressure: 28,
      evidence_coverage: 1,
      action_priority: 'watch',
      data_stale: false,
      momentum: 1.0,
      accelerating: false,
      factors: { content_growth: 26 },
      blockers: [],
    },
  ],
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <PredictionsPage />
    </QueryClientProvider>,
  )
}

test('renders the leaderboard with separated outputs', async () => {
  mocks.hasRole.mockReturnValue(false)
  vi.mocked(api.listRuns).mockResolvedValue(RUN)
  vi.mocked(api.runResults).mockResolvedValue(RESULTS)

  renderPage()

  expect(await screen.findByText('延吉')).toBeInTheDocument()
  expect(screen.getByText('淄博')).toBeInTheDocument()
  expect(screen.getByText('行动')).toBeInTheDocument()
  expect(screen.getByText('观察')).toBeInTheDocument()
  expect(screen.getAllByText('100%').length).toBeGreaterThanOrEqual(2)
})

test('city detail shows factor breakdown and series', async () => {
  mocks.hasRole.mockReturnValue(false)
  vi.mocked(api.listRuns).mockResolvedValue(RUN)
  vi.mocked(api.runResults).mockResolvedValue(RESULTS)
  vi.mocked(api.cityTrend).mockResolvedValue({
    city_code: '222401',
    city_name: '延吉',
    province: '吉林',
    result: RESULTS.items[0],
    series: {
      content_growth: [
        { metric_date: '2026-08-14', value: 84 },
        { metric_date: '2026-08-15', value: 85 },
      ],
    },
    series_window_days: 14,
  })

  renderPage()

  fireEvent.click((await screen.findAllByRole('button', { name: '详情' }))[0])

  expect(await screen.findByText('趋势分（非概率）')).toBeInTheDocument()
  expect(await screen.findByText('内容增速')).toBeInTheDocument()
  expect(screen.getByText('84.0 → 85.0')).toBeInTheDocument()
})

test('analyst can create a prediction run', async () => {
  mocks.hasRole.mockImplementation((role: string) => role === 'analyst')
  vi.mocked(api.listRuns).mockResolvedValue({ items: [], total: 0 })
  vi.mocked(api.createRun).mockResolvedValue(RUN.items[0])

  renderPage()

  fireEvent.click(await screen.findByRole('button', { name: '创建预测运行' }))

  await waitFor(() => expect(api.createRun).toHaveBeenCalledWith(14))
})

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { BacktestsPage } from './BacktestsPage'
import * as api from './api'
import type { BacktestRunList, CityListResponse } from '../../shared/api/types'

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
      user: null,
      status: 'authenticated' as const,
      hasRole: mocks.hasRole,
    }),
  }
})

vi.mock('./api')

const CITIES: CityListResponse = {
  items: [
    {
      id: 'c1',
      code: '222401',
      name: '延吉',
      province: '吉林',
      valid_from: null,
      valid_to: null,
      aliases: [],
    },
    {
      id: 'c2',
      code: '370300',
      name: '淄博',
      province: '山东',
      valid_from: null,
      valid_to: null,
      aliases: [],
    },
  ],
  total: 2,
}

const RUNS: BacktestRunList = {
  items: [
    {
      id: 'bt-1',
      t0: '2026-07-15',
      cutoff_offsets: [30, 14, 7],
      window_days: 14,
      target_city_codes: ['222401'],
      control_city_codes: ['370300'],
      status: 'succeeded',
      error: null,
      created_at: '2026-08-16T12:00:00+08:00',
      finished_at: '2026-08-16T12:00:03+08:00',
      metrics: {
        hit_at_5: 1.0,
        hit_at_5_note: 'descriptive only when candidates < 6',
        mean_lead_days: 7,
        lead_days: [7],
        false_alerts_per_100: 0,
        evidence_coverage: 1.0,
        candidate_count: 2,
        snapshots: [
          {
            offset_days: 7,
            cutoff_at: '2026-07-08T15:59:59+00:00',
            ranking: [
              { city_code: '222401', trend_score: 76.7 },
              { city_code: '370300', trend_score: 39.4 },
            ],
            evidence_coverage: 1.0,
          },
        ],
      },
    },
  ],
  total: 1,
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <BacktestsPage />
    </QueryClientProvider>,
  )
}

test('renders metrics cards and cutoff snapshots', async () => {
  mocks.hasRole.mockReturnValue(false)
  vi.mocked(api.listCities).mockResolvedValue(CITIES)
  vi.mocked(api.listBacktests).mockResolvedValue(RUNS)

  renderPage()

  expect(await screen.findByText('平均提前量')).toBeInTheDocument()
  expect(screen.getAllByText('100%').length).toBeGreaterThanOrEqual(2)
  expect(screen.getByText('7 天')).toBeInTheDocument()
  expect(screen.getByText(/222401 \/ 76.7/)).toBeInTheDocument()
  expect(screen.getByText(/descriptive only/)).toBeInTheDocument()
})

test('analyst selects cohorts and runs a backtest', async () => {
  mocks.hasRole.mockImplementation((role: string) => role === 'analyst')
  vi.mocked(api.listCities).mockResolvedValue(CITIES)
  vi.mocked(api.listBacktests).mockResolvedValue({ items: [], total: 0 })
  vi.mocked(api.createBacktest).mockResolvedValue(RUNS.items[0])

  renderPage()

  const targetCheck = await screen.findAllByRole('checkbox')
  fireEvent.click(targetCheck[0])

  fireEvent.click(screen.getByRole('button', { name: '运行回测（T0-30/14/7 截点）' }))

  await waitFor(() =>
    expect(api.createBacktest).toHaveBeenCalledWith({
      t0: '2026-07-15',
      target_city_codes: ['222401'],
      control_city_codes: [],
      window_days: 14,
    }),
  )
})

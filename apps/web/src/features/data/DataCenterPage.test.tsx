import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { DataCenterPage } from './DataCenterPage'
import * as dataApi from './api'
import type { Dataset } from '../../shared/api/types'

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

function makeDataset(overrides: Partial<Dataset> = {}): Dataset {
  return {
    id: 'ds-1',
    source_type: 'analyst_upload',
    source_name: '文旅局公开月报',
    legal_basis: '公开统计公报',
    original_filename: 'sample.csv',
    stored_filename: 'stored.csv',
    sha256: 'abcdef1234567890abcdef1234567890',
    byte_size: 512,
    status: 'uploaded',
    report: null,
    created_at: '2026-08-16T01:00:00+08:00',
    validated_at: null,
    committed_at: null,
    ...overrides,
  }
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <DataCenterPage />
    </QueryClientProvider>,
  )
}

test('lists datasets with status badges and row counts', async () => {
  mocks.hasRole.mockReturnValue(false)
  vi.mocked(dataApi.listDatasets).mockResolvedValue({
    items: [
      makeDataset(),
      makeDataset({
        id: 'ds-2',
        source_name: '高德 POI 快照',
        original_filename: 'poi.xlsx',
        status: 'committed',
        report: {
          row_count: 30,
          city_count: 3,
          metric_date_min: '2026-07-01',
          metric_date_max: '2026-07-10',
          errors: [],
          warnings: [],
        },
      }),
    ],
    total: 2,
  })

  renderPage()

  expect(await screen.findByText('文旅局公开月报')).toBeInTheDocument()
  expect(screen.getByText('已上传')).toBeInTheDocument()
  expect(screen.getByText('已提交')).toBeInTheDocument()
  expect(screen.getByText('30 行 / 3 城')).toBeInTheDocument()
})

test('analyst can trigger validation for an uploaded dataset', async () => {
  mocks.hasRole.mockImplementation((role: string) => role === 'analyst')
  vi.mocked(dataApi.listDatasets).mockResolvedValue({ items: [makeDataset()], total: 1 })
  vi.mocked(dataApi.validateDataset).mockResolvedValue({
    dataset: makeDataset({ status: 'valid' }),
    report: {
      row_count: 3,
      city_count: 2,
      metric_date_min: '2026-07-01',
      metric_date_max: '2026-07-02',
      errors: [],
      warnings: [],
    },
  })

  renderPage()

  const validateButton = await screen.findByRole('button', { name: '校验' })
  fireEvent.click(validateButton)

  await waitFor(() => expect(dataApi.validateDataset).toHaveBeenCalledWith('ds-1'))
})

test('invalid datasets expose blocking errors in the detail view', async () => {
  mocks.hasRole.mockReturnValue(false)
  vi.mocked(dataApi.listDatasets).mockResolvedValue({
    items: [
      makeDataset({
        status: 'invalid',
        report: {
          row_count: 1,
          city_count: 0,
          metric_date_min: null,
          metric_date_max: null,
          errors: [
            { code: 'UNKNOWN_CITY', message: "City code '999999' is not present.", row: 2, column: 'city_code' },
          ],
          warnings: [],
        },
      }),
    ],
    total: 1,
  })

  renderPage()

  fireEvent.click(await screen.findByRole('button', { name: '详情' }))

  expect(await screen.findByText(/UNKNOWN_CITY/)).toBeInTheDocument()
})

test('city catalog tab searches the catalog', async () => {
  mocks.hasRole.mockReturnValue(false)
  vi.mocked(dataApi.listDatasets).mockResolvedValue({ items: [], total: 0 })
  vi.mocked(dataApi.searchCities).mockResolvedValue({
    items: [
      {
        id: 'c1',
        code: '370300',
        name: '淄博',
        province: '山东',
        valid_from: null,
        valid_to: null,
        aliases: [],
      },
    ],
    total: 1,
  })

  renderPage()

  fireEvent.click(await screen.findByRole('tab', { name: '城市目录' }))

  expect(await screen.findByText('370300')).toBeInTheDocument()
  expect(screen.getByText('淄博')).toBeInTheDocument()
})

import { getJson, postJson } from '../../shared/api/client'
import type { BacktestRun, BacktestRunList, CityListResponse } from '../../shared/api/types'

export const listBacktests = () => getJson<BacktestRunList>('/api/v1/backtest-runs')

export const createBacktest = (payload: {
  t0: string
  target_city_codes: string[]
  control_city_codes: string[]
  window_days: 7 | 14 | 30
}) => postJson<BacktestRun>('/api/v1/backtest-runs', payload)

export const listCities = () => getJson<CityListResponse>('/api/v1/cities?limit=100')

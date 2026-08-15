import { getJson, postJson } from '../../shared/api/client'
import type {
  CityTrend,
  JobList,
  PredictionResults,
  PredictionRun,
  PredictionRunList,
} from '../../shared/api/types'

export const listRuns = () => getJson<PredictionRunList>('/api/v1/prediction-runs')

export const createRun = (windowDays: 7 | 14 | 30) =>
  postJson<PredictionRun>('/api/v1/prediction-runs', { window_days: windowDays })

export const runResults = (runId: string) =>
  getJson<PredictionResults>(`/api/v1/prediction-runs/${runId}/results`)

export const cityTrend = (cityCode: string, runId: string | null, windowDays = 14) =>
  getJson<CityTrend>(
    `/api/v1/cities/${cityCode}/trend?window_days=${windowDays}` +
      (runId ? `&run_id=${runId}` : ''),
  )

export const listJobs = () => getJson<JobList>('/api/v1/jobs')

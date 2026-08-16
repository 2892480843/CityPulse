import { getJson, postForm, postJson } from '../../shared/api/client'
import type {
  CityListResponse,
  DatasetCommitResponse,
  DatasetCreateResponse,
  DatasetListResponse,
  DatasetValidateResponse,
} from '../../shared/api/types'

export const listDatasets = () => getJson<DatasetListResponse>('/api/v1/datasets')

export const uploadDataset = (form: FormData) =>
  postForm<DatasetCreateResponse>('/api/v1/datasets', form)

export const validateDataset = (id: string) =>
  postJson<DatasetValidateResponse>(`/api/v1/datasets/${id}/validate`)

export const commitDataset = (id: string) =>
  postJson<DatasetCommitResponse>(`/api/v1/datasets/${id}/commit`)

export const searchCities = (query: string) =>
  getJson<CityListResponse>(`/api/v1/cities?q=${encodeURIComponent(query)}&limit=20`)

export const listDataSources = () =>
  getJson<import('../../shared/api/types').DataSourceList>('/api/v1/data-sources')

export const syncDataSource = (id: string) =>
  postJson<{
    source: import('../../shared/api/types').DataSourceView
    result: Record<string, unknown>
  }>(`/api/v1/data-sources/${id}/sync`)

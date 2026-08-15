export type RoleName = 'admin' | 'analyst' | 'operator'

export type CurrentUser = {
  id: string
  username: string
  display_name: string
  is_active: boolean
  roles: RoleName[]
}

export type DatasetStatus =
  | 'uploaded'
  | 'validating'
  | 'valid'
  | 'invalid'
  | 'committed'
  | 'archived'

export type ValidationIssue = {
  code: string
  message: string
  row: number | null
  column: string | null
}

export type DatasetReport = {
  row_count: number
  city_count: number
  metric_date_min: string | null
  metric_date_max: string | null
  errors: ValidationIssue[]
  warnings: ValidationIssue[]
}

export type Dataset = {
  id: string
  source_type: 'official_sync' | 'analyst_upload'
  source_name: string
  legal_basis: string
  original_filename: string
  stored_filename: string
  sha256: string
  byte_size: number
  status: DatasetStatus
  report: DatasetReport | null
  created_at: string
  validated_at: string | null
  committed_at: string | null
}

export type DatasetListResponse = {
  items: Dataset[]
  total: number
}

export type DatasetCreateResponse = {
  dataset: Dataset
  already_exists: boolean
}

export type DatasetValidateResponse = {
  dataset: Dataset
  report: DatasetReport
}

export type DatasetCommitResponse = {
  dataset: Dataset
  version_no: number
  observation_count: number
  already_committed: boolean
}

export type Observation = {
  city_code: string
  metric_date: string
  metric_name: string
  value: number
  source_url: string | null
  published_at: string | null
  observed_at: string | null
  available_at: string
}

export type ObservationListResponse = {
  items: Observation[]
  limit: number
}

export type CityView = {
  id: string
  code: string
  name: string
  province: string
  valid_from: string | null
  valid_to: string | null
  aliases: string[]
}

export type CityListResponse = {
  items: CityView[]
  total: number
}

export type UserAdminView = {
  id: string
  username: string
  display_name: string
  is_active: boolean
  roles: RoleName[]
  created_at: string
  last_login_at: string | null
}

export type UserListResponse = {
  items: UserAdminView[]
  total: number
}

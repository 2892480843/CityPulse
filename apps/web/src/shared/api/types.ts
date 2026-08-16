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

export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed'
export type ActionPriority = 'high' | 'medium' | 'watch' | 'blocked'
export type PlanStatus = 'draft' | 'pending_review' | 'approved' | 'rejected' | 'archived'

export type PredictionRun = {
  id: string
  window_days: number
  status: RunStatus
  as_of_date: string
  city_count: number
  scoring_version_id: string
  data_fingerprint: string
  created_at: string
  finished_at: string | null
  error: string | null
}

export type PredictionRunList = { items: PredictionRun[]; total: number }

export type PredictionResult = {
  id: string
  run_id: string
  city_code: string
  city_name: string
  province: string
  trend_rank: number
  trend_score: number
  risk_pressure: number
  evidence_coverage: number
  action_priority: ActionPriority
  data_stale: boolean
  factors: Record<string, number>
  blockers: string[]
}

export type PredictionResults = {
  run: PredictionRun
  items: PredictionResult[]
}

export type CityTrend = {
  city_code: string
  city_name: string
  province: string
  result: PredictionResult | null
  series: Record<string, { metric_date: string; value: number }[]>
  series_window_days: number
}

export type Job = {
  id: string
  job_type: 'prediction_run' | 'backtest_run' | 'action_generation'
  status: RunStatus
  ref_type: string | null
  ref_id: string | null
  summary: string | null
  error: string | null
  created_at: string
  finished_at: string | null
}

export type JobList = { items: Job[]; total: number }

export type ActionPlan = {
  id: string
  prediction_result_id: string
  run_id: string
  city_code: string
  city_name: string
  status: PlanStatus
  generator_type: 'rule_fallback' | 'deepseek'
  generation_note: string | null
  target_segment: string
  action_window_start: string | null
  action_window_end: string | null
  product_bundle: { type: string; reason: string; priority: string }[]
  campaign_theme: string
  supply_actions: string[]
  assumptions: string[]
  risk_notes: string
  created_by: string
  created_at: string
  updated_at: string
  reviewed_by: string | null
  reviewed_at: string | null
  review_comment: string | null
}

export type ActionPlanList = { items: ActionPlan[]; total: number }

export type BacktestSnapshotEntry = {
  city_code: string
  trend_score: number
}

export type BacktestRun = {
  id: string
  t0: string
  cutoff_offsets: number[]
  window_days: number
  target_city_codes: string[]
  control_city_codes: string[]
  status: RunStatus
  error: string | null
  created_at: string
  finished_at: string | null
  metrics: {
    hit_at_5: number | null
    hit_at_5_note: string | null
    mean_lead_days: number | null
    lead_days: number[]
    false_alerts_per_100: number | null
    evidence_coverage: number | null
    candidate_count: number
    snapshots: {
      offset_days: number
      cutoff_at: string
      ranking: BacktestSnapshotEntry[]
      evidence_coverage: number
    }[]
  } | null
}

export type BacktestRunList = { items: BacktestRun[]; total: number }

export type CalibrationVerdict =
  | 'insufficient_samples'
  | 'eligible_for_validation'
  | 'not_eligible'

export type CalibrationReport = {
  id: string
  backtest_run_id: string
  sample_size: number
  brier: number
  ece: number
  bins: { bin_low: number; bin_high: number; count: number; mean_score: number; observed_rate: number }[]
  verdict: CalibrationVerdict
  created_by: string
  created_at: string
}

export type CalibrationListResponse = {
  items: CalibrationReport[]
  total: number
  gate_note: string
}

export type CityEvidence = {
  city_code: string
  total_observations: number
  sourced_share: number
  metric_coverage: number
  covered_metrics: string[]
  missing_metrics: string[]
  date_min: string | null
  date_max: string | null
  latest_available_at: string | null
  sources: string[]
}

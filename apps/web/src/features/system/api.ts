import { getJson } from '../../shared/api/client'

export type Liveness = {
  status: 'ok'
  service: string
  version: string
}

export type CheckResult = {
  status: 'ok' | 'error'
  latency_ms: number
}

export type Readiness = {
  status: 'ok' | 'degraded'
  version: string
  checks: Record<'database' | 'redis', CheckResult>
}

export const getLiveness = () => getJson<Liveness>('/health/live')
export const getReadiness = () => getJson<Readiness>('/health/ready', [503])
